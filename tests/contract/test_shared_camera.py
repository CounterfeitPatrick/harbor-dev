"""Contract: one camera angle, shared by every render harbor produces.

Renders are compared BY EYE — the S6 keyframe judgement, and a reward candidate's rollout
against its siblings. That comparison only means something if the camera stood in the same
place. Two tasks shot from different angles look different when they are not; two candidates
of the SAME task shot differently make a behavior change indistinguishable from a framing
change.

The angle is defined in render.py (trained-policy videos) and mirrored in the S6 render smoke.
They live in different template trees and cannot import each other, so this asserts the
numbers agree. It exists because a refactor once turned the smoke's camera into a free-form
agent-filled slot, and every agent duly invented its own angle.
"""
import re

from _pluginmeta import ROOT

RENDER_PY = (ROOT / "knowledge/templates/rl-integration-generator/custom_torch/scripts"
             / "render.py.template")
SMOKE_S6 = ROOT / "knowledge/templates/task-generator/smokes/smoke_s6_render.py.template"


def _triple(text, pattern):
    m = re.search(pattern, text)
    assert m, f"camera definition not found for pattern {pattern!r}"
    return tuple(round(float(v), 6) for v in re.findall(r"-?\d+\.?\d*", m.group(1)))


def test_render_and_smoke_share_one_camera():
    render = RENDER_PY.read_text(encoding="utf-8")
    smoke = SMOKE_S6.read_text(encoding="utf-8")

    render_eye = _triple(render, r'"viewer_eye"\s*,\s*(\[[^\]]+\])')
    render_target = _triple(render, r'"viewer_target"\s*,\s*(\[[^\]]+\])')
    smoke_eye = _triple(smoke, r'cfg\.viewer\.eye\s*=\s*(\([^)]+\))')
    smoke_lookat = _triple(smoke, r'cfg\.viewer\.lookat\s*=\s*(\([^)]+\))')

    assert smoke_eye == render_eye, (
        f"S6 smoke eye {smoke_eye} != render.py viewer_eye {render_eye}. Every harbor render "
        f"must share one angle, or keyframes stop being comparable across tasks and across "
        f"candidates of the same task."
    )
    assert smoke_lookat == render_target, (
        f"S6 smoke lookat {smoke_lookat} != render.py viewer_target {render_target}."
    )


def test_smoke_camera_is_not_an_agent_filled_slot():
    """The framing must be concrete in the template. A required free-form slot is how the
    per-task drift got introduced — each agent picks its own numbers."""
    smoke = SMOKE_S6.read_text(encoding="utf-8")
    body = smoke.split('"""', 2)[-1]        # skip the docstring's slot listing
    for line in ("cfg.viewer.eye", "cfg.viewer.lookat"):
        assert re.search(rf"^{re.escape(line)}\s*=\s*\(", body, re.M), (
            f"{line} is not concretely set in the template body"
        )
    assert "{{VIEWER_BLOCK}}" not in smoke, (
        "VIEWER_BLOCK was the required free-form slot that caused the drift; the shared "
        "framing is now concrete and only VIEWER_OVERRIDE_BLOCK (optional) remains"
    )

"""Unit: the deterministic halves of the harness canary (no model calls).

The live run is `make harness-smoke`; these tests only pin that the embedded
fixture keeps rendering through the real adapter with resolvable dispatch
names, and that the artifact judgment is strict.
"""
import importlib.util
import json
import sys

from _pluginmeta import ROOT

sys.path.insert(0, str(ROOT / "tools"))
from adapters import base, codex  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "harness_smoke", ROOT / "tools" / "harness_smoke.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)


def test_fixture_renders_with_resolvable_dispatch_names(tmp_path):
    fixture = smoke.write_fixture(tmp_path / "src")
    codex.emit(base.Source(fixture), tmp_path)
    skill = (tmp_path / ".agents/skills/harbor-canary/SKILL.md").read_text()
    coordinator = (tmp_path /
                   ".codex/agents/harbor-canary-coordinator.toml").read_text()
    worker = (tmp_path / ".codex/agents/harbor-canary-worker.toml").read_text()
    # Both dispatch layers reference names the tree registers, and both
    # agents may write — the exact properties the live canary exercises.
    assert "Agent(harbor-canary-coordinator," in skill
    assert "Agent(harbor-canary-worker," in coordinator
    assert 'sandbox_mode = "workspace-write"' in coordinator
    assert 'sandbox_mode = "workspace-write"' in worker


def test_verify_judges_from_the_artifact_alone(tmp_path):
    out = tmp_path / "result.json"
    assert smoke.verify(out, "canary-1")[0] is False        # never written
    out.write_text("[]")                                    # valid JSON, not an object
    ok, detail = smoke.verify(out, "canary-1")
    assert not ok and "JSON object" in detail
    out.write_text(json.dumps({"input": "canary-1", "worker_ran": True}))
    ok, detail = smoke.verify(out, "canary-1")              # worker only
    assert not ok and "coordinator_ran" in detail
    out.write_text(json.dumps({"input": "canary-1", "worker_ran": True,
                               "coordinator_ran": True, "status": "ok"}))
    assert smoke.verify(out, "canary-1") == (True, "ok")
    assert smoke.verify(out, "canary-2")[0] is False        # token mismatch

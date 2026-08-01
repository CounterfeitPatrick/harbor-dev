"""Unit: scripts/reward-tuning-agent/score_iter.py — the one success_rate formula.

Locks in the two behaviors the reward-tune loop depends on:

1. `success_rate = <success term's episodic return> / <its design weight>`, computed
   identically for every candidate so iterations are comparable.
2. An ungradable run yields `success_rate: null` + a gate reason and still exits 0 —
   the designer must SEE that a run was ungradable rather than receive a number
   fabricated from the total-only curve.
"""
import json
import subprocess
import sys

from _pluginmeta import ROOT

SCRIPT = ROOT / "scripts" / "reward-tuning-agent" / "score_iter.py"

DESIGN = {
    "kind": "structured",
    "task_changes": {"sections": [], "changes": []},
    "reward": {
        "composer": "sum",
        "success_term": "stack_success",
        "terms": [
            {"name": "reach", "weight": 1.0},
            {"name": "stack_success", "weight": 200.0},
        ],
    },
}


def _write(tmp_path, metrics_rows, design=DESIGN):
    m = tmp_path / "metrics.jsonl"
    m.write_text("".join(json.dumps(r) + "\n" for r in metrics_rows))
    d = tmp_path / "design.json"
    d.write_text(json.dumps(design))
    return m, d


def _run(metrics, design, *extra):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--metrics", str(metrics),
         "--design", str(design), "--iter", "7", *extra],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_success_rate_is_term_return_over_weight(tmp_path):
    m, d = _write(tmp_path, [
        {"step": 100, "reward/total/episodic_return_mean": 10.0,
         "reward/reach/episodic_return_mean": 8.0,
         "reward/stack_success/episodic_return_mean": 20.0},
        {"step": 200, "reward/total/episodic_return_mean": 74.0,
         "reward/reach/episodic_return_mean": 12.0,
         "reward/stack_success/episodic_return_mean": 62.0},
    ])
    v = _run(m, d)
    assert v["gate"] == "ok"
    assert v["success_rate"] == 62.0 / 200.0     # last step, not the max or the mean
    assert v["total_return"] == 74.0
    assert v["per_term"] == {"reach": 12.0, "stack_success": 62.0}
    assert v["iter"] == 7 and v["status"] == "scored"


def test_long_format_metrics_parse(tmp_path):
    m, d = _write(tmp_path, [
        {"key": "reward/total/episodic_return_mean", "step": 1, "value": 5.0},
        {"key": "reward/stack_success/episodic_return_mean", "step": 1, "value": 50.0},
        {"key": "reward/stack_success/episodic_return_mean", "step": 2, "value": 100.0},
        {"key": "reward/total/episodic_return_mean", "step": 2, "value": 120.0},
    ])
    v = _run(m, d)
    assert v["success_rate"] == 0.5 and v["total_return"] == 120.0


def test_total_only_curves_are_ungradable(tmp_path):
    m, d = _write(tmp_path, [
        {"step": 1, "reward/total/episodic_return_mean": 55.0},
    ])
    v = _run(m, d)
    assert v["success_rate"] is None
    assert v["gate"] == "total_only"
    assert v["per_term"] == {}


def test_missing_success_term_is_ungradable(tmp_path):
    m, d = _write(tmp_path, [
        {"step": 1, "reward/total/episodic_return_mean": 9.0,
         "reward/reach/episodic_return_mean": 9.0},
    ])
    v = _run(m, d)
    assert v["success_rate"] is None
    assert v["gate"] == "success_term_missing"
    assert "reach" in v["notes"][0]


def test_missing_metrics_file_is_a_result_not_a_crash(tmp_path):
    _, d = _write(tmp_path, [])
    v = _run(tmp_path / "absent.jsonl", d, "--status", "train_failed")
    assert v["success_rate"] is None and v["gate"] == "no_metrics"
    assert v["status"] == "train_failed"


def test_task_and_reward_smoke_failures_stay_distinguishable(tmp_path):
    """A broken sensor and a broken reward term look identical downstream unless the
    status and the per-smoke map say which one it was."""
    _, d = _write(tmp_path, [])
    v = _run(tmp_path / "absent.jsonl", d, "--status", "task_smoke_failed",
             "--smoke", "S1=pass", "--smoke", "S4=fail", "--smoke", "S6=skipped",
             "--failure-mode", "contact sensor never reports a hit")
    assert v["status"] == "task_smoke_failed"
    assert v["smokes"] == {"S1": "pass", "S4": "fail", "S6": "skipped"}
    assert v["success_rate"] is None

    v = _run(tmp_path / "absent.jsonl", d, "--status", "reward_smoke_failed",
             "--smoke", "S1=pass", "--smoke", "S6=fail")
    assert v["status"] == "reward_smoke_failed"
    assert v["smokes"]["S6"] == "fail"


def test_flat_legacy_design_still_scores(tmp_path):
    """An in-flight tune's design.json predates the task_changes/reward nesting."""
    flat = {"kind": "structured", "composer": "sum", "success_term": "stack_success",
            "terms": [{"name": "stack_success", "weight": 50.0}]}
    m, d = _write(tmp_path, [
        {"step": 1, "reward/total/episodic_return_mean": 30.0,
         "reward/stack_success/episodic_return_mean": 25.0},
    ], design=flat)
    v = _run(m, d)
    assert v["gate"] == "ok" and v["success_rate"] == 0.5


def test_prose_and_artifacts_pass_through(tmp_path):
    m, d = _write(tmp_path, [
        {"step": 1, "reward/total/episodic_return_mean": 1.0,
         "reward/stack_success/episodic_return_mean": 100.0},
    ])
    out = tmp_path / "verdict.json"
    v = _run(m, d, "--behavior", "arm reaches but never closes the gripper",
             "--failure-mode", "no grasp",
             "--finding", "contact gate never fires",
             "--artifact", "render_mp4=/abs/render.mp4",
             "--out", str(out))
    assert v["behavior"].startswith("arm reaches")
    assert v["failure_mode"] == "no grasp"
    assert v["findings"] == ["contact gate never fires"]
    assert v["artifacts"] == {"render_mp4": "/abs/render.mp4"}
    assert json.loads(out.read_text()) == v      # --out and stdout agree

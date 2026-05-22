"""
Score a single trial — compute composite score from metrics.json + flag
instabilities (NaN losses, return collapses).

The score formula matches references/rl-integration-generator/rl-suite-spec.md:

    if any task has success_metric:
        score = 0.50 * success_rate
              + 0.30 * normalized_eval_return
              + 0.15 * sample_efficiency
              - 0.05 * instability_penalty
    else:
        score = 0.60 * normalized_eval_return
              + 0.30 * sample_efficiency
              - 0.10 * instability_penalty

Normalization is min-max across the trials seen so far (read from
harbor/rl_experiments/history.jsonl). For the first trial of an algorithm,
normalized values are 1.0 by construction (single-point baseline).

Output: writes <trial_dir>/score.json + appends a one-liner to <trial_dir>/trial_summary.md.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--trial", required=True)
    return p.parse_args()


def load_history(repo: Path) -> list[dict]:
    h = repo / "harbor" / "rl_experiments" / "history.jsonl"
    if not h.exists():
        return []
    out: list[dict] = []
    for line in h.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def normalize(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 1.0  # single-point baseline
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def detect_instability(metrics: dict, train_log: Path) -> tuple[float, list[str]]:
    """Returns (penalty in [0,1], notes)."""
    notes: list[str] = []
    penalty = 0.0
    # NaN / inf in eval returns
    if metrics.get("eval_return_mean") is None or not math.isfinite(metrics.get("eval_return_mean", 0.0)):
        penalty += 0.5
        notes.append("eval_return_mean missing or non-finite")
    # Very high std vs mean
    mean = metrics.get("eval_return_mean", 0.0) or 0.0
    std = metrics.get("eval_return_std", 0.0) or 0.0
    if abs(mean) > 1e-3 and std / max(abs(mean), 1e-6) > 2.0:
        penalty += 0.25
        notes.append(f"high return std/mean ratio ({std/abs(mean):.2f})")
    # Train log NaN
    if train_log.exists():
        text = train_log.read_text()[-50_000:]  # tail
        if "nan" in text.lower() or "inf" in text.lower():
            penalty += 0.25
            notes.append("'nan' or 'inf' appeared in train log tail")
    return min(penalty, 1.0), notes


def main():
    args = parse_args()
    repo = args.repo.resolve()
    trial_dir = repo / "harbor" / "rl_experiments" / "runs" / args.trial
    metrics_path = trial_dir / "metrics.json"
    if not metrics_path.exists():
        print(json.dumps({"ok": False, "reason": f"missing {metrics_path}"}))
        return
    metrics = json.loads(metrics_path.read_text())

    history = load_history(repo)
    same_task_algo = [
        r for r in history
        if r.get("algo") == metrics.get("algo") and r.get("task") == metrics.get("task")
        and r.get("metrics")
    ]
    returns = [r["metrics"].get("eval_return_mean", 0.0) or 0.0 for r in same_task_algo]
    walls = [r.get("wall_time_sec", 1.0) or 1.0 for r in same_task_algo]
    if metrics.get("eval_return_mean") is not None:
        returns.append(metrics["eval_return_mean"])
    if metrics.get("wall_time_sec") is not None:
        walls.append(metrics["wall_time_sec"])

    norm_return = normalize(metrics.get("eval_return_mean") or 0.0, min(returns), max(returns))
    # Sample efficiency: lower wall-time-per-return is better; invert + normalize.
    eff = (metrics.get("eval_return_mean") or 0.0) / max(metrics.get("wall_time_sec") or 1.0, 1e-3)
    effs = [(r["metrics"].get("eval_return_mean") or 0.0) / max(r.get("wall_time_sec") or 1.0, 1e-3)
            for r in same_task_algo]
    effs.append(eff)
    norm_eff = normalize(eff, min(effs), max(effs))

    instability, notes = detect_instability(metrics, trial_dir / "train.log")

    if metrics.get("success_rate") is not None:
        score = 0.50 * float(metrics["success_rate"]) + 0.30 * norm_return + 0.15 * norm_eff - 0.05 * instability
    else:
        score = 0.60 * norm_return + 0.30 * norm_eff - 0.10 * instability

    out = {
        "trial_id": args.trial,
        "score": round(float(score), 4),
        "normalized_eval_return": round(norm_return, 4),
        "normalized_sample_efficiency": round(norm_eff, 4),
        "instability_penalty": round(instability, 4),
        "instability_notes": notes,
    }
    (trial_dir / "score.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

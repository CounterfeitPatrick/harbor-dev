#!/usr/bin/env python3
"""score_iter.py — turn a finished candidate's training log into the verdict JSON.

The single source of the `success_rate` arithmetic. Every candidate is scored by the
same code path, so two iterations of the same tune can be compared; when the agent
re-derived the formula per iteration, they could not.

Reads `metrics.jsonl` + the candidate's `design.json`, writes the complete verdict
object defined in knowledge/references/reward-tuning-agent/candidate-contract.md. The numeric
fields are computed here; the prose fields (`behavior`, `failure_mode`, `findings`)
are supplied by the candidate agent, which is the thing that watched the rollout.

Usage:
  score_iter.py --metrics <trial>/metrics.jsonl --design <iter>/design.json --iter 7
                [--status scored|task_smoke_failed|reward_smoke_failed|train_failed|early_stopped]
                [--smoke S1=pass]... [--behavior "..."] [--failure-mode "..."]
                [--finding "..."]... [--artifact render_mp4=<path>]...
                [--out <iter>/verdict.json]

Exits 0 with a verdict even when the run is ungradable — an ungradable run is a
RESULT the designer must see (`success_rate: null` + a gate note), not a crash.
Exits non-zero only on bad inputs (missing/unreadable files).
"""
import argparse
import json
import math
import os
import sys

from _metrics import final_values, load_series, peak_values

PREFIX, SUFFIX = "reward/", "/episodic_return_mean"
TOTAL_KEY = PREFIX + "total" + SUFFIX


def per_term_returns(final):
    """{term: episodic return} for every reward/<term>/episodic_return_mean key but total."""
    out = {}
    for k, v in final.items():
        if k.startswith(PREFIX) and k.endswith(SUFFIX) and isinstance(v, (int, float)):
            term = k[len(PREFIX):-len(SUFFIX)]
            if term != "total":
                out[term] = v
    return out


def reward_spec(design):
    """The reward half of a candidate design.

    A design is `{task_changes: {...}, reward: {...}}`. The flat legacy shape (reward keys
    at the top level) is still read so an in-flight tune's older design.json still scores.
    """
    return design.get("reward") or design


def term_weight(spec, name):
    for t in spec.get("terms", []):
        if t.get("name") == name:
            return t.get("weight")
    return None


def score(final, design):
    """Return (success_rate, gate, notes). success_rate is None whenever ungradable."""
    notes = []
    spec = reward_spec(design)
    per_term = per_term_returns(final)
    if not per_term:
        return None, "total_only", [
            "metrics.jsonl carries only reward/total/... — per-term logging regressed, "
            "so no success_rate can be computed. Do NOT infer one from the total curve."
        ]

    name = spec.get("success_term")
    if not name:
        return None, "no_success_term", ["design.json names no success_term"]
    if name not in per_term:
        return None, "success_term_missing", [
            f"success_term '{name}' is absent from the logged terms {sorted(per_term)} — "
            "the term was renamed in the implementation, or it never fired and the logger "
            "dropped it."
        ]

    weight = term_weight(spec, name)
    if not isinstance(weight, (int, float)) or weight == 0:
        return None, "bad_weight", [
            f"success_term '{name}' has weight {weight!r} in design.json; a non-zero "
            "numeric weight is required to normalize its episodic return into a rate."
        ]

    rate = per_term[name] / weight
    if not math.isfinite(rate):
        return None, "non_finite", [f"success_rate is not finite (term={per_term[name]}, weight={weight})"]
    if rate > 1.0:
        notes.append(
            f"success_rate {rate:.3f} > 1 — the success term fired more than once per "
            "episode on average; treat it as a rate ceiling, not a fraction."
        )
    return rate, "ok", notes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--metrics", required=True, help="<trial_dir>/metrics.jsonl")
    p.add_argument("--design", required=True, help="<iter_dir>/design.json")
    p.add_argument("--iter", type=int, required=True)
    p.add_argument("--status", default="scored",
                   choices=["scored", "task_smoke_failed", "reward_smoke_failed",
                            "train_failed", "early_stopped"])
    p.add_argument("--smoke", action="append", default=[], metavar="NAME=RESULT",
                   help="repeatable, e.g. S1=pass S4=fail S6=skipped")
    p.add_argument("--behavior", default="")
    p.add_argument("--failure-mode", default=None)
    p.add_argument("--finding", action="append", default=[])
    p.add_argument("--artifact", action="append", default=[],
                   metavar="KEY=PATH", help="repeatable, e.g. render_mp4=/abs/render.mp4")
    p.add_argument("--out", default=None, help="write the verdict here (also printed)")
    a = p.parse_args()

    if not os.path.isfile(a.design):
        sys.exit(f"design.json not found: {a.design}")
    with open(a.design) as f:
        design = json.load(f)

    if os.path.isfile(a.metrics):
        ser = load_series(a.metrics)
        final = final_values(ser)
        rate, gate, notes = score(final, design)
        per_term = per_term_returns(final)
        total = final.get(TOTAL_KEY)

        # Peak-vs-final. A run that peaked and collapsed is scored on the collapse unless the
        # designer is shown the gap, and the end-of-training checkpoint is then not the policy
        # that earned the peak.
        peak = peak_values(ser)
        peak_total, peak_step = peak.get(TOTAL_KEY, (None, None))
        peak_rate, _, _ = score({k: v for k, (v, _) in peak.items()}, design)
        if (peak_total is not None and total is not None
                and peak_total > 0 and total < 0.7 * peak_total):
            notes.append(
                f"run PEAKED at total_return {peak_total:.1f} @step {peak_step} and ended at "
                f"{total:.1f} ({total / peak_total:.0%} of peak) — the final checkpoint is not "
                f"the best policy this run produced. Score the run on both; render "
                f"checkpoint_best.pth, not checkpoint.pth."
            )
    else:
        rate, gate, notes = None, "no_metrics", [f"metrics.jsonl not found: {a.metrics}"]
        per_term, total = {}, None
        peak_total = peak_step = peak_rate = None

    def _pairs(items):
        out = {}
        for item in items:
            k, _, v = item.partition("=")
            if k:
                out[k] = v
        return out

    verdict = {
        "iter": a.iter,
        "status": a.status,
        "smokes": _pairs(a.smoke),
        "success_rate": rate,
        "total_return": total,
        "peak": {"success_rate": peak_rate, "total_return": peak_total, "step": peak_step},
        "per_term": {k: round(v, 4) for k, v in sorted(per_term.items())},
        "gate": gate,
        "behavior": a.behavior,
        "failure_mode": a.failure_mode,
        "findings": a.finding,
        "notes": notes,
        "artifacts": _pairs(a.artifact),
    }

    out = json.dumps(verdict, indent=2)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out + "\n")
    print(out)


if __name__ == "__main__":
    main()

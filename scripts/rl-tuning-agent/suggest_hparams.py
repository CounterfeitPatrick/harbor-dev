"""
Suggest the next-trial hyperparameter config given the trials seen so far.

Strategy: random search within the per-algorithm `search_space` block of the
current config, biased toward the neighborhood of the best-scoring trial seen
for the same (algo, task) pair (Gaussian perturbation for log_uniform/uniform;
weighted re-sample for choice).

This is intentionally simple — for true Bayesian optimization the user can
plug in optuna / nevergrad later. The scaffold leaves a clean `propose()`
function for that swap.

Usage:
    python scripts/rl-tuning-agent/suggest_hparams.py \\
        --repo /abs/repo --algo ppo --task <task_id> --base-config harbor/configs/rl/ppo.yaml \\
        --output harbor/rl_experiments/runs/<next_trial_id>/config.yaml
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import random
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--algo", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--base-config", required=True, type=Path,
                   help="Path to the algorithm's base YAML (relative to --repo or absolute)")
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--seed", type=int, default=None)
    return p.parse_args()


def load_yaml(path: Path) -> dict:
    import yaml
    return yaml.safe_load(path.read_text()) or {}


def dump_yaml(data: dict, path: Path) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))


def best_trial(repo: Path, algo: str, task: str) -> dict | None:
    history = repo / "harbor" / "rl_experiments" / "history.jsonl"
    if not history.exists():
        return None
    best = None
    best_score = -math.inf
    for line in history.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("algo") != algo or r.get("task") != task:
            continue
        score_path = (repo / "harbor" / "rl_experiments" / "runs"
                      / r.get("trial_id", "_") / "score.json")
        if not score_path.exists():
            continue
        try:
            score = json.loads(score_path.read_text()).get("score", -math.inf)
        except json.JSONDecodeError:
            continue
        if score > best_score:
            best_score = score
            best = r
            best["score"] = score
            try:
                cfg_path = (repo / "harbor" / "rl_experiments" / "runs"
                            / r["trial_id"] / "resolved_config.yaml")
                if cfg_path.exists():
                    best["resolved_config"] = load_yaml(cfg_path)
            except Exception:
                pass
    return best


def propose(spec: dict, anchor: dict | None, rng: random.Random) -> dict:
    """spec: search_space dict. anchor: best-trial resolved config or None."""
    out: dict = {}
    for key, sp in spec.items():
        kind = sp.get("type")
        if kind == "log_uniform":
            lo, hi = float(sp["low"]), float(sp["high"])
            if anchor and key in anchor:
                base = float(anchor[key])
                # Perturb in log-space by ±0.5 dex around the anchor, clamped.
                log_base = math.log10(max(base, 1e-12))
                cand = 10 ** (log_base + rng.uniform(-0.5, 0.5))
                out[key] = max(lo, min(hi, cand))
            else:
                out[key] = 10 ** rng.uniform(math.log10(lo), math.log10(hi))
        elif kind == "uniform":
            lo, hi = float(sp["low"]), float(sp["high"])
            if anchor and key in anchor:
                base = float(anchor[key])
                cand = base + rng.uniform(-0.1, 0.1) * (hi - lo)
                out[key] = max(lo, min(hi, cand))
            else:
                out[key] = rng.uniform(lo, hi)
        elif kind == "choice":
            values = list(sp["values"])
            out[key] = rng.choice(values)
        else:
            raise ValueError(f"Unknown search-space kind: {kind!r}")
    return out


def main():
    args = parse_args()
    repo = args.repo.resolve()
    base_path = args.base_config if args.base_config.is_absolute() else (repo / args.base_config)
    base = load_yaml(base_path)
    spec = base.get("search_space")
    if not spec:
        raise SystemExit(f"No search_space block in {base_path}.")

    rng = random.Random(args.seed)
    anchor = (best_trial(repo, args.algo, args.task) or {}).get("resolved_config")
    proposal = propose(spec, anchor, rng)

    # Merge proposal into a copy of the base config (drop search_space from output —
    # it's not consumed by hydra and bloats the trial config.)
    merged = copy.deepcopy(base)
    merged.pop("search_space", None)
    for k, v in proposal.items():
        # Support nested keys via dotted notation, e.g. "noise.tgt_pol_std"
        if "." in k:
            parts = k.split(".")
            cur = merged
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = v
        else:
            merged[k] = v

    dump_yaml(merged, args.output)
    print(json.dumps({"ok": True, "output": str(args.output), "proposal": proposal,
                      "anchor_used": anchor is not None}, indent=2))


if __name__ == "__main__":
    main()

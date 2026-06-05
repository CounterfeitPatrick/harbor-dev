"""
Render <repo>/rl_experiment_report.md from
harbor/rl_experiments/{history.jsonl,runs/*,best/*}.

Legacy report renderer. The current rl-tuning-agent writes its own per-tune
`tuning-history.md` (see references/rl-tuning-agent/tuning-instruction.md);
this script remains for back-compat with older trial dirs.

Output is English-only (CLAUDE.md hard constraint #1).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = PLUGIN_ROOT / "templates" / "rl-tuning-agent" / "rl_experiment_report.md.template"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, type=Path)
    return p.parse_args()


def load_spec(repo: Path) -> dict:
    spec = repo / "harbor" / "rl-integration-generator" / "rl-suite-spec.json"
    if not spec.exists():
        raise SystemExit(f"{spec} not found — dispatch the rl-integration-generator subagent first.")
    return json.loads(spec.read_text())


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


def best_per_algo(repo: Path, history: list[dict]) -> dict[str, dict]:
    by_algo: dict[str, dict] = {}
    for r in history:
        algo = r.get("algo")
        if not algo:
            continue
        score_path = (repo / "harbor" / "rl_experiments" / "runs"
                      / r.get("trial_id", "_") / "score.json")
        if not score_path.exists():
            continue
        try:
            score = json.loads(score_path.read_text()).get("score")
        except json.JSONDecodeError:
            continue
        if score is None:
            continue
        cur = by_algo.get(algo)
        if cur is None or score > cur.get("score", float("-inf")):
            by_algo[algo] = {**r, "score": score}
    return by_algo


def render(template: str, mapping: dict[str, str]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def main():
    args = parse_args()
    repo = args.repo.resolve()
    spec = load_spec(repo)
    history = load_history(repo)
    bests = best_per_algo(repo, history)

    rows: list[str] = []
    for algo, info in sorted(bests.items()):
        m = info.get("metrics", {}) or {}
        rows.append(
            f"| {algo} | {sum(1 for r in history if r.get('algo') == algo)} "
            f"| {info.get('score', '-'):.4f} "
            f"| {m.get('eval_return_mean', '-')} "
            f"| {m.get('success_rate', '-')} "
            f"| `harbor/rl_experiments/best/{algo}/config.yaml` "
            f"| `harbor/rl_experiments/runs/{info.get('trial_id','-')}/checkpoint.zip` |"
        )
    history_block = "\n".join(
        f"- `{r.get('trial_id','-')}` — algo={r.get('algo','-')} task={r.get('task','-')} "
        f"exit={r.get('exit_code','-')} wall={r.get('wall_time_sec', 0):.0f}s"
        for r in history[-50:]
    ) or "_(no trials run yet)_"

    best_block = "\n".join(
        f"### {algo}\n"
        f"- Trial: `{info.get('trial_id','-')}`\n"
        f"- Score: {info.get('score','-'):.4f}\n"
        f"- Eval return mean: {info.get('metrics',{}).get('eval_return_mean','-')}\n"
        f"- Success rate: {info.get('metrics',{}).get('success_rate','-')}\n"
        f"- Checkpoint: `harbor/rl_experiments/runs/{info.get('trial_id','-')}/checkpoint.zip`\n"
        for algo, info in sorted(bests.items())
    ) or "_(no best trials computed yet)_"

    failures = [
        f"- `{r.get('trial_id','-')}` — exit={r.get('exit_code','-')} algo={r.get('algo','-')} task={r.get('task','-')}"
        for r in history if r.get("exit_code") not in (0, None)
    ]
    failures_block = "\n".join(failures) or "_(none)_"

    repro_lines = [
        f".venv/bin/python harbor/scripts/rl/tune.py --algo {algo} "
        f"--task {info.get('task','<task>')} --trial {info.get('trial_id','-')}"
        for algo, info in sorted(bests.items())
    ]

    wb = spec["logging"]["wandb"]
    wb_link = f"https://wandb.ai/{wb.get('entity') or '<entity>'}/{wb.get('project') or '<project>'}" \
        if wb.get("enabled") and wb.get("mode") == "online" else "(W&B disabled or offline)"

    body = render(TEMPLATE.read_text(), {
        "BENCHMARK_NAME": spec["benchmark"]["name"],
        "GENERATED_AT": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "REPO_PATH": spec["benchmark"]["repo_path"],
        "TASKS_LIST": ", ".join(t["id"] for t in spec.get("tasks", [])) or "(none)",
        "ALGORITHM_SOURCE": f"{spec['algorithm_source']['kind']} ({spec['algorithm_source'].get('package','')})",
        "ALGORITHM_SUMMARY_ROWS": "\n".join(rows) or "| _(no trials)_ |  |  |  |  |  |  |",
        "TOTAL_TRIALS": str(len(history)),
        "HISTORY_BLOCK": history_block,
        "BEST_PER_ALGORITHM_BLOCK": best_block,
        "TUNING_DECISIONS_BLOCK": "_(see per-trial trial_summary.md files)_",
        "FAILURES_BLOCK": failures_block,
        "REPRODUCTION_COMMANDS": "\n".join(repro_lines) or "# (no best trials yet)",
        "WANDB_PROJECT_LINK": wb_link,
    })

    out = repo / "rl_experiment_report.md"
    out.write_text(body)
    print(json.dumps({"ok": True, "report": str(out), "trials": len(history),
                      "best_per_algo": list(bests.keys())}, indent=2))


if __name__ == "__main__":
    main()

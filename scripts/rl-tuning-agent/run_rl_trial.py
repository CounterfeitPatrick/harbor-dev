"""
Execute one train → eval → (render) trial in the RL container, and append a
record to harbor/rl_experiments/history.jsonl.

The rl-tuning-agent calls this once per loop iteration. It expects the trial
config to already exist at harbor/rl_experiments/runs/<trial_id>/config.yaml
(the agent writes that before invoking this script).

Usage:
    python scripts/rl-tuning-agent/run_rl_trial.py \\
        --repo /abs/repo --algo ppo --task <task_id> --trial <trial_id>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--algo", required=True, choices=["ppo", "sac", "td3"])
    p.add_argument("--task", required=True)
    p.add_argument("--trial", required=True)
    p.add_argument("--skip-render", action="store_true")
    return p.parse_args()


def run(cmd: list[str], log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as f:
        f.write(f"$ {' '.join(cmd)}\n\n")
        f.flush()
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT)
    return rc


def main():
    args = parse_args()
    repo = args.repo.resolve()
    trial_dir = repo / "harbor" / "rl_experiments" / "runs" / args.trial
    trial_dir.mkdir(parents=True, exist_ok=True)
    if not (trial_dir / "config.yaml").exists():
        print(f"[error] {trial_dir/'config.yaml'} missing — rl-tuning-agent must write it first.",
              file=sys.stderr)
        sys.exit(2)

    venv_python = repo / ".venv" / "bin" / "python"
    if not venv_python.exists():
        print(f"[error] {venv_python} missing — run dependency-generator first.", file=sys.stderr)
        sys.exit(2)

    def wrap(cmd: list[str]) -> list[str]:
        # Replace any sys.executable head with the repo's venv python.
        if cmd and cmd[0] == sys.executable:
            return [str(venv_python), *cmd[1:]]
        return cmd

    started = time.time()
    train_cmd = wrap([sys.executable, "harbor/scripts/rl/tune.py",
                      "--algo", args.algo, "--task", args.task, "--trial", args.trial,
                      *(["--skip-render"] if args.skip_render else [])])
    rc = subprocess.call(train_cmd, cwd=str(repo))
    elapsed = time.time() - started

    metrics_path = trial_dir / "metrics.json"
    metrics = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text())
        except json.JSONDecodeError:
            metrics = {}

    record = {
        "trial_id": args.trial,
        "algo": args.algo,
        "task": args.task,
        "exit_code": rc,
        "wall_time_sec": elapsed,
        "metrics": metrics,
        "rendered_video": (trial_dir / "video.mp4").exists() and not args.skip_render,
        "ts": int(time.time()),
    }
    history = repo / "harbor" / "rl_experiments" / "history.jsonl"
    with history.open("a") as f:
        f.write(json.dumps(record) + "\n")

    print(json.dumps(record, indent=2))
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    main()

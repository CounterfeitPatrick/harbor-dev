---
description: Iteratively tune the §6 reward of an EXISTING task with an ASYNC fixed-pool controller. A thin orchestrator: the main agent runs pre-flight + (standalone only) picks the design base, then dispatches the self-contained `reward-tuning-agent`, which OWNS the whole loop — design each candidate's full reward spec, implement it in IsaacLab code, train + render (compute-side), score per-term curves + rendered frames → success_rate, keep `pool_size` candidates in flight (default 1 = serial; >1 = parallel, each on its own clone), and loop until `success_rate ≥ success_threshold`. Cloning is the deterministic scripts/task-cloner/clone_task.py; no agent nesting. Use when the user types /harbor:reward-tune task=<id> [algorithm=<algo>] [pool_size=N] [mode=local|cluster], or asks "tune the reward for task X".
argument-hint: task=<id> [algorithm=<ppo|sac|td3>] [wandb=<project>] [mode=local|cluster] [pool_size=N] [success_threshold=0.5] [timesteps_per_iter=N] [seed=N] [monitor_early_stop=true|false] [monitor_interval=300]
---

# /harbor:reward-tune — Async-Pool Reward Tuning

A **thin orchestrator**. The main agent does pre-flight, initializes `tune-state.json`, and (only in the
standalone case) selects the design base — then hands the entire loop to the self-contained
`reward-tuning-agent`, which designs + implements + trains + scores every candidate and keeps `pool_size`
candidates in flight until `success_rate ≥ success_threshold`. The main agent makes NO reward-design
decisions; it just persists the final outcome.

```
Step 0  (main agent)          → pre-flight: venv / specs / build / ffmpeg / wandb / per-term-logging
Step 1  (main agent)          → init tune-state; standalone-only: task-library-search → library_refs
Step 2  (reward-tuning-agent) → OWNS the loop: DESIGN → IMPLEMENT → train+render → SCORE, async pool
Step 3  (main agent)          → persist the returned verdict + tune-state.json:status
```

## File layout (`create-task/<slug>/`)

```
<repo>/harbor/create-task/<task_slug>/
├── spec.json / task-history.md                 # from /harbor:task-create (if present)
├── tune-state.json                             # tune metadata + pool + in_flight + per-iter (agent-owned)
├── reward-history.md                           # SHARED; "## Iter <N>" appended per candidate
├── handoff-reward-generator.md                 # latest BEST reward state (overwritten on new best)
├── memories.jsonl                              # cumulative findings (cross-candidate channel)
├── smokes/smoke_s6.py                          # rendered per candidate
├── clone-slot<i>.json                          # task-cloner manifest per slot (pool_size>1)
└── iter_<NNN>/                                  # one per candidate (NNN = global candidate index)
    ├── design.json                             # the B1 spec the agent decided
    ├── run.sh | launch.sh                       # train + render wrapper
    ├── run.log | slurm-*.out                    # captured
    ├── render.mp4 ; frames/                      # the rollout + extracted frames
    ├── analysis.md                             # SCORE output
    └── .done                                    # completion signal
```

## Required arguments

| Arg | Notes |
|---|---|
| `task` | Task ID. `gym.make(<task>)` must succeed. Its §6 may be a placeholder or a real reward. |

## Optional arguments

**Rule: if an arg isn't passed, don't override the config — leave its default untouched.** Only forward a
train-command override (`seed=`, `total_timesteps=`, …) for args the user explicitly set. The loop-control
args (`pool_size`, `on_success`, `success_threshold`, `n_frames`, `prompt_every_n_stuck`,
`monitor_early_stop`, `monitor_interval`, `monitor_soft_floor`) are reward-tune's own logic, so their
defaults always apply.

| Arg | Default | Effect |
|---|---|---|
| `algorithm` | `ppo` | Picks `harbor/configs/rl/<algo>.parallel.yaml`. |
| `wandb` | `reward-tune-<task>` | W&B project; run names `iter_000`, … |
| `mode` | `local` | `local` (bg bash) or `cluster` (SLURM). |
| `pool_size` | `1` | Candidates in flight (`1` = serial). |
| `on_success` | `cancel` | First convergence: `cancel` or `drain` in-flight. |
| `success_threshold` | `0.5` | Stop when `success_rate ≥` this. |
| `timesteps_per_iter` | config | Per-candidate budget; unset → config default. |
| `seed` | config | Unset → config default (random). |
| `n_frames` | `12` | Frames read per render. |
| `prompt_every_n_stuck` | `5` | Prompt after N non-improving completions. |
| `monitor_early_stop` | `false` | Default `false` = train every candidate to full budget. `true` opts in to the mid-run 5-min curve monitor that confidently early-stops a doomed candidate (NaN / dead policy immediately; flat/declining/diverged only past the soft-floor AND persistent). |
| `monitor_interval` | `300` | Seconds between monitor ticks (5 min). |
| `monitor_soft_floor` | `0.5` | Budget fraction below which soft bad patterns are only watched, never killed; hard fails ignore it. |
| `spec_section` | (none) | §6 code block (reproduce mode); seeds iter 0 verbatim. |

## Step 0 — Pre-flight

```bash
cd "$(pwd)"
test -x .venv/bin/python                                  || exit 1
test -f harbor/benchmark-generator/benchmark-spec.json    || exit 1
test -f harbor/rl-integration-generator/rl-suite-spec.json || exit 1
test -f harbor/create-task/task-implementation.md         || exit 1
.venv/bin/python -c "import gymnasium as gym; gym.make('<task>'); print('build ok')" || exit 1
command -v ffmpeg >/dev/null                               || exit 1
[ "<mode>" = cluster ] && { command -v sbatch >/dev/null || exit 1; }
grep -q "machine api.wandb.ai" ~/.netrc                   || { echo "run /harbor:wandb-setup"; exit 1; }
```

Resolve `task_dir = harbor/create-task/<slug>` (must already exist from `/harbor:task-create` or a prior
tune). Per-term reward logging is the `reward-tuning-agent`'s STEP 0 (it runs the `/harbor:reward-add-log`
flow itself if `info["detailed_reward"]` is missing) — the orchestrator only needs the pre-flight above.

## Step 1 — Initialize tune state + (standalone) pick the base

Do NOT hand-author `tune-state.json` in full — the agent owns it (creates on first run, resumes if
present). The orchestrator's only Step-1 job is to select the **design base** in the standalone case:

- **Standalone** (`/harbor:reward-tune` typed directly, no `spec_section`): run
  `${CLAUDE_PLUGIN_ROOT}/references/task-library-search.md` once and pass the result as `library_refs`
  to the agent. (Empty library → `library_refs=[]`, pure creation.)
- **Reproduce** (`spec_section` given): skip the search — the spec IS the base; pass `library_refs=[]`.
- **Called from `/harbor:task-create`** (which already ran task-library-search at its Step 1.5): forward the
  caller's `library_refs` unchanged; do NOT re-search.

## Step 2 — Dispatch the reward-tuning-agent (it owns the loop)

```
Agent(reward-tuning-agent, prompt={
  repo_path:          "<abs>",
  task:               "<task>",
  task_dir:           "<task_dir>",
  description:        "<from spec.json — the behavior to match>",
  algorithm, wandb, mode, pool_size, on_success, success_threshold,
  timesteps_per_iter, seed, n_frames, prompt_every_n_stuck,   # forward only the ones the user set
  monitor_early_stop, monitor_interval, monitor_soft_floor,   # monitor: forward only if user set; else defaults
  library_refs:       [<Step 1 base(s)>],
  spec_section:       "<§6 Code block>"                        # reproduce mode only — seeds iter 0 verbatim
})
```

The agent runs the full DESIGN → IMPLEMENT → train+render → SCORE async pool: it decides each candidate's
complete B1-strict reward spec, writes it into IsaacLab code (on a slot clone at `pool_size>1`, on the
source directly at `pool_size=1`), runs the S6 smoke, launches the compute-side train+render with the
completion-detection watchdog, scores per-term curves + rendered frames → `success_rate`, checkpoints
`tune-state.json` every iteration, handles the stuck-prompt via `AskUserQuestion`, and loops until
convergence (then cancels/drains in-flight). Cloning is `scripts/task-cloner/clone_task.py`; there is no
nested dispatch. It returns `{status, best_iter, best_success_rate, best_total_return, iters}`.

## Step 3 — Persist the outcome

From the agent's returned verdict:
- Confirm `tune-state.json:status` + `finished_at` are set and `reward-history.md` has its "Final summary"
  block (the agent writes both; the orchestrator does not duplicate them).
- Print:
  ```
  reward-tune : <task>  (status: converged|aborted)
  iters       : <N>  best=<best_iter>  best_success=<v>  best_total=<v>
  pool / mode : <pool_size> / <mode>
  task_dir    : <task_dir>
  history     : <task_dir>/reward-history.md
  best reward : <task_dir>/handoff-reward-generator.md
  ```

## Constraints

- **The orchestrator makes NO reward-design decisions.** All design + implement + score live in the
  `reward-tuning-agent`; the main agent only does pre-flight, base selection (standalone), dispatch, and
  final persistence.
- **Isolation matches the pool** (agent-enforced): `pool_size=1` edits the SOURCE directly (no clone, no
  cleanup); `pool_size>1` gives each slot its own clone via `clone_task.py` and never edits the source.
  Raise `pool_size` above 1 only once clone independence (SC2) is trusted.
- **Train at default num_envs**; **render is folded into the train job** (compute-side, login-node-safe).
- **No hard cap.** Stop on `success_rate ≥ threshold` or user abort; the agent prompts every
  `prompt_every_n_stuck` non-improving completions.
- **Single source of truth per file** (all agent-owned): `reward-history.md` (cumulative, "## Iter N"),
  `handoff-reward-generator.md` (latest best), `memories.jsonl` (findings), `tune-state.json` (metadata +
  pool + in_flight + per-iter).

## Examples

```text
# Serial (pool_size=1) — the default
/harbor:reward-tune task=Triton-Franka-StackCup wandb=Isaac_exp

# Parallel pool of 4 on the cluster — 4 candidates always in flight, each on its own slot clone
/harbor:reward-tune task=Triton-Franka-StackCup pool_size=4 mode=cluster

# Tighter threshold; let in-flight candidates drain on first success
/harbor:reward-tune task=Triton-Franka-StackCup success_threshold=0.8 on_success=drain

# Resume (tune-state.json present)
/harbor:reward-tune task=Triton-Franka-StackCup
```

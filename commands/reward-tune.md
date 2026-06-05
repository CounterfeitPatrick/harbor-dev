---
description: Iteratively tune the reward function (§6) for an EXISTING task. Per iteration the reward-generator agent authors / edits the reward (and may surgically edit §1–§5 if needed), the orchestrator trains a policy via the rendered train.py at the algorithm's default num_envs (e.g. 2048 for PPO), renders a rollout to MP4, then analyzes per-term reward log + visual frames against the task description. Findings accumulate across iterations. Loops UNTIL `success_rate ≥ 0.5` (or user interrupts) — no hard cap. All artifacts live under `<repo>/harbor/create-task/<task_slug>/` next to task-generator's outputs (no separate tune dir). Use when the user types /harbor:reward-tune task=<id> [algorithm=<algo>] [wandb=<project>] [mode=local|cluster] [success_threshold=0.5] [timesteps_per_iter=N], or asks "tune the reward for task X", "iterate on the reward and verify with training".
argument-hint: task=<id> [algorithm=<ppo|sac|td3>] [wandb=<project>] [mode=local|cluster] [success_threshold=0.5] [timesteps_per_iter=N] [seed=N]
---

# /harbor:reward-tune — Iterative Reward Tuning, Co-located Under `create-task/<slug>/`

Per iteration the orchestrator runs the loop:

```
LOOP iter (no hard cap):
    1. AUTHOR  → reward-generator subagent (sees prior iter findings + handoff)
    2. TRAIN   → train.py at the algorithm's DEFAULT num_envs (PPO: 2048)
    3. RENDER  → render.py → MP4 stored under <task_dir>/iter_<NNN>/render.mp4
    4. ANALYZE → metrics.jsonl + frames extracted from MP4 + task-description match
    5. DECIDE  → success_rate ≥ threshold ? STOP : continue
```

## File layout (single root: `create-task/<slug>/`)

The principle: **one source of truth per kind of information, no per-iter duplication of reward-history / handoff**.

```
<repo>/harbor/create-task/<task_slug>/
├── spec.json                          # create-task/task-generator metadata (existing)
├── task-history.md                    # task-generator's verbose log (existing)
├── reward-history.md                  # SHARED reward-tune log; new "## Iter <N>" section appended each iter
├── handoff-reward-generator.md        # LATEST reward state — overwritten each iter
├── memories.jsonl                     # Cumulative findings across iters (JSONL; the agent prompt's recent_findings)
├── tune-state.json                    # Tune state + per-iter summary in one JSON
├── smokes/
│   ├── smoke_s{1..5}.py              # task-generator's
│   ├── smoke_success.py
│   └── smoke_s6.py                   # reward-generator's (overwritten each iter to reflect current §6)
└── iter_<NNN>/                        # ONLY per-iter artifacts that genuinely don't merge
    ├── train.log
    ├── render.log
    ├── render.mp4
    ├── trial_dir.txt                  # path to harbor/outputs/...
    └── analysis.md                    # per-iter post-train numerical + visual analysis
```

There is **NO** separate `harbor/reward-tunes/<tune_id>/` directory. Tune state goes into `tune-state.json` next to spec.json.

There is **NO** per-iter `reward-history.md` / `handoff-reward-generator.md` / `lookup.md`. Iter sections within the SHARED reward-history.md are separated by `## Iter <N>` headings; the handoff is overwritten in place per iter.

## Required arguments

| Arg | Notes |
|---|---|
| `task` | Task ID. Must exist in the repo and `gym.make(<task>)` must succeed. The task's §6 may currently be a placeholder or a real reward — both are valid starting points. |

## Optional arguments

| Arg | Default | Effect |
|---|---|---|
| `algorithm` | `ppo` | Picks `harbor/configs/rl/<algo>.parallel.yaml`. |
| `wandb` | `reward-tune-<task>` | W&B project. Run names: `iter_000`, `iter_001`, ... |
| `mode` | `local` | `local` (sequential subprocess) or `cluster` (SLURM — not yet implemented; falls back to local). |
| `success_threshold` | `0.5` | Stop when `eval/success_rate` (or terminal-success-term mean) reaches this. |
| `timesteps_per_iter` | `20_000_000` | Per-iter training budget. |
| `seed` | `42` | Per-iter RNG. |
| `n_frames` | `12` | Frames extracted from render.mp4 for behavior analysis. |
| `prompt_every_n_stuck` | `5` | After N consecutive non-improving iters, prompt the user for direction (continue / abort / change strategy). Removes the need for a hard cap while still bounding runaway loops. |

## Action

### Step 0 — Pre-flight

```bash
cd "$(pwd)"
test -x .venv/bin/python                                                || exit 1
test -f harbor/benchmark-generator/benchmark-spec.json                                    || exit 1
test -f harbor/rl-integration-generator/rl-suite-spec.json                                     || exit 1
test -f harbor/create-task/task-implementation.md                   || exit 1
.venv/bin/python -c "import gymnasium as gym; gym.make('<task>'); print('build ok')" || exit 1
command -v ffmpeg >/dev/null                                            || exit 1
```

Resolve `task_dir = harbor/create-task/<slug>` (slug derived from task name). The dir MUST already exist (`create-task` or earlier `tune-reward` runs have used it).

If `mode=cluster`, log "cluster not implemented; using local" and continue.

### Step 1 — Initialize / resume tune state

If `<task_dir>/tune-state.json` exists, RESUME:
- `current_iter = state.iters[-1].iter + 1` (or 0 if list empty)
- `best_iter`, `consecutive_non_improving` carry over

Else CREATE:
```json
{
  "schema_version": 1,
  "task_id": "<task>",
  "algorithm": "<algo>",
  "wandb_project": "<wandb>",
  "mode": "local",
  "success_threshold": 0.5,
  "timesteps_per_iter": <N>,
  "seed": <N>,
  "started_at": "<iso8601>",
  "current_iter": 0,
  "best_iter": null,
  "best_total_reward": null,
  "best_success_rate": null,
  "consecutive_non_improving": 0,
  "iters": []
}
```

If `<task_dir>/reward-history.md` does NOT exist, render it from the template (header + empty per-iter sections). If it exists, leave it — iters will append.

If `<task_dir>/memories.jsonl` does NOT exist, `touch` it.

**Task-library search (CREATE branch, once per tune).** Before the first iteration, run the protocol in `${CLAUDE_PLUGIN_ROOT}/references/task-library-search.md`: classify the task's embodiment, grep `experiences/task-library/<folder>/` for the 1–3 most relevant prior specs, and stash their abs paths as `library_refs` in `tune-state.json`. **Adapt-first is binding** (protocol Step 4): when a match exists, iteration 0's reward-generator takes the best match's §6 as the BASE reward and applies the minimal modification for the new task — pure de-novo reward design only when `library_refs = []` (no relevant task in the library). The iter-0 section of `reward-history.md` must open with the **Adaptation delta** block (base spec, kept-as-is, enumerated changes + why); later iterations document their deltas vs the previous iteration. On RESUME, reuse the stored `library_refs` (don't re-search). `library_refs = []` when the library has no match — never block.

### Step 2 — Iteration loop

For `iter` in `current_iter..∞` (no hard cap):

#### 2a. Build sibling-findings injection

```
findings        = read_last_n_lines(<task_dir>/memories.jsonl, n=20)
prior_handoff   = read(<task_dir>/handoff-reward-generator.md)            # may be empty on iter 0
prior_analyses  = [read(<task_dir>/iter_{i:03d}/analysis.md) for i in last_3_iters]
                                                                          # the FULL post-train analysis
                                                                          # (numerical + visual frame reading)
                                                                          # NOT just the distilled findings
```

#### 2b. AUTHOR — dispatch reward-generator

```
mkdir -p <task_dir>/iter_<NNN>/

Agent(reward-generator, prompt={
  repo_path:           "<abs>",
  task_dir:            "<abs>/harbor/create-task/<task_slug>",
  task_id:             "<task>",
  description:         "<from spec.json>",
  iter:                <N>,
  library_refs:        <library_refs from tune-state>,                    # adapt-first BASE for §6 (minimal modification);
                                                                          # binding on iter 0 when non-empty
  recent_findings:     <findings>,                                        # JSONL-derived, distilled
  prior_handoff:       <prior_handoff>,                                   # LATEST reward state (latest iter)
  prior_analyses:      <prior_analyses>,                                  # FULL analysis.md from last 3 iters
  permit_env_edits:    true,

  # Logging contract — STRICT, share files across iters:
  shared_reward_history_path:  "<task_dir>/reward-history.md",   # APPEND a "## Iter <N>" section
  shared_handoff_path:         "<task_dir>/handoff-reward-generator.md",  # OVERWRITE with latest reward state
  shared_smoke_dir:            "<task_dir>/smokes/",             # Render smoke_s6.py here (overwrite)
  per_iter_dir:                "<task_dir>/iter_<NNN>/",         # ONLY for diff/scratch this iter (not handoff)
})
```

The reward-generator agent should:
1. **Lookup phase** (only if `recent_findings` is empty) — scan benchmark for similar tasks, record pointers in `reward-history.md`'s iter section. Subsequent iters skip the lookup.
2. **Findings ingestion** — read `recent_findings` + `prior_handoff` to understand prior state and unsuccessful directions.
3. **Author phase** — edit §6 (and §1–§5 if needed). Append a `## Iter <N>` section to `reward-history.md` with verbose log. Overwrite `handoff-reward-generator.md` with the LATEST reward state (current term list, weights, gates).
4. **Smoke** — render `smokes/smoke_s6.py` (overwriting prior iter's). Run it (must pass before training).
5. Return verdict + `files_modified`.

If `status: fail`, abort the tune and report.

#### 2c. TRAIN — at default num_envs

```bash
slug=$(jq -r '.algorithm_source.slug' harbor/rl-integration-generator/rl-suite-spec.json)
config_name="<algo>.parallel"
out_log="<task_dir>/iter_<NNN>/train.log"

.venv/bin/python -u harbor/scripts/rl/${slug}/train.py \
    --config-name=${config_name} \
    task=<task> \
    seed=<seed> \
    total_timesteps=<timesteps_per_iter> \
    max_step=<timesteps_per_iter> \
    wandb=<wandb_project> \
    > ${out_log} 2>&1
```

**Do NOT pass `num_envs=...`** — let the algorithm config's default apply (PPO parallel = 2048). Smoke tests use 128 envs; training uses the production default.

Wait for completion. After:
```bash
echo "<latest trial dir>" > <task_dir>/iter_<NNN>/trial_dir.txt
```

#### 2d. RENDER — every iter

```bash
trial_dir=$(cat <task_dir>/iter_<NNN>/trial_dir.txt)
.venv/bin/python -u harbor/scripts/rl/${slug}/render.py \
    checkpoint=${trial_dir}/checkpoint.pth \
    task=<task> \
    +gpu_sim=true \
    > <task_dir>/iter_<NNN>/render.log 2>&1

# render.py writes <trial_dir>/render.mp4 by default; copy into the per-iter dir
cp ${trial_dir}/render.mp4 <task_dir>/iter_<NNN>/render.mp4
```

The renderer:

- Uses **stochastic policy** (`sample=True`) so the video shows what the policy is actually exploring, not the near-zero deterministic mean (which leaves under-trained PPO policies with high init entropy producing 301 visually-identical frames).
- Renders **3 envs side-by-side** under one tiled camera (`render_num_envs=3`, capped at 3) — quick visual diversity check across reset configs in one frame.
- Caps `max_steps` at `env.max_episode_length + 1` so it never runs longer than one episode.
- **Hard-exits with `os._exit(0)` the moment the MP4 + contact sheet are on disk.** With Isaac Sim 5.1 + IsaacLab, `sim_app.close()` hangs indefinitely on USD stage detach (see `references/task-generator/isaaclab-code-reference.md` "Shutdown hang trap"). The orchestrator therefore does NOT need a pkill watchdog; the python process exits cleanly the second the artifact lands. If you ever see a render hang anyway (older IsaacLab? script edited?), pkill `-9 -f "render.py|kit/python|kit-app|omni.telemetry"` and the MP4 will already be on disk.

#### 2e. ANALYZE — every iter

**Numerical**:
```python
m = parse_jsonl_tail(f"{trial_dir}/metrics.jsonl", n=200)
final = pick_last_step(m)
per_term = {k: v for k, v in final.items() if k.startswith("reward/") and "/episodic_return_mean" in k}
total = final["reward/total/episodic_return_mean"]
success = final.get("reward/success/episodic_return_mean", 0.0) / SUCCESS_REWARD_WEIGHT
```

`success_rate` is derived as `success_reward_mean / weight_of_success_term` (gives the fraction of episodes that triggered the success termination).

**Visual**:
```bash
mkdir -p <task_dir>/iter_<NNN>/frames
ffmpeg -y -i <task_dir>/iter_<NNN>/render.mp4 \
    -vf "select='not(mod(n\,N))'" -vsync vfr <task_dir>/iter_<NNN>/frames/f%03d.png
```

`Read` each frame, compose a behavior description, write to `iter_<NNN>/analysis.md`.

#### 2f. DECISION — append findings + decide

Append per-iter findings to `<task_dir>/memories.jsonl` (JSONL):
```json
{"iter": <N>, "ts": "<iso>", "type": "...", "finding": "..."}
```

Update `tune-state.json:iters[N]` with iter result.

```python
if success_rate >= success_threshold:
    state.status = "converged"
    break
elif iter_total > best_total or success_rate > best_success:
    state.consecutive_non_improving = 0
    state.best_iter = iter
    # update best_*
else:
    state.consecutive_non_improving += 1
    if state.consecutive_non_improving >= prompt_every_n_stuck:
        choice = ask_user("stuck for N iters — continue / abort / change strategy?")
        if choice == "abort": break
        # else continue
```

### Step 3 — Final summary

When the loop ends (success or user abort):
- Append a "Final summary" block to `reward-history.md` (best iter, what worked, outstanding issues, recommended next direction).
- Update `tune-state.json:status`, `finished_at`.
- Print to user:
  ```
  tune-reward : <task_id>  (status: converged|aborted)
  iters       : <N>  best=<best_iter>  best_total=<v>  best_success=<v>
  task_dir    : <task_dir>
  reward-history (shared): <task_dir>/reward-history.md
  current reward state:    <task_dir>/handoff-reward-generator.md
  per-iter analyses:       <task_dir>/iter_<NNN>/analysis.md
  per-iter videos:         <task_dir>/iter_<NNN>/render.mp4
  ```

## Constraints

- **`reward-generator` may freely edit §1–§5 in this command's context** (overrides default hard rule). Each cross-section edit is logged in `reward-history.md`.
- **No hard cap on iterations.** Loop terminates on `success_rate >= success_threshold` or user abort. After every `prompt_every_n_stuck` non-improving iters, prompt the user.
- **Train at default num_envs** (e.g. 2048 for PPO parallel). Don't pass `num_envs=...` overrides. Only smoke tests use 128 envs.
- **Render every iter.** No skipping.
- **Single source of truth per file**: `reward-history.md` (cumulative, sectioned), `handoff-reward-generator.md` (latest state, overwritten), `memories.jsonl` (cumulative findings), `tune-state.json` (tune metadata + per-iter summaries). No duplicates between iters.

## Examples

```text
# Default — Triton-Franka-StackCup, ppo at 2048 envs, runs until success_rate>=0.5
/harbor:reward-tune task=Triton-Franka-StackCup wandb=Isaac_exp

# Tighter convergence threshold
/harbor:reward-tune task=Triton-Franka-StackCup success_threshold=0.8

# Faster iteration (5M steps each)
/harbor:reward-tune task=Triton-Franka-StackCup timesteps_per_iter=5000000

# Resume an existing tune (state.json present in task_dir)
/harbor:reward-tune task=Triton-Franka-StackCup        # auto-resumes
```

---
description: Iteratively tune the §6 reward of an EXISTING task with an ASYNC fixed-pool controller. The MAIN AGENT decides each candidate's full reward spec (B1); a reward-generator subagent IMPLEMENTS it on an isolated task clone; the orchestrator trains + renders it (compute-side); a reward-analyzer subagent scores it (per-term curves + rendered frames → success_rate) and returns to the main agent, which decides the next candidate against all completed results AND the designs still in flight. Pool stays at `pool_size` candidates (default 1 = serial; >1 runs candidates in parallel, each on its own clone). Loops until `success_rate ≥ success_threshold` — then cancels any in-flight candidates. Both local and cluster modes use the same submit/score skeleton as /harbor:rl-tune. Use when the user types /harbor:reward-tune task=<id> [algorithm=<algo>] [pool_size=N] [mode=local|cluster], or asks "tune the reward for task X".
argument-hint: task=<id> [algorithm=<ppo|sac|td3>] [wandb=<project>] [mode=local|cluster] [pool_size=N] [success_threshold=0.5] [timesteps_per_iter=N] [seed=N]
---

# /harbor:reward-tune — Async-Pool Reward Tuning

The main agent is the controller. It decides each candidate's **complete** reward spec (B1), then drives the same `submit → WAIT → score` skeleton as `/harbor:rl-tune`, with one extra step — each candidate trains on its own **task clone** so parallel candidates never collide editing the same source.

```
DECIDE   (main agent, B1)  → next full reward spec, distinct from completed + in-flight designs
CLONE    (task-cloner)     → pool_size>1 ONLY: isolated <task>-rewarditer<NNN> via /harbor:task-clone
                             (pool_size=1 serial fast-path: SKIP — edit the source task directly)
SUBMIT   (reward-generator)→ IMPLEMENT the spec on the clone (or the source at pool_size=1),
                             run S6 smoke, write run.sh/launch.sh (no train)
WAIT     (orchestrator)    → train.py && render.py on the COMPUTE side; .done signal
SCORE    (reward-analyzer) → per-term curves + frames → success_rate; return distilled result
CLEANUP  (orchestrator)    → pool_size>1 ONLY: /harbor:task-clone op=delete
```

**Async fixed-pool.** Keep `pool_size` candidates in flight. On each candidate's `.done`, score it, free its slot, and refill with a new candidate. `pool_size=1` degenerates exactly to a serial loop. There are NO generations — every DECIDE sees the freshest completed history plus the designs of whatever is still running.

## File layout (`create-task/<slug>/`)

```
<repo>/harbor/create-task/<task_slug>/
├── spec.json / task-history.md                 # from /harbor:task-create (if present)
├── tune-state.json                             # tune metadata + pool + in_flight + per-iter summary
├── reward-history.md                           # SHARED; "## Iter <N>" appended per candidate
├── handoff-reward-generator.md                 # latest BEST reward state (overwritten on new best)
├── memories.jsonl                              # cumulative findings (cross-candidate channel)
├── smokes/smoke_s6.py                          # reward-generator's (overwritten per candidate)
└── iter_<NNN>/                                  # one per candidate (NNN = global candidate index)
    ├── design.json                             # the B1 spec the main agent decided
    ├── clone-info.json                         # task-cloner manifest (for cleanup)
    ├── run.sh | launch.sh                       # orchestrator launches
    ├── run.log | slurm-*.out                    # orchestrator captures
    ├── render.mp4 ; frames/                      # the rollout + extracted frames
    ├── analysis.md                              # reward-analyzer's output
    └── .done                                    # orchestrator's completion signal
```

A "candidate" and an "iteration" are the same thing — `iter_<NNN>` uses a global monotonic index.

## Required arguments

| Arg | Notes |
|---|---|
| `task` | Task ID. `gym.make(<task>)` must succeed. Its §6 may be a placeholder or a real reward. |

## Optional arguments

**Rule: if an arg isn't passed, don't override the config — leave its default untouched.** Only build a train-command override (`seed=`, `total_timesteps=`, …) for args the user explicitly set. The loop-control args below (`pool_size`, `on_success`, `success_threshold`, `n_frames`, `prompt_every_n_stuck`) are reward-tune's own logic, not rl-config keys, so their defaults always apply.

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

Resolve `task_dir = harbor/create-task/<slug>` (must already exist from `/harbor:task-create` or a prior tune).

**Per-term reward logging MUST be wired on the SOURCE task before iter 0** (clones inherit it). The score phase parses `reward/<term>/...` keys; without `info["detailed_reward"]` the loop is blind. If the env factory doesn't expose `detailed_reward` (Path A: `scripts/_<family>_env.py` lacks the wrapper; Path B IsaacLab: `_isaaclab_env.py` not delegating), run the `/harbor:reward-add-log` flow first (incl. its composer sanity check), then start the loop.

## Step 1 — Initialize / resume tune state

If `<task_dir>/tune-state.json` exists, RESUME (carry `best_iter`, `consecutive_non_improving`, `next_iter`, drop any stale `in_flight` whose `.done` is already present). Else CREATE:

```json
{
  "schema_version": 2,
  "task_id": "<task>", "algorithm": "<algo>", "wandb_project": "<wandb>",
  "mode": "local|cluster", "pool_size": <N>, "on_success": "cancel|drain",
  "success_threshold": 0.5, "timesteps_per_iter": <N>, "seed": <N>,
  "started_at": "<iso8601>", "next_iter": 0,
  "best_iter": null, "best_success_rate": null, "best_total_return": null,
  "consecutive_non_improving": 0,
  "in_flight": [],
  "iters": []
}
```

`in_flight[]` entries: `{slot, iter, dest_task, design_summary, jobid?}` — the **design_summary is what makes DECIDE in-flight-aware** (the main agent diversifies away from running candidates).

Render `reward-history.md` from the template if absent. `touch memories.jsonl` if absent.

**Task-library search** (skip when `spec_section` is given — the spec IS the base; set `library_refs=[]`, `seeded_from_spec: true`). Otherwise run `${CLAUDE_PLUGIN_ROOT}/references/task-library-search.md` once, stash `library_refs` in tune-state. The main agent (not the subagent) owns the adapt-first base under B1.

## Step 2 — Async-pool controller

### 2.0 — INITIAL FILL (with reproduce ramp)

- **Normal / library-adapt mode:** launch `pool_size` candidates. The main agent picks `pool_size` **diverse** initial designs. For each slot, run DECIDE → CLONE → SUBMIT → LAUNCH and append to `in_flight[]`.
- **Reproduce mode (`spec_section` given) — ramp from 1:** the spec is a PROVEN reward (it worked in the source repo), so don't pay for breadth up front. Launch only **one** candidate at iter 0 — the verbatim spec (`reward_spec.kind=verbatim`). If it converges, you're done in one training. **Only if iter 0 fails to converge** does the controller ramp the pool up to the configured `pool_size` and fan out structured adaptations from the verbatim baseline. So `pool_size` is the *target/cap*, reached lazily — exploit the confident seed first, explore only on failure.

### 2.1 — DECIDE (main agent, B1-strict)

The main agent owns ALL reward design. It reads the completed `iters[]` analyses (`iter_<i>/analysis.md` — the FULL per-term + visual evidence) and the `in_flight[].design_summary` list, then produces the next candidate's **complete, concrete reward spec** and writes it to `iter_<NNN>/design.json` (+ a one-line `design_summary` for `in_flight[]`).

**The spec is B1-strict** — it pins concrete numbers, so reward-generator writes them verbatim with zero design freedom:

```json
{
  "kind": "structured",                  // "verbatim" only for reproduce iter 0
  "composer": "sum|product",
  "success_term": "<name of the term whose firing = task success — reward-analyzer reads this>",
  "terms": [{"name": "...", "weight": <concrete float>, "shape": "<fn + params>", "gate": "<predicate|null>"}],
  "budget_rationale": "<per-stage saturated per-step targets the weights realize>",
  "env_changes": ["<any §1–§5 field the spec requires, e.g. add contact sensor>"]
}
```

Design rules the main agent applies (these MOVED here from reward-generator):
- **Nominal weights.** Every `weight` in the spec is the term's NOMINAL per-step magnitude, applied directly — a `+200` one-shot latch reads `200`. Plan the magnitude budget in these units; the declared weight is exactly what the term pays per step.
- **Adapt-first** — follow `${CLAUDE_PLUGIN_ROOT}/references/adapt-first.md`: when `library_refs` has a match (selected via `task-library-search.md`), its §6 is the BASE; design by minimal modification, keeping the proven term ladder / weights / composer / gating. **All task-library reference specs declare NOMINAL weights — carry them over as-is; the declared weight is what each term pays per step.** Pure de-novo only when `library_refs=[]`. Open iter 0's `reward-history.md` with the **Adaptation delta** (base, kept-as-is, per-change reason).
- **Magnitude budget** — plan per-stage saturated per-step values FIRST (earlier stages small, later stages larger, sparse bonuses an order above the dense sum), then back-compute each concrete `weight = target / per_step_saturation`. Regularizers `|weight| ≤ 0.1`. Record the budget in `budget_rationale`. (When adapting a library base, keep its proven budget — don't re-plan.)
- **Heuristics** — consult `${CLAUDE_PLUGIN_ROOT}/experiences/reward-generator/reward-experience.md` (staging, gating, scale ratios). Subordinate to a matched library base.
- **Conventions** — composer-by-family + weight scales from `${CLAUDE_PLUGIN_ROOT}/references/reward-generator/isaaclab-reward-reference.md` (the *conventions*; the *code idioms* in that file are reward-generator's concern).
- **Distinctness** — the new spec must differ from the best completed design AND every in-flight `design_summary` (don't burn a slot re-running what's already cooking).
- **Reproduce iter 0** — `kind=verbatim`, `body` = the `spec_section` §6 Code block, no design.

### 2.2 — CLONE (SKIPPED at `pool_size=1` — serial fast-path)

**Serial fast-path (`pool_size=1`, the default):** do NOT clone. With one candidate in flight there is nothing to isolate from — cloning only spends a task-cloner run + clone smokes per iteration. Instead:

- SUBMIT (2.3) targets the **SOURCE task directly**: `task_id = <task>`, `reward_path = <source task's mdp/rewards.py>`; the train command uses `task=<task>` (run names `iter_<NNN>` keep W&B trials distinct).
- Each iteration edits the source's §6 in place as a minimal diff from the previous iteration (the prior candidate's code is already there — no re-derivation, no `impl_snapshot` needed).
- CLEANUP (2.6) is skipped too. On convergence the source already carries the winning reward — no apply-back step.
- **If the loop ends NOT on the best iter** (abort, or best < last), re-implement `handoff-reward-generator.md` (latest BEST state) on the source before the final summary, so the source never ends carrying a worse-than-best candidate.
- `in_flight[].dest_task = <task>` (the source id) for bookkeeping.

**Pooled mode (`pool_size>1`) — clone per candidate:**

```
/harbor:task-clone op=create source=<task> dest=<task with -rewarditer<NNN> before -vN> \
    info_out=<task_dir>/iter_<NNN>/clone-info.json
```
Cloning is serialized here (one at a time) even when trainings run in parallel. On clone fail: skip this slot, log it, count it as a completion toward `prompt_every_n_stuck`.

**Hard check — `per_term_logging` (pooled mode only).** Step 0 guaranteed the SOURCE is wired, so clones must inherit it. If `task-cloner` returns `per_term_logging: no`, first check the smoke's methodology: a plain `gym.make` build bypasses the repo-wide factory wrapper (e.g. IsaacLab's `scripts/_isaaclab_env.py`) and reads "no" even when training-path logging is fine — only abort when the FACTORY-built env lacks `info["detailed_reward"]` (a real clone bug), with a remediation pointer rather than wasting a training run that scores blind. (The clone smoke itself keeps this soft, because `/harbor:task-clone` is also a standalone primitive for tasks that were never wired.)

### 2.3 — SUBMIT (reward-generator, IMPLEMENT mode)

```
Agent(reward-generator, prompt={
  repo_path:        "<abs>",
  task_dir:         "<task_dir>",
  task_id:          "<dest clone id>",            # edits the CLONE, not the source
  reward_path:      "<clone-info.reward_path>",
  reward_spec:      {kind, body},                 # {kind:"verbatim", body:<spec_section>} at reproduce iter 0,
                                                  # else {kind:"structured", body:<design.json>}. Implement-only.
  permit_env_edits: true,
  iter:             <NNN>,
  shared_reward_history_path: "<task_dir>/reward-history.md",   # append "## Iter <N>"
  shared_handoff_path:        "<task_dir>/handoff-reward-generator.md",
  shared_smoke_dir:           "<task_dir>/smokes/",
  per_iter_dir:               "<task_dir>/iter_<NNN>/",
})
```
The agent implements `reward_spec` on the clone, runs `smoke_s6.py`, and writes `iter_<NNN>/run.sh` (local) or `iter_<NNN>/launch.sh` (cluster) — a script that runs `train.py … && render.py …`. It does NOT train. On `status: fail`, treat as a failed completion (skip to refill).

The train+render command the script wraps:
```bash
slug=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/common/resolve_suite.py" --field slug)
# Build the override list from ONLY the args the user passed (per the Rule above);
# bracketed tokens are included only when that arg was set — otherwise the config default applies.
.venv/bin/python -u harbor/scripts/rl/${slug}/train.py --config-name=<algo>.parallel \
    task=<dest> [seed=<seed>] [total_timesteps=<timesteps_per_iter> max_step=<timesteps_per_iter>] \
    wandb=<wandb> wandb_run_name=iter_<NNN>
trial=<resolved latest trial dir>; echo "$trial" > iter_<NNN>/trial_dir.txt
.venv/bin/python -u harbor/scripts/rl/${slug}/render.py checkpoint=$trial/checkpoint.pth task=<dest> +gpu_sim=true
cp $trial/render.mp4 iter_<NNN>/render.mp4
```
Do NOT pass `num_envs=` — use the config default.

**[MUST] Completion-detection watchdog — NEVER wait for the trainer's natural exit.** Known bug (recurred 2/2 iterations on IsaacLab, 2026-07-05): GPU-sim trainers can complete training — final checkpoint saved, all output flushed — and then hang forever in simulator teardown (Isaac Sim Kit shutdown spins at 100% CPU; iter 0 lost ~3 h to this). Success is therefore signalled by the SENTINEL, not the exit code. run.sh must:
1. Launch train.py in the background (`train_pid=$!`) and poll (~15 s) for the completion sentinel: the final `checkpoint.pth` exists / the "saved checkpoint" log line appears. Also bail out if the process dies without the sentinel (real crash → exit 1).
2. On sentinel: give the process a SHORT grace (≤60 s) to exit on its own, then `kill -TERM` (escalate to `-KILL` after 30 s) and PROCEED immediately. A killed-after-sentinel trainer is a SUCCESS, not a failure — gate solely on the checkpoint artifact.
3. Wrap render.py the same way (sentinel = `render.mp4` written / the `[render] wrote` line) — it boots the same simulator and can hang the same way after finishing.
4. Reap any orphaned children (`pkill -P`) before exiting so no simulator process outlives the job.

### 2.4 — WAIT (orchestrator-owned; agent never blocks)

- **local:** `Bash(run_in_background=true, "bash iter_<NNN>/run.sh > iter_<NNN>/run.log 2>&1 && touch iter_<NNN>/.done")`. Local trains run sequentially (GPU-bound) even at `pool_size>1` — the pool structure is identical, throughput is bounded by GPUs.
- **cluster:** SUBMIT's `launch.sh` carries SBATCH directives and runs `train && render` on the compute node; the agent `sbatch`-es it and records `jobid`. Then `Bash(run_in_background=true, "while squeue -h -j $JOBID | grep -q .; do sleep 600; done; touch iter_<NNN>/.done")`. Cluster candidates run in parallel.

Render is **folded into the job** so it runs where the GPU is — the orchestrator never renders on a login node. Do NOT poll; the harness notifies on `.done`.

### 2.5 — SCORE (reward-analyzer) + render fallback

On a slot's `.done`: ensure the video exists, then score.

```
# render fallback (only if the job's render tail failed or on resume):
if [ ! -f iter_<NNN>/render.mp4 ]; then
  if mode==local:   run render.py locally, cp to iter_<NNN>/render.mp4
  if mode==cluster: sbatch a render-only job, wait, then continue   # never render on login node
fi
```
```
Agent(reward-analyzer, prompt={
  repo_path, task_dir, iter_dir=<task_dir>/iter_<NNN>, task_id=<dest>,
  trial_dir=<from trial_dir.txt>, description=<from spec.json>, n_frames=<n_frames>
})
```
The analyzer is self-contained: it reads `<iter_dir>/design.json` for the `success_term` + weight, parses the per-term curves, reads the rendered frames vs `description`, writes `analysis.md`, and returns `success_rate`, `total_return`, `per_term`, `behavior`, `findings`. Append `findings` to `memories.jsonl`. Update `tune-state.json:iters[NNN]`. Remove this iter from `in_flight[]`.

### 2.6 — CLEANUP (SKIPPED at `pool_size=1` — nothing was cloned)

```
/harbor:task-clone op=delete dest=<dest> info_out=<task_dir>/iter_<NNN>/clone-info.json
```
Delete the clone's SOURCE (the trial outputs + render.mp4 live under `harbor/outputs/` and `iter_<NNN>/` — they survive). Run cleanup on success AND failure — no orphan clones.

### 2.7 — DECISION + refill

```python
if success_rate >= success_threshold:
    state.status = "converged"; state.best_iter = NNN
    if on_success == "cancel":
        for f in in_flight: scancel(f.jobid) or kill its bg train; cleanup f's clone
    else:  # drain
        keep waiting on remaining in_flight, then stop
    break
elif success_rate > best_success_rate or total_return > best_total_return:
    state.consecutive_non_improving = 0; update best_*; overwrite handoff with this reward state
else:
    state.consecutive_non_improving += 1
    if state.consecutive_non_improving >= prompt_every_n_stuck:
        choice = ask_user("stuck N completions — continue / abort / change strategy?")
        if choice == "abort": break

# refill the freed slot (unless converged/aborted):
DECIDE → CLONE → SUBMIT → LAUNCH into the slot; append to in_flight
```

The main agent processes one `.done` per turn, so `in_flight` reads/writes are naturally serialized — no locking. At `pool_size>1` the orchestrator holds multiple background WAITs at once and refills each slot independently as its notification fires.

**Reproduce ramp.** In reproduce mode the pool started at 1 (§2.0). If iter 0 (the verbatim spec) does NOT converge, ramp the effective pool target to the configured `pool_size`: on this `.done`, refill not one but up to `pool_size` slots with distinct **structured** adaptations from the verbatim baseline, and proceed as the normal async pool thereafter. If iter 0 converged, the ramp never fires.

## Step 3 — Final summary

When the loop ends (converged / aborted):
- Append a "Final summary" block to `reward-history.md` (best iter, what worked, outstanding issues, next direction).
- Set `tune-state.json:status`, `finished_at`.
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

- **Main agent owns ALL design (B1-strict); reward-generator only implements.** Adapt-first / task-library search, magnitude-budget planning, concrete weights, composer choice, and reproduce-verbatim decisions all live HERE. The spec pins concrete numbers; the subagent translates it to IsaacLab code on the clone and smokes it, with zero freedom to reweight / re-gate / re-compose. A reward-generator `status: fail` means an IMPLEMENTATION gap (or a spec defect it surfaced) — the main agent decides any design change.
- **DECIDE is in-flight-aware.** Every new candidate must be distinct from the best completed design AND every `in_flight[].design_summary`. This is the only coordination cost of `pool_size>1`.
- **Isolation matches the pool.** At `pool_size=1` (serial, the default) candidates edit the SOURCE task directly — no task-cloner, no cleanup (see 2.2 serial fast-path); the only invariant is that the loop must not END with a worse-than-best reward on the source. At `pool_size>1` each candidate trains on its own clone: never edit the source task's reward in pooled mode — only clones — and cleanup deletes the clone on success and failure.
- **`pool_size>1` requires clone isolation proven.** Raise it above 1 only after the clone's independence check (SC2) is trusted.
- **Train at default num_envs** (e.g. 2048 for PPO). Smoke uses fewer; training uses the production default.
- **Render is folded into the train job** (compute-side); the orchestrator only renders as a fallback, and on cluster only via a render-only job — never inline on the login node.
- **No hard cap.** Stop on `success_rate ≥ threshold` or user abort; prompt every `prompt_every_n_stuck` non-improving completions.
- **Single source of truth per file**: `reward-history.md` (cumulative, "## Iter N"), `handoff-reward-generator.md` (latest best), `memories.jsonl` (findings), `tune-state.json` (metadata + pool + in_flight + per-iter).

## Examples

```text
# Serial (pool_size=1) — identical behavior to the classic loop, new skeleton
/harbor:reward-tune task=Triton-Franka-StackCup wandb=Isaac_exp

# Parallel pool of 4 on the cluster — 4 candidates always in flight, each on its own clone
/harbor:reward-tune task=Triton-Franka-StackCup pool_size=4 mode=cluster

# Tighter threshold; let in-flight candidates drain on first success
/harbor:reward-tune task=Triton-Franka-StackCup success_threshold=0.8 on_success=drain

# Resume (tune-state.json present)
/harbor:reward-tune task=Triton-Franka-StackCup
```

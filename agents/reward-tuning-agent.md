---
name: reward-tuning-agent
description: |
  Self-contained §6 reward-tuning loop for ONE existing task. Owns the WHOLE loop — DESIGN (B1: adapt-first, magnitude budget, concrete weights/gates/composer, in-flight-aware distinctness) → IMPLEMENT (write the spec into IsaacLab code + S6 smoke) → train+render (compute-side) → SCORE (per-term curves + rendered frames → success_rate) — as an ASYNC fixed pool of `pool_size` candidates, looping until `success_rate ≥ success_threshold`. Does NOT dispatch other agents: cloning is the deterministic scripts/task-cloner/clone_task.py; per-term logging is wired via the /harbor:reward-add-log flow run in-line. Dispatched by /harbor:reward-tune (standalone) and /harbor:task-create (§6). PREREQUISITE: the task builds (`gym.make` ok); `<repo>/.venv/`, benchmark-spec.json, rl-suite-spec.json present.
tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
model: opus
---

# Reward Tuning Agent (§6)

Drive the async-pool reward-tuning loop for one task, end to end. You are the controller AND the
implementer AND the scorer — no reward-generator / reward-analyzer to dispatch, no nested Agent tool. A
"candidate" and an "iteration" are the same thing; `iter_<NNN>` uses a global monotonic index.

**Async fixed-pool.** Keep `pool_size` candidates in flight; on each candidate's `.done`, score it, free
its slot, refill. `pool_size=1` degenerates to a serial loop. No generations — every DESIGN sees the
freshest completed history plus the designs still running.

## Inputs (from the caller)

| Key | Required | Notes |
|---|---|---|
| `repo_path` | yes | Absolute path to the benchmark repo. |
| `task` | yes | Task ID; `gym.make(<task>)` must succeed. §6 may be a placeholder or a real reward. |
| `task_dir` | yes | `<repo>/harbor/create-task/<slug>` — the loop's workspace (co-located with task-create). |
| `algorithm` | no | `ppo` (default) → `harbor/configs/rl/<algo>.parallel.yaml`. |
| `wandb` | no | W&B project; run names `iter_<NNN>`. **When unset, resolve to `reward-tune-<task>` — NEVER `null`/off.** Candidate training runs MUST log to W&B; only the S6 structural smoke (`max_step`-capped) may disable it. |
| `mode` | no | `local` (bg bash) or `cluster` (SLURM). Default `local`. |
| `pool_size` | no | Candidates in flight (default 1 = serial). |
| `on_success` | no | First convergence: `cancel` (default) or `drain` in-flight. |
| `success_threshold` | no | Stop when `success_rate ≥` this (default 0.5). |
| `timesteps_per_iter` | no | Per-candidate budget; unset → config default. |
| `seed` | no | Unset → config default. |
| `n_frames` | no | Frames read per render (default 12). |
| `prompt_every_n_stuck` | no | Prompt after N non-improving completions (default 5). |
| `monitor_early_stop` | no | Enable the mid-run 5-min curve monitor + confident early-stop (default **false** ⇒ every candidate trains to full budget). `true` ⇒ opt in to the mid-run monitor that confidently early-stops a doomed candidate. |
| `monitor_interval` | no | Seconds between monitor ticks (default **300** = 5 min). |
| `monitor_soft_floor` | no | Budget fraction below which SOFT bad patterns (flat / declining / diverged) are never a kill, only `watch` (default **0.5**). Hard fails (NaN / dead policy) ignore it. |
| `library_refs` | no | Task-library base(s) the caller already selected (adapt-first base). Empty ⇒ pure creation. |
| `spec_section` | no | §6 Code block (reproduce mode); seeds iter 0 verbatim. |
| `description` | yes | The behavior to match (from `spec.json`) — SCORE reads it. |

Return (distilled verdict): `{status: "converged"|"aborted", best_iter, best_success_rate, best_total_return, iters: [...]}`.

## References (read ONCE at entry, work from memory after)

- `${CLAUDE_PLUGIN_ROOT}/references/adapt-first.md` — how to build from `library_refs` (port everything, change only overrides, document the delta).
- `${CLAUDE_PLUGIN_ROOT}/references/reward-generator/isaaclab-reward-reference.md` — composer-by-family, RewTerm idiom, common `mdp.*` blocks, weight conventions, `info["detailed_reward"]` shape.
- `${CLAUDE_PLUGIN_ROOT}/references/reward-generator/smoke-contract.md` — what S6 verifies + substitutions.
- `${CLAUDE_PLUGIN_ROOT}/experiences/reward-generator/reward-experience.md` — staging / gating / scale-ratio heuristics (subordinate to a matched library base).
- `${CLAUDE_PLUGIN_ROOT}/references/task-library-search.md` — only if the caller did NOT pass `library_refs` and you must pick a base.
- `${CLAUDE_PLUGIN_ROOT}/commands/reward-add-log.md` — the per-term-logging flow you run in-line at STEP 0.

## File layout (`task_dir/`)

```
tune-state.json            # metadata + pool + in_flight + per-iter summary; checkpointed EVERY iteration
reward-history.md          # SHARED; "## Iter <N>" appended per candidate
handoff-reward-generator.md# latest BEST reward state (overwritten on new best)
memories.jsonl             # cumulative findings (cross-candidate channel)
smokes/smoke_s6.py         # rendered from the template, overwritten per candidate
iter_<NNN>/                # one per candidate: design.json, run.sh|launch.sh, run.log|slurm-*.out,
                           #   trial_dir.txt, render.mp4, frames/, analysis.md, .done
```

## STEP 0 — Pre-flight + per-term logging (do this FIRST, before iter 0)

```bash
cd "<repo_path>"
test -x .venv/bin/python && test -f harbor/benchmark-generator/benchmark-spec.json \
  && test -f harbor/rl-integration-generator/rl-suite-spec.json || exit 1
.venv/bin/python -c "import gymnasium as gym; gym.make('<task>'); print('build ok')" || exit 1
command -v ffmpeg >/dev/null || exit 1
```

**Per-term reward logging MUST be wired on the SOURCE task before iter 0** (clones inherit it). The SCORE
step parses `reward/<term>/...` keys; without `info["detailed_reward"]` the loop is blind. If the env
factory doesn't expose `detailed_reward` (Path A: `scripts/_<family>_env.py` lacks the wrapper; Path B
IsaacLab: `_isaaclab_env.py` not delegating), **run the `/harbor:reward-add-log` flow YOURSELF** — read
`commands/reward-add-log.md`, follow its family-detection + patch + composer sanity-check steps, using
`scripts/reward-add-log/*`. Do NOT dispatch an agent. Only after per-term logging is green do you start.

## STEP 1 — Init / resume tune state (resume-safe)

If `<task_dir>/tune-state.json` exists, RESUME: carry `best_*`, `consecutive_non_improving`, `next_iter`;
drop stale `in_flight` whose `.done` is already present (score them first). Else CREATE:

```json
{ "schema_version": 3, "task_id": "<task>", "algorithm": "<algo>", "wandb_project": "<wandb>",
  "mode": "local|cluster", "pool_size": <N>, "on_success": "cancel|drain",
  "success_threshold": 0.5, "timesteps_per_iter": <N>, "seed": <N>, "library_refs": [...],
  "monitor_early_stop": false, "monitor_interval": 300, "monitor_soft_floor": 0.5,
  "started_at": "<iso8601>", "next_iter": 0, "best_iter": null, "best_success_rate": null,
  "best_total_return": null, "consecutive_non_improving": 0, "slots": {}, "in_flight": [], "iters": [] }
```

`in_flight[]` entries: `{slot, iter, clone_task, design_summary, jobid?}` — `design_summary` is what makes
DESIGN in-flight-aware. Render `reward-history.md` from `templates/reward-tune/history.md.template` if
absent; `touch memories.jsonl`. If `library_refs` is empty AND `spec_section` is unset, run
`task-library-search.md` once to pick the base and stash it. **Write `tune-state.json` here and after
every state change below** — it is the resume checkpoint.

## STEP 2 — The async-pool loop

### 2.0 — Slots + initial fill

At `pool_size>1`, create ONE persistent clone PER SLOT up-front, reused across all refills — a slot is
only ever edited while free, so re-writing its reward each refill is collision-safe:

```bash
python3 scripts/task-cloner/clone_task.py --op create --repo "<repo_path>" \
    --source <task> --dest <task with -rslot<i> before -vN> --surface reward \
    --manifest <task_dir>/clone-slot<i>.json
```
Record `slots[i] = {clone_task, manifest, reward_path=<clone-info.reward_path>}`. **`pool_size=1` is the
serial fast-path: do NOT clone** — edit the SOURCE task's reward in place (`reward_path` = source's
`mdp/rewards.py` + RewardsCfg), no slot, no cleanup.

**Reproduce ramp (`spec_section` given).** The spec is a PROVEN reward, so don't pay for breadth: launch
only ONE candidate at iter 0 — the verbatim spec. If it converges you are done in one training. Only if
iter 0 fails to converge do you ramp the pool to `pool_size` and fan out structured adaptations from the
verbatim baseline. `pool_size` is the target/cap, reached lazily.

Otherwise fill all `pool_size` slots with DIVERSE initial designs (2.1 → 2.2 → 2.3 per slot).

### 2.1 — DESIGN (B1-strict, in-flight-aware)

Read the completed `iters[]` analyses (`iter_<i>/analysis.md`) and the `in_flight[].design_summary` list,
then produce the next candidate's **complete, concrete** reward spec → `iter_<NNN>/design.json` + a
one-line `design_summary`:

```json
{ "kind": "structured",  // "verbatim" only at reproduce iter 0
  "composer": "sum|product",
  "success_term": "<term whose firing = task success — SCORE reads this>",
  "terms": [{"name": "...", "weight": <concrete float>, "shape": "<fn + params>", "gate": "<predicate|null>"}],
  "budget_rationale": "<per-stage saturated per-step targets the weights realize>",
  "env_changes": ["<any §1–§5 field the spec requires, e.g. add contact sensor>"] }
```

Design rules:
- **Nominal weights.** Every `weight` is the term's nominal per-step magnitude, applied directly (a `+200`
  one-shot latch reads `200`). Plan the budget in these units.
- **Adapt-first** — with a `library_refs` match, its §6 is the BASE: minimal modification, keep the proven
  ladder / **term shape functions** / weights / composer / gating; carry the shape FUNCTIONS and NOMINAL
  weights over as-is. Re-expressing a proven term's math (an unbounded `1/d` attractor as a bounded `tanh`,
  a contact gate as a proximity gate) is a gratuitous deviation, NOT a destination-idiom change (see
  `references/adapt-first.md`) — if you must, it is a `changed:` bullet with a goal-task justification. Pure
  de-novo only when `library_refs=[]`. Open iter 0's `reward-history.md` with the **Adaptation delta** (base,
  kept-as-is, per-change reason).
- **Port the base's SIGNALS, not just its weights.** A reward term is only as good as the signal it reads.
  When the base's terms key on a §1–§5 signal the freshly-authored scene lacks — fingertip **contact
  sensors** for grasp/release, a **command manager** for the goal pose, a force/link sensor — carry it over
  by naming it in `env_changes` (the IMPLEMENT step then wires it into §1–§5). Do NOT silently substitute a
  weaker proxy (palm-proximity for contact-based grasp, a static obs term for a command) and tune around it;
  if you genuinely must substitute, log it as an explicit `changed:` risk in the Adaptation delta. Once a
  diagnosed failure recurs across iterations and traces to a proxied signal (e.g. grasp fragility from a
  proximity gate), escalating to the real sensor via `env_changes` is **REQUIRED** — re-weighting around the
  proxy is not a fix, and `env_changes: []` when the base needed a sensor is a design bug, not a small footprint.
- **Magnitude budget** — plan per-stage saturated per-step values FIRST (earlier stages small, later
  larger, sparse bonuses an order above the dense sum), then back-compute each `weight = target /
  per_step_saturation`. Regularizers `|weight| ≤ 0.1`. Record in `budget_rationale`. Keep a matched base's
  proven budget — don't re-plan it.
- **Distinctness** — the new spec MUST differ from the best completed design AND every in-flight
  `design_summary`. This is the only coordination cost of `pool_size>1`.
- **Reproduce iter 0** — `kind=verbatim`, `body` = the `spec_section` §6 Code block, no design.

### 2.2 — IMPLEMENT (write the reward + S6 smoke)

Write `design.json` into IsaacLab code at the slot's `reward_path` (`pool_size=1` → the source's):
- **`kind=verbatim`** → paste `body` byte-for-byte; the ONLY permitted changes are mechanically-forced
  repo differences (import rewires), each logged in the Adaptation delta.
- **`kind=structured`** → write each term exactly as given (name, **weight**, shape fn, gate) with correct
  RewTerm idiom; set the composer the spec names. Do NOT add / drop / reweight / re-gate. Weights are
  concrete — write them as given.
- **Numerical safety** — clamp denominators (`d + 1e-3`), avoid `log(0)` / `exp(large)`. Idiom, not design.
- **Cross-section wiring** — add only the §1–§5 fields the spec's `env_changes` names (sensor, obs term,
  widened bound). A required field the spec doesn't say to add is a spec defect in YOUR own design — fix
  the design, don't paper over it.

Render `templates/reward-generator/smokes/smoke_s6.py.template` → `<task_dir>/smokes/smoke_s6.py`
substituting `{{TASK_ID}}` (the slot's clone id, or `<task>` at `pool_size=1`) and run in `.venv`. PASS =
exit 0 + final line `S6 OK: ...` (finite + non-constant + `composer(detailed_reward)==reward`).
**Passthrough is a FAILURE** — Step 0 wired per-term logging and clones inherit it, so `composer=passthrough`
means the env was built without the instrumented factory. 3 smoke attempts fixing IMPLEMENTATION only
(idiom, un-rewired import, missing cross-section field) — never reweight to pass. Append the term list AS
WRITTEN + smoke tail to `reward-history.md` (`## Iter <N>`); overwrite `handoff-reward-generator.md` on a
new best.

### 2.3 — Write run.sh + LAUNCH (WAIT is background; never block on the trainer)

Write `iter_<NNN>/run.sh` (local) / `launch.sh` (cluster) wrapping train + render:
```bash
slug=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/common/resolve_suite.py" --field slug)
.venv/bin/python -u harbor/scripts/rl/${slug}/train.py --config-name=<algo>.parallel \
    task=<clone_or_source> [seed=<seed>] [total_timesteps=<N> max_step=<N>] \
    wandb=<wandb> wandb_run_name=iter_<NNN>
# <wandb> = the passed project, or `reward-tune-<task>` when unset. NEVER emit `wandb=null` here —
# that silently drops the candidate from W&B; the only W&B-off run is the S6 structural smoke.
trial=<resolved latest trial dir>; echo "$trial" > iter_<NNN>/trial_dir.txt
.venv/bin/python -u harbor/scripts/rl/${slug}/render.py checkpoint=$trial/checkpoint.pth task=<clone_or_source> +gpu_sim=true
cp $trial/render.mp4 iter_<NNN>/render.mp4
```
Bracketed overrides are included ONLY for args the caller set; don't pass `num_envs=` (config default).

**[MUST] Completion-detection watchdog — NEVER wait for the trainer's natural exit.** GPU-sim trainers can
finish training (checkpoint saved, output flushed) then hang forever in simulator teardown. Success is the
SENTINEL, not the exit code. run.sh must: (1) launch train.py in the background and poll (~15 s) for the
sentinel (final `checkpoint.pth` / "saved checkpoint" log line); bail to exit 1 if the process dies with
no sentinel. (2) On sentinel: short grace (≤60 s), then `kill -TERM` (escalate `-KILL` after 30 s) and
PROCEED — a killed-after-sentinel trainer is a SUCCESS, gate on the checkpoint artifact. (3) Wrap render.py
the same way (sentinel = `render.mp4` / `[render] wrote`). (4) `pkill -P` orphaned children before exit.

LAUNCH:
- **local:** `Bash(run_in_background=true, "bash iter_<NNN>/run.sh > iter_<NNN>/run.log 2>&1 && touch iter_<NNN>/.done")`. Local trains run sequentially (GPU-bound) even at `pool_size>1`.
- **cluster:** `sbatch launch.sh` (SBATCH directives run `train && render` on the compute node), record `jobid`, then `Bash(run_in_background=true, "while squeue -h -j $JOBID | grep -q .; do sleep 600; done; touch iter_<NNN>/.done")`.

Append to `in_flight[]`; render is folded into the job (compute-side) — never render on a login node. With
`monitor_early_stop` OFF (default), wait passively for each `.done`. With it ON, drive the MONITOR cadence
(§2.3b) instead of a passive wait.

### 2.3b — MONITOR (5-min cadence, confident early-stop)   [only when `monitor_early_stop` is opted in]

Purpose: kill an obviously-doomed candidate early instead of burning its full budget — but ONLY when
CONFIDENT. Early RL curves are noisy and non-monotonic — a dip at 20–40 % of budget routinely recovers
(ledger #11 / #14 / #16). A slow or noisy run is NOT a kill candidate; a merely-underperforming run trains
to completion and is judged at `.done` as before. This step only catches the *unambiguously* doomed.

While ≥1 job is in flight, repeat this tick (no `Monitor` tool in this agent — use a bounded Bash wait):

1. **Wait up to `monitor_interval` (≈300 s) for the next `.done`:**
   `Bash(timeout≈interval+10s, "timeout <interval> bash -c 'until [ -f <task_dir>/iter_<NNN>/.done ]; do sleep 15; done'; [ -f <task_dir>/iter_<NNN>/.done ] && echo DONE || echo TICK")`
   (at `pool_size>1`, make the `until` test cover every in-flight `.done`).
2. **`DONE`** → process that `.done` normally (§2.4 SCORE → §2.5 DECIDE).
3. **`TICK`** (still training) → snapshot EACH in-flight trial's LIVE curves. The live trial dir is the
   newest `harbor/outputs/<algo>_<task>_*` (its `trial_dir.txt` is written only at completion, so resolve
   it yourself):
   ```bash
   trial=$(ls -dt harbor/outputs/<algo>_<task>_* | head -1)
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/reward-tuning-agent/curve_health.py" \
       --metrics "$trial/metrics.jsonl" --total-steps <this iter's total_timesteps> \
       --success-term <design.success_term> --success-weight <its weight> \
       --stage0-term <earliest ladder term> --soft-floor <monitor_soft_floor> \
       | tee -a <task_dir>/iter_<NNN>/monitor.jsonl
   ```
   `Read` the snapshot and apply the RUBRIC. Not stopping → loop to step 1.

**EARLY-STOP RUBRIC (confident-only).** Early-stop iff one holds:
- **`concern == "hard_fail"`** (`nan_inf`, or `dead_policy` = entropy collapsed to ~0 with total flat) — act
  on the FIRST occurrence, at any `budget_frac`. NaN / a dead-collapsed policy does not recover.
- **`concern == "confident_bad"`** (`no_learning` / `total_declining` / `optimization_diverged` — the tool
  already floors these to `watch` until `budget_frac ≥ monitor_soft_floor` and suppresses them when
  `improving`) on **≥2 CONSECUTIVE ticks** (~10 min of persistent badness). One bad tick is never enough —
  that is the dip-and-recover trap the soft-floor + persistence together guard against.

NEVER early-stop on `concern ∈ {none, watch}`, an `improving` flag, a single soft tick, or a later stage
flat while an earlier one is still climbing (tail exposure). **When unsure, KEEP the run** — a wasted run
costs only compute; a wrongly-killed good reward costs a whole iteration AND pollutes the search.

**Executing an early-stop:** `kill -TERM` the trial's process group (escalate `-KILL` after 30 s; `pkill -P`
orphans), `touch <task_dir>/iter_<NNN>/.done`, and record `iters[NNN].status = "early_stopped"` with the
trigger flag + the deciding snapshot(s) in `tune-state.json`. Then run §2.4 on what exists: score from the
last checkpoint if one was written, else `success_rate = 0` (do NOT render a dead policy). Append a one-line
`memories.jsonl` finding (WHY it was doomed — this steers the next DESIGN). In §2.5 an `early_stopped` iter
is a non-improving completion (bumps the stuck counter) and its diagnosis feeds the next candidate.

### 2.4 — SCORE (on each `.done`) + render fallback

Ensure `iter_<NNN>/render.mp4` exists (only re-render if the job's tail failed / on resume — local: run
render.py + cp; cluster: sbatch a render-only job, never inline on login node). Then score, reading
`design.json` for `success_term`:

```python
final = last_step(parse_jsonl(f"{trial_dir}/metrics.jsonl"))
per_term = {k.split("/")[1]: v for k,v in final.items()
            if k.startswith("reward/") and k.endswith("/episodic_return_mean")}
total_return = final["reward/total/episodic_return_mean"]
success_rate = per_term[design["success_term"]] / <that term's weight>
```
- **HARD GATE:** there MUST be per-term keys beyond `reward/total/...`. Total-only ⇒ per-term logging
  regressed — flag it (`success_rate=null`), do NOT fabricate a score from total-only curves.
- Extract `n_frames` from `render.mp4` (`ffmpeg`), `Read` them, describe what the policy does vs
  `description`. If `render.mp4` is genuinely absent, note it and score numerically only.
- Write `iter_<NNN>/analysis.md` (per-term table + success_rate + behavior + 0–3 findings). Append
  `findings` to `memories.jsonl`. Update `tune-state.json:iters[NNN]`, remove the iter from `in_flight[]`.

### 2.5 — DECIDE + refill

```python
if success_rate >= success_threshold:
    status = "converged"; best_iter = NNN
    if on_success == "cancel":  scancel/kill each in_flight job
    else:                       drain remaining in_flight, then stop
    break
elif success_rate > best_success_rate or total_return > best_total_return:
    consecutive_non_improving = 0; update best_*; overwrite handoff with this reward state
else:
    consecutive_non_improving += 1
    if consecutive_non_improving >= prompt_every_n_stuck:
        # handle the stuck-prompt YOURSELF via AskUserQuestion
        if ask_user("stuck N completions — continue / abort / change strategy?") == "abort": break
# refill the freed slot (unless converged/aborted): 2.1 DESIGN → 2.2 IMPLEMENT (re-write onto the SAME
# slot clone) → 2.3 LAUNCH. Reproduce ramp: if iter 0 failed, refill up to pool_size distinct structured
# adaptations from the verbatim baseline and proceed as the normal async pool thereafter.
```
One `.done` is processed per turn, so `in_flight` reads/writes are naturally serialized — no locking.

## STEP 3 — Finalize + return

Delete every slot clone via the script (`--op delete --repo <repo_path> --manifest <task_dir>/clone-slot<i>.json`)
— run on success AND failure, no orphans. At `pool_size=1` there is nothing to delete, BUT if the loop
ended NOT on the best iter (abort, or best < last), re-implement `handoff-reward-generator.md` (latest BEST
state) on the source first, so the source never ends carrying a worse-than-best reward. Append a
"Final summary" block to `reward-history.md`; set `tune-state.json:status` + `finished_at`. Return the
distilled verdict.

## Hard rules

- **English-only** comments / logs. **No nested dispatch** (no Agent tool) — cloning is `clone_task.py`,
  per-term logging is the reward-add-log flow run in-line.
- **§7 DR placeholder stays untouched.** No registry mutations
  (`harbor/benchmark-generator/benchmark-spec.json` is benchmark-generator's).
- **Isolation matches the pool.** `pool_size=1` edits the SOURCE directly (no clone, no cleanup); `pool_size>1`
  edits ONLY slot clones. Raise `pool_size` above 1 only once clone independence (SC2) is trusted.
- **Train at default num_envs** (smoke uses fewer). **Render folded into the train job** (compute-side).
- **No hard cap.** Stop on `success_rate ≥ threshold` or user abort; prompt every `prompt_every_n_stuck`
  non-improving completions. **Checkpoint `tune-state.json` every iteration** (resume-safe).
- **Single source of truth per file:** `reward-history.md` (cumulative), `handoff-reward-generator.md`
  (latest best), `memories.jsonl` (findings), `tune-state.json` (metadata + pool + in_flight + per-iter).

---
description: Author a NEW task or surgically edit an EXISTING task in a benchmark repo. Pre-flight verifies the dependency-generator → benchmark-generator → rl-integration-generator chain in sequence and dispatches any missing stage first (rl-integration defaults to the custom_torch algorithm source unless the user specifies one). Then reads <repo>/harbor/create-task/task-implementation.md and dispatches up to three subagents (task-generator → reward-generator → dr-generator) based on the requested sections, each running its own smoke. Also supports REPRODUCE mode via `from=<path>` (a per-task spec emitted by /harbor:probe-task) — rebuilds the task identically including reward / DR / observation / action code. Use when the user types /harbor:task-create name=<TaskID> description="..." [sections=<list>] [assets=<paths>] | /harbor:task-create name=<TaskID> from=<path>, or asks "create a new task", "scaffold a task called X", "reproduce task Y from this spec", "edit only the action/reward/observation of task X".
argument-hint: name=<TaskID> (description="<spec>" | from=<spec.md>) [sections=<comma-list of 1..7>] [assets=<path1,path2,...>]
---

# /harbor:task-create — Author or Edit a Task

The user wants to either (a) add a NEW task to the current benchmark repo, or (b) surgically edit a subset of an EXISTING task. The shape, file pointers, code templates, and per-phase smoke commands all live in `<repo>/harbor/create-task/task-implementation.md` — written by `benchmark-generator`. This command body parses the user's spec, bootstraps any missing prerequisite stage (dependency-generator → benchmark-generator → rl-integration-generator, checked in that order), and orchestrates the relevant subagents.

## Required arguments

| Arg | Notes |
|---|---|
| `name` | Task ID for `gym.register` (or family equivalent). For new tasks must follow the family's naming convention; for edit mode must already exist. |
| `description` OR `from` | Exactly one of these. `description=<one paragraph>` for free-form authoring; `from=<spec.md path>` for verbatim reproduction from a `/harbor:probe-task` output. |

## Optional arguments

| Arg | Default | Effect |
|---|---|---|
| `sections` | (all) | Comma-separated list of section numbers from 1..7. Omitted ⇒ create mode (full §1..§7 chain). Provided ⇒ edit mode (partial chain, task must already exist). Section→agent mapping: §1 register/scene · §2 actions · §3 reset · §4 goal+termination · §5 observation → `task-generator`. §6 reward → `reward-generator`. §7 DR → `dr-generator`. |
| `assets` | (none) | Comma-separated repo-relative paths or asset URLs. If set, `task-generator` §1 prefers these over Nucleus / library defaults. Ignored when §1 is not in the requested sections. In reproduce mode (`from=...`) `assets` overrides paths the spec resolved against the source repo — use when the destination repo's assets live at different locations. |

`/create-task` does NOT take a `repo_path` — it always operates on `$(pwd)`. Run it from inside the benchmark repo.

## Mode determination

| Inputs | Mode | Pre-flight |
|---|---|---|
| `description=...`, no `sections` | **create** (full new task) | task ID must NOT already be in `harbor/benchmark-generator/benchmark-spec.json:tasks[].id` |
| `description=...`, `sections=...` | **edit** | task ID must already exist (`gym.make(<name>)` works) |
| `from=<spec.md>` (with or without `sections`) | **reproduce** | task ID must NOT already exist; spec file must exist and parse |

## Reproduce mode (`from=<spec.md>`)

When `from=` is supplied, the orchestrator:

1. Reads the per-task spec at `<spec.md>` (output of `/harbor:probe-task`). Validates it has the expected `# <task_id> — Implementation Spec` header and §1..§7 sections.
2. Synthesizes a description for each subagent by **quoting that section's Code block verbatim**, with a preamble: `"Reproduce <task_id> from spec at <spec.md>. Section §N must match the Code block below byte-for-byte (after renaming the spec's task_id to <name> and updating asset paths if `assets=` overrides were given). No ambiguity resolution — if any placeholder remains in the spec, surface AskUserQuestion."`
3. Passes each section's Code block as a `spec_section` kwarg to the relevant subagent in addition to the family-level `task-implementation.md`. The subagents prefer the per-task spec over the family guide when both are present.
4. `sections` defaults to **all 7** in reproduce mode (so the rebuilt task is byte-identical except for `name` / `assets` overrides). If the user passes `sections=...`, only the listed sections are reproduced; the rest are left at the family template's placeholder.

The spec is treated as **ground truth** — subagents don't re-derive design choices from the description, they paste-then-adjust.

## Action

### Step 0 — Pre-flight

1. Resolve `repo_path = $(pwd)`. Verify the prerequisite chain **in sequence** — each stage's output is the next stage's input. For any stage whose done-check fails, dispatch that agent first (main thread orchestrates — constraint #4; wait for it to finish cleanly before checking the next stage):

   | # | Stage | Done-check | If missing |
   |---|---|---|---|
   | 1 | `dependency-generator` | `test -x ${repo_path}/.venv/bin/python` | `Agent(dependency-generator, prompt={repo_path})` — renders `harbor/dependency-generator/setup_uv.sh`, creates `.venv/`, runs the import smoke |
   | 2 | `benchmark-generator` | `test -f ${repo_path}/harbor/benchmark-generator/benchmark-spec.json` AND its `tasks[]` is non-empty | `Agent(benchmark-generator, prompt={repo_path})` — random rollout + render-to-MP4 smokes, writes `benchmark-spec.json` + `task-implementation.md` (Step 3.7) |
   | 3 | `rl-integration-generator` | `test -f ${repo_path}/harbor/rl-integration-generator/rl-suite-spec.json` | `Agent(rl-integration-generator, prompt={repo_path, algorithm_source})` — renders the train/eval/render scaffold + configs |

   **`algorithm_source` for stage 3**: if the user's prompt names a source (`stable_baseline3`, `local_implementation` with a package path / github URL) or otherwise states a specific algorithm requirement, honor it. Otherwise default to `custom_torch` (the self-contained custom algorithm tree) — do NOT ask.

   After stages 1–2 are green, additionally verify `harbor/create-task/task-implementation.md` exists. If `benchmark-spec.json` was already present but the guide is missing (older run), author it via `/harbor:probe-benchmark` (≡ benchmark-generator Step 3.7) before continuing.

   A bootstrap agent that finishes with a failure verdict is a **hard stop** — print its error and exit; do not run later stages or the task-authoring chain.

2. Parse args:
   - `name` → in **create**/**reproduce** mode, validate against family convention (read `task-implementation.md:CANONICAL_EXAMPLE_TASK_ID` as the pattern).
   - Exactly one of `description` / `from`:
     - `description` → trim; require non-empty. Sets mode = create (no sections) or edit (sections).
     - `from` → resolve to absolute path; verify the file exists and parses as a probe-task spec (top-level `# <task_id> — Implementation Spec` header + `## §1..§7` anchors). Sets mode = reproduce.
   - `sections` → split on commas; validate each element is one of `{1,2,3,4,5,6,7}`. Empty/missing → all seven (create / reproduce mode). Compute the partition:
     - `task_sections = sections ∩ {1,2,3,4,5}`
     - `do_reward     = 6 ∈ sections`
     - `do_dr         = 7 ∈ sections`
   - `assets` → split on commas; verify each entry exists on disk OR is a fully-qualified URL. Drop missing entries with a one-line warning.

3. Mode-specific check:
   - **create**: refuse if `<name>` already exists in `harbor/benchmark-generator/benchmark-spec.json:tasks[].id`. Authoring a duplicate is out-of-scope.
   - **edit**: verify `<name>` already builds:
     ```bash
     .venv/bin/python -c "import gymnasium as gym; gym.make('<name>'); print('build ok')"
     ```
     Refuse if it doesn't.
   - **reproduce**: refuse if `<name>` already exists. Parse the `from` spec and extract per-section Code blocks into `spec_sections = {"1": <code>, "2": <code>, ..., "7": <code>}` for downstream injection. If any requested section is absent from the spec (e.g. spec was emitted with a `WARN:` on §6), refuse and surface the WARN.

### Step 1 — Mint (or reuse) the per-task workspace

```bash
slug=$(echo "<name>" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]' '-' | sed 's/--*/-/g; s/^-//; s/-$//')
task_dir="${repo_path}/harbor/create-task/${slug}"
mkdir -p "${task_dir}"
```

Write `${task_dir}/spec.json` (overwriting any prior run for this slug):

```json
{
  "schema_version": 1,
  "task_id": "<name>",
  "slug": "<slug>",
  "description": "<description verbatim>",
  "assets": ["<path1>", "<path2>"],
  "mode": "create|edit",
  "sections": [1,2,3,4,5,6,7],
  "created_at": "<iso8601>",
  "phases": {
    "task_generator":   {"status": "pending|skipped", "smoke": {}},
    "reward_generator": {"status": "pending|skipped", "smoke": {}},
    "dr_generator":     {"status": "pending|skipped", "smoke": {}}
  }
}
```

`status: skipped` is set up-front for any agent whose sections aren't requested (e.g. if `sections=2,5`, `reward_generator` and `dr_generator` start as `skipped`).

Each subagent updates its own `phases.<role>` slot with the final status. The orchestrator reads the slot post-dispatch to decide whether to continue.

Each subagent also writes a per-role process log inside the same directory:

| Agent | Log file | Contents |
|---|---|---|
| `task-generator`   | `<task_dir>/task-history.md`   | Per-section block for each section in `task_sections`: decisions resolved (with source — user / canonical / repo-scan / batched-ask), files written, smoke command, smoke output (last 50 lines), per-attempt diagnosis, verdict |
| `reward-generator` | `<task_dir>/reward-history.md` | Decisions resolved, files modified, composer chosen, per-term-logging token, smoke command + output, iteration notes |
| `dr-generator`     | `<task_dir>/dr-history.md`     | Skip-or-wire rationale, decisions resolved, files modified, smoke command + output, iteration notes |

These logs are **append-only within one agent's run**, written as work progresses. Each agent discovers state from the repo (env_cfg, mdp/ tree) on entry — there is no inter-agent handoff file.

### Step 1.5 — Search the task-library (create / edit mode)

Before dispatching the chain, run the protocol in `${CLAUDE_PLUGIN_ROOT}/references/task-library-search.md` **once** for the whole task:

1. Classify the task's embodiment from `<description>` + `<name>` → pick the `experiences/task-library/<folder>/`.
2. `ls` + `grep -ril <verb/object/robot keywords>` that folder; pick the 1–3 most relevant `*-implementation.md` specs. Set `library_refs = [<abs paths>]`.
3. If a match is **byte-identical** to what's wanted, recommend `/harbor:task-create from=<that spec>` (reproduce mode) and ask the user whether to switch before authoring from scratch.
4. Record the matches (or "no match") in `spec.json` and the final summary.

Skip in **reproduce** mode — the `from=<spec>` already IS the source design. Never block on an empty library; `library_refs = []` is fine. Pass `library_refs` into the task-generator and reward-generator dispatches so they don't each re-grep.

### Step 2 — Dispatch `task-generator` (sections from §1..§5)

Only when `task_sections` is non-empty:

```
Agent(task-generator, prompt={
  repo_path:     <abs>,
  task_dir:      <task_dir>,
  task_id:       <name>,
  description:   <description>,                   // for create/edit; reproduce mode synthesizes from spec
  assets:        [<...>],
  sections:      <task_sections>,                 // e.g. [1,2,3,4,5] (create) or [2,5] (partial edit)
  library_refs:  [<abs paths>],                   // Step 1.5 matches — relevant task-library specs to mirror (§1–§5)
  spec_sections: {"1": <code>, ...}               // ONLY in reproduce mode — per-section ground-truth Code blocks
                                                  // from the probe-task spec. Subagent prefers these over
                                                  // resolving from description/family-guide.
})
```

The agent owns §1 (register/scene), §2 (actions), §3 (reset), §4 (goal+termination), §5 (observation). It authors the requested sections in Phase A, then runs the smokes for those sections in Phase B with a per-smoke retry budget. Ambiguity in any section's "Decisions" sub-block triggers a single batched `AskUserQuestion`. In **reproduce** mode, the agent pastes `spec_sections[N]` verbatim (renaming task_id and substituting `assets[]` overrides), and ambiguity is treated as a spec defect — surface immediately rather than asking the user.

**Verdict shape**:
```json
{
  "phase": "task_generator",
  "status": "pass|fail",
  "smoke": {"S1": "pass|fail|skipped", ...},
  "files_written": ["<repo-relative paths>"],
  "errors": []
}
```

Smoke entries for sections NOT in `task_sections` read `skipped`.

Persist into `${task_dir}/spec.json:phases.task_generator`. **Stop the chain if `status != pass`** — print the verdict and exit. Downstream agents have nothing to attach to.

### Step 3 — Dispatch `reward-generator` (§6)

Only when `do_reward` is true AND (task-generator was skipped OR returned pass):

```
Agent(reward-generator, prompt={
  repo_path:     <abs>,
  task_dir:      <task_dir>,
  task_id:       <name>,
  description:   <description>,
  library_refs:  [<abs paths>],                   // Step 1.5 matches — relevant task-library specs to mirror (§6 reward)
  spec_section:  <spec_sections["6"]>             // ONLY in reproduce mode — full §6 Code block (RewardsCfg
                                                  // + all reward function source) from probe-task. Pasted
                                                  // verbatim into mdp/rewards.py + env_cfg.
})
```

The agent reads §6 of `task-implementation.md` and the existing reward (placeholder for create mode, real reward for edit mode), authors the new reward, runs the §6 smoke, iterates on failure. In **reproduce** mode, `spec_section` is ground truth — the agent pastes it, runs the smoke, and only iterates if the smoke fails (which would indicate a spec defect, not authoring ambiguity).

Persist verdict into `${task_dir}/spec.json:phases.reward_generator`. Stop the chain if `status != pass`.

### Step 4 — Dispatch `dr-generator` (§7)

Only when `do_dr` is true AND prior agents (whichever ran) returned pass:

```
Agent(dr-generator, prompt={
  repo_path:     <abs>,
  task_dir:      <task_dir>,
  task_id:       <name>,
  description:   <description>,
  spec_section:  <spec_sections["7"]>             // ONLY in reproduce mode — full §7 Code block (EventCfg
                                                  // DR terms) from probe-task. May be "<no DR>" — then the
                                                  // agent skips DR entirely.
})
```

The agent reads §7 of `task-implementation.md` and the existing DR slot, wires DR (or skips per the 3-condition gate), runs the §7 smoke. In **reproduce** mode, if `spec_section == "<no DR>"`, skip outright; else paste the spec block verbatim and run the smoke.

Persist verdict into `${task_dir}/spec.json:phases.dr_generator`. DR can be a soft fail — `status: skipped` still counts as chain success.

### Step 5 — Final summary

After the chain returns (or stops on failure), print one block:

```
create-task : <task_id>  (mode: create|edit, sections: [...])
slug          : <slug>
spec          : <task_dir>/spec.json
phases        :
  task-generator   : pass — S1..S6 green       (log: <task_dir>/task-history.md)
  reward-generator : pass — finite + composer  (log: <task_dir>/reward-history.md)
  dr-generator     : skipped — no DR requested (log: <task_dir>/dr-history.md)
files written : <count>
next step     : test the task end-to-end with
                /harbor:rl-run task=<task_id> algorithm=ppo total_timesteps=20000
```

Skipped phases (whose section was not in the request) read `skipped (not requested)`. If any phase failed, replace its row with a one-line error summary and add a final line: `chain stopped at <phase> — see ${task_dir}/spec.json for details`.

## Constraints

- **Do NOT regenerate `task-implementation.md` from this command.** Subagents may patch it surgically when they find a bug; full re-renders are owned by `benchmark-generator`.
- **Sequential, not parallel.** Later agents may read files written by earlier ones; the chain is strict.
- **Per-phase smoke is fatal.** A subagent that returns `status: fail` halts the chain. The subagent owns its own retry loop.
- **Ambiguity → user, not heuristic.** Any "Decisions" sub-block in `task-implementation.md` that the user's `description` doesn't fully resolve must trigger an `AskUserQuestion`. Subagents must batch all open questions for one section into a single ask.
- **No editing of sibling tasks.** Refactoring nearby tasks is out-of-scope.
- **Do not append to `harbor/benchmark-generator/benchmark-spec.json`.** That file is `benchmark-generator`'s output.

## Examples

```text
# Create mode (no sections arg) — full §1..§7 chain
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Franka panda pushes a small wooden block from the table center toward a target marker. Episode succeeds when block-to-marker distance < 5cm; horizon 200 steps."

# Create mode with explicit asset override
/harbor:task-create name=Isaac-Open-Drawer-Custom-v0 \
  description="UR10 opens a drawer to a target opening angle. Use absolute joint position control." \
  assets=assets/custom_drawer.usd

# Edit mode — only swap action mode to delta-EE-pose on an existing task
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Switch action mode to delta-EE-pose via DifferentialIK; keep the rest unchanged." \
  sections=2

# Edit mode — re-author actions and observations together (e.g. add an obs term that the new action mode needs)
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Use delta-EE-pose actions and add ee_pose_in_robot_root_frame to the obs." \
  sections=2,5

# Edit mode — only swap reward
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Boost reaching weight to 5.0 and add a contact-bonus term." \
  sections=6

# Edit mode — only wire DR after the rest is settled
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Add startup-mass and friction randomization for sim-to-real robustness." \
  sections=7

# Reproduce mode — clone an existing task into a new benchmark from a probe-task spec
/harbor:task-create name=Isaac-Push-Block-UR10-v0 \
  from=harbor/create-task/isaac-push-block-franka-v0-implementation.md

# Reproduce mode with asset overrides (destination repo's assets live elsewhere)
/harbor:task-create name=Isaac-Push-Block-UR10-v0 \
  from=harbor/create-task/isaac-push-block-franka-v0-implementation.md \
  assets=harbor/assets/ur10/ur10.usd,harbor/assets/cube_blue/cube.usd

# Reproduce mode but only re-apply §6 (reward) from the spec; keep §1..§5 / §7 untouched
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  from=harbor/create-task/isaac-push-block-franka-other-reward.md \
  sections=6
```

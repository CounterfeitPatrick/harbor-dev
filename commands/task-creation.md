---
description: Author a NEW task or surgically edit an EXISTING task in a benchmark repo. Reads <repo>/harbor/task-creation/task-implementation.md (must already exist — created by benchmark-generator) and dispatches up to three subagents (task-generator → reward-generator → dr-generator) based on the requested sections, each running its own smoke. Use when the user types /harbor:task-creation name=<TaskID> description="..." [sections=<list>] [assets=<paths>] or asks "create a new task", "scaffold a task called X", "edit only the action/reward/observation of task X".
argument-hint: name=<TaskID> description="<one-paragraph spec>" [sections=<comma-list of 1..7>] [assets=<path1,path2,...>]
---

# /harbor:task-creation — Author or Edit a Task

The user wants to either (a) add a NEW task to the current benchmark repo, or (b) surgically edit a subset of an EXISTING task. The shape, file pointers, code templates, and per-phase smoke commands all live in `<repo>/harbor/task-creation/task-implementation.md` — written by `benchmark-generator`. This command body parses the user's spec, verifies the doc exists, and orchestrates the relevant subagents.

## Required arguments

| Arg | Notes |
|---|---|
| `name` | Task ID for `gym.register` (or family equivalent). For new tasks must follow the family's naming convention; for edit mode must already exist. |
| `description` | One paragraph in plain English. The agents quote-include this verbatim into AskUserQuestion prompts when resolving ambiguity. Wrap in double quotes to allow spaces. For edit mode, scope the description to what's changing (e.g. "switch action mode to delta-EE-pose"). |

## Optional arguments

| Arg | Default | Effect |
|---|---|---|
| `sections` | (all) | Comma-separated list of section numbers from 1..7. Omitted ⇒ create mode (full §1..§7 chain). Provided ⇒ edit mode (partial chain, task must already exist). Section→agent mapping: §1 register/scene · §2 actions · §3 reset · §4 goal+termination · §5 observation → `task-generator`. §6 reward → `reward-generator`. §7 DR → `dr-generator`. |
| `assets` | (none) | Comma-separated repo-relative paths or asset URLs. If set, `task-generator` §1 prefers these over Nucleus / library defaults. Ignored when §1 is not in the requested sections. |

`/task-creation` does NOT take a `repo_path` — it always operates on `$(pwd)`. Run it from inside the benchmark repo.

## Mode determination

| Inputs | Mode | Pre-flight |
|---|---|---|
| no `sections` arg | **create** (full new task) | task ID must NOT already be in `harbor/benchmark-spec.json:tasks[].id` |
| `sections=...` (subset of 1..7) | **edit** | task ID must already exist (`gym.make(<name>)` works) |

## Action

### Step 0 — Pre-flight

1. Resolve `repo_path = $(pwd)`. Verify it's a benchmark workspace:

   ```bash
   test -x "${repo_path}/.venv/bin/python"                                   || { echo "ERROR: <repo>/.venv missing — run /harbor:env-generator first"; exit 1; }
   test -f "${repo_path}/harbor/benchmark-spec.json"                       || { echo "ERROR: harbor/benchmark-spec.json missing — dispatch benchmark-generator first"; exit 1; }
   test -f "${repo_path}/harbor/task-creation/task-implementation.md"      || { echo "ERROR: harbor/task-creation/task-implementation.md missing — dispatch benchmark-generator (Step 3.7) to author it"; exit 1; }
   ```

   **Hard stop on any miss.**

2. Parse args:
   - `name` → in **create** mode, validate against family convention (read `task-implementation.md:CANONICAL_EXAMPLE_TASK_ID` as the pattern).
   - `description` → trim; require non-empty.
   - `sections` → split on commas; validate each element is one of `{1,2,3,4,5,6,7}`. Empty/missing → all seven (create mode). Compute the partition:
     - `task_sections = sections ∩ {1,2,3,4,5}`
     - `do_reward     = 6 ∈ sections`
     - `do_dr         = 7 ∈ sections`
   - `assets` → split on commas; verify each entry exists on disk OR is a fully-qualified URL. Drop missing entries with a one-line warning.

3. Mode-specific check:
   - **create**: refuse if `<name>` already exists in `harbor/benchmark-spec.json:tasks[].id`. Authoring a duplicate is out-of-scope.
   - **edit**: verify `<name>` already builds:
     ```bash
     .venv/bin/python -c "import gymnasium as gym; gym.make('<name>'); print('build ok')"
     ```
     Refuse if it doesn't.

### Step 1 — Mint (or reuse) the per-task workspace

```bash
slug=$(echo "<name>" | tr '[:upper:]' '[:lower:]' | tr -c '[:alnum:]' '-' | sed 's/--*/-/g; s/^-//; s/-$//')
task_dir="${repo_path}/harbor/task-creation/${slug}"
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

### Step 2 — Dispatch `task-generator` (sections from §1..§5)

Only when `task_sections` is non-empty:

```
Agent(task-generator, prompt={
  repo_path:   <abs>,
  task_dir:    <task_dir>,
  task_id:     <name>,
  description: <description>,
  assets:      [<...>],
  sections:    <task_sections>     // e.g. [1,2,3,4,5] (create) or [2,5] (partial edit)
})
```

The agent owns §1 (register/scene), §2 (actions), §3 (reset), §4 (goal+termination), §5 (observation). It authors the requested sections in Phase A, then runs the smokes for those sections in Phase B with a per-smoke retry budget. Ambiguity in any section's "Decisions" sub-block triggers a single batched `AskUserQuestion`.

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
  repo_path:   <abs>,
  task_dir:    <task_dir>,
  task_id:     <name>,
  description: <description>
})
```

The agent reads §6 of `task-implementation.md` and the existing reward (placeholder for create mode, real reward for edit mode), authors the new reward, runs the §6 smoke, iterates on failure.

Persist verdict into `${task_dir}/spec.json:phases.reward_generator`. Stop the chain if `status != pass`.

### Step 4 — Dispatch `dr-generator` (§7)

Only when `do_dr` is true AND prior agents (whichever ran) returned pass:

```
Agent(dr-generator, prompt={
  repo_path:   <abs>,
  task_dir:    <task_dir>,
  task_id:     <name>,
  description: <description>
})
```

The agent reads §7 of `task-implementation.md` and the existing DR slot, wires DR (or skips per the 3-condition gate), runs the §7 smoke.

Persist verdict into `${task_dir}/spec.json:phases.dr_generator`. DR can be a soft fail — `status: skipped` still counts as chain success.

### Step 5 — Final summary

After the chain returns (or stops on failure), print one block:

```
task-creation : <task_id>  (mode: create|edit, sections: [...])
slug          : <slug>
spec          : <task_dir>/spec.json
phases        :
  task-generator   : pass — S1..S5 green       (log: <task_dir>/task-history.md)
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
- **Do not append to `harbor/benchmark-spec.json`.** That file is `benchmark-generator`'s output.

## Examples

```text
# Create mode (no sections arg) — full §1..§7 chain
/harbor:task-creation name=Isaac-Push-Block-Franka-v0 \
  description="Franka panda pushes a small wooden block from the table center toward a target marker. Episode succeeds when block-to-marker distance < 5cm; horizon 200 steps."

# Create mode with explicit asset override
/harbor:task-creation name=Isaac-Open-Drawer-Custom-v0 \
  description="UR10 opens a drawer to a target opening angle. Use absolute joint position control." \
  assets=assets/custom_drawer.usd

# Edit mode — only swap action mode to delta-EE-pose on an existing task
/harbor:task-creation name=Isaac-Push-Block-Franka-v0 \
  description="Switch action mode to delta-EE-pose via DifferentialIK; keep the rest unchanged." \
  sections=2

# Edit mode — re-author actions and observations together (e.g. add an obs term that the new action mode needs)
/harbor:task-creation name=Isaac-Push-Block-Franka-v0 \
  description="Use delta-EE-pose actions and add ee_pose_in_robot_root_frame to the obs." \
  sections=2,5

# Edit mode — only swap reward
/harbor:task-creation name=Isaac-Push-Block-Franka-v0 \
  description="Boost reaching weight to 5.0 and add a contact-bonus term." \
  sections=6

# Edit mode — only wire DR after the rest is settled
/harbor:task-creation name=Isaac-Push-Block-Franka-v0 \
  description="Add startup-mass and friction randomization for sim-to-real robustness." \
  sections=7
```

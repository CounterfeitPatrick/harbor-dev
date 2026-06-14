---
description: Clone an existing task into an isolated, independently-editable copy registered under a new suffixed gym id, or delete a previously-created clone. Used by /harbor:reward-tune to give each parallel reward candidate its own collision-free task to edit + train. `op=create` dispatches the task-cloner subagent (copy source's editable surface → rewire imports → register `<source>-rewarditer<NNN>` → run clone smokes). `op=delete` removes the clone's files and confirms the source still builds. Use when the user types /harbor:task-clone op=create source=<TaskID> dest=<TaskID> | op=delete dest=<TaskID>, or asks "clone task X for isolated editing".
argument-hint: op=create source=<TaskID> dest=<TaskID> [repo=<path>] [info_out=<path>] | op=delete dest=<TaskID> [repo=<path>]
---

# /harbor:task-clone — Isolated Task Clone

Make a standalone copy of a task so a candidate can edit its reward (or any section) **without touching the source or any sibling clone**. The copy is registered under a new gym id (`<source>` with a `-rewarditer<NNN>` suffix inserted **before** the `-vN` token) and is verified to build + roll out + inherit per-term logging.

This is the isolation primitive `/harbor:reward-tune` uses for parallel candidates. Cloning is serialized in the caller (the orchestrator creates clones one at a time), so registration never races — only the trainings run in parallel.

## Required arguments

| Arg | Notes |
|---|---|
| `op` | `create` or `delete`. |
| `source` | (create) Existing task id; `gym.make(<source>)` must succeed. |
| `dest` | New task id. Must be valid for `gym.register` (word chars / `:` / `.` / `-` only — **no `#`**) and must insert its suffix before any `-vN` version token. |

## Optional arguments

| Arg | Default | Effect |
|---|---|---|
| `repo` | `$(pwd)` | Repo root. |
| `info_out` | `<repo>/harbor/clones/<dest>.json` | Where to write the clone manifest (caller passes the candidate dir, e.g. `<task_dir>/iter_<NNN>/clone-info.json`). |

## Action

### op=create

1. **Pre-flight** (in `repo`):
   ```bash
   test -x .venv/bin/python || exit 1
   .venv/bin/python -c "import gymnasium as gym; gym.make('<source>'); print('source ok')" || exit 1
   ```
   Validate `<dest>` is a legal gym id and differs from `<source>`. Reject a `#` or a suffix placed after `-vN`.

2. **Dispatch the `task-cloner` subagent** (main thread — no nesting):
   ```
   Agent(task-cloner, prompt={
     repo_path: <abs>,
     source_id: <source>,
     dest_id:   <dest>,
     info_out:  <info_out abs>
   })
   ```
   The agent copies the source's editable surface (env_cfg + reward-relevant mdp modules), rewires the cloned cfg's imports to the copies, registers `<dest>`, runs the clone smokes, and writes the manifest. See `agents/task-cloner.md`.

3. **Return** the agent verdict + manifest path. On `status: fail`, the agent has already removed any partial clone — surface the error and exit non-zero.

### op=delete

Lightweight, no subagent. Read `<info_out>` (or `<repo>/harbor/clones/<dest>.json`), remove every path in `cloned_files[]` and the registration entry it recorded, then confirm the source still builds:

```bash
.venv/bin/python -c "import gymnasium as gym; gym.make('<source_from_manifest>'); print('source still ok')" || exit 1
```

Delete is idempotent — a missing manifest or already-removed files is a no-op success (the clone is gone either way).

## Constraints

- **Never edit the source task's files.** A clone only writes NEW files + one registration entry.
- **Registration suffix goes before `-vN`** (`Isaac-Lift-Cube-Franka-v0` → `Isaac-Lift-Cube-Franka-rewarditer7-v0`), never after.
- **Clone creation is serialized by the caller.** This command assumes it is not invoked concurrently for the same repo (the reward-tune orchestrator guarantees this); trainings parallelize, cloning does not.
- **Clean up on failure.** A create that fails any smoke removes its partial files before returning — no orphans.

## Examples

```text
# Clone for reward candidate 7, manifest into the candidate dir
/harbor:task-clone op=create source=Isaac-Lift-Cube-Franka-v0 dest=Isaac-Lift-Cube-Franka-rewarditer7-v0 \
    info_out=harbor/create-task/isaac-lift-cube-franka-v0/iter_007/clone-info.json

# Delete it after the candidate is scored
/harbor:task-clone op=delete dest=Isaac-Lift-Cube-Franka-rewarditer7-v0 \
    info_out=harbor/create-task/isaac-lift-cube-franka-v0/iter_007/clone-info.json
```

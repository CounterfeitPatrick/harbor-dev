---
name: task-cloner
description: |
  Clones an existing task into an isolated, independently-editable copy registered under a new suffixed gym id. Copies only the task's EDITABLE surface (env_cfg + the mdp modules a reward edit would touch), rewires the cloned cfg's imports to the copies, mirrors the source's registration mechanism for `<dest>`, then runs the clone smokes (build + rollout + per-term-logging). Writes a manifest listing every created file so the clone can be deleted cleanly. Dispatched by /harbor:task-clone (op=create). PREREQUISITE: `gym.make(<source_id>)` succeeds. Never edits the source task's files.
tools: [Read, Write, Edit, Bash, Glob, Grep]
model: opus
---

# Task Cloner

Produce a standalone copy of `<source_id>` registered as `<dest_id>` that builds, rolls out, and can have its reward edited **without affecting the source or any sibling clone**. You add only NEW files plus one registration entry; you never modify the source task's code.

## Inputs

```json
{
  "repo_path": "<abs path>",
  "source_id": "<existing TaskID>",
  "dest_id":   "<new TaskID — suffix BEFORE any -vN token, no '#'>",
  "info_out":  "<abs path to write clone-info.json>"
}
```

## Output

```json
{
  "phase":        "task_cloner",
  "status":       "pass|fail",
  "dest_id":      "<dest>",
  "smoke":        {"build": "pass|fail", "rollout": "pass|fail", "per_term_logging": "yes|no"},
  "cloned_files": ["<repo-relative>", "..."],
  "reward_path":  "<repo-relative cloned reward module / RewardsCfg location>",
  "manifest":     "<info_out>",
  "errors":       []
}
```

## References (load on demand)

- `${CLAUDE_PLUGIN_ROOT}/references/task-cloner/clone-contract.md` — what each clone check verifies + the registration rule + smoke substitution slots.
- `${CLAUDE_PLUGIN_ROOT}/harbor/create-task/task-implementation.md` (in the repo) — per-family file pointers: where env_cfg / mdp / registration live for THIS benchmark.

## Smoke template

```
${CLAUDE_PLUGIN_ROOT}/templates/task-cloner/smokes/smoke_clone.py.template
```

Render to `<repo>/harbor/clones/_smoke/smoke_<dest_slug>.py` substituting `{{DEST_ID}}` + `{{NUM_ENVS}}` (2 for gpu-sim per `benchmark-spec.json:gpu_sim`, else 1), then run inside `.venv`. Pass = exit 0 + final line `CLONE OK: ...`.

## Step 0 — Pre-flight

```bash
cd "<repo_path>"
test -x .venv/bin/python || exit 1
.venv/bin/python -c "import gymnasium as gym; gym.make('<source_id>'); print('source ok')" || exit 1
```

Read the repo's `harbor/create-task/task-implementation.md` for the family's file conventions, then locate the source task's: (a) `*_env_cfg.py` (the cfg class + its `RewardsCfg`), (b) the `mdp/` modules its reward functions live in, (c) its `gym.register(...)` site.

## Workflow

```
- [ ] Discover the source task's editable surface + registration site
- [ ] Copy that surface to dest-named files; rewire the cloned cfg's imports
- [ ] Register <dest_id> mirroring the source's mechanism (suffix before -vN)
- [ ] Render + run smoke_clone.py
- [ ] Write clone-info.json manifest; return verdict (clean up on failure)
```

### Discover + copy

1. **Editable surface = the env_cfg file + every mdp module a reward edit could touch** (typically `mdp/rewards.py`, plus any task-local `mdp/*` the cfg imports from a TASK-specific path). Shared, family-wide read-only modules that the reward never edits stay imported from their originals — do NOT copy the whole family.
2. Copy each surface file to a `<dest_slug>`-named sibling (e.g. `lift_cube_franka_env_cfg.py` → `lift_cube_franka_rewarditer7_env_cfg.py`). Rename the cfg class + any module-level symbols that must be unique.
3. **Rewire the cloned cfg's imports** so its reward terms resolve to the COPIED mdp module(s), not the originals. This is what makes edits to the clone invisible to the source.

### Register

Mirror exactly how the source registers (same `gym.register` idiom / entry-point shape), pointing `<dest_id>` at the cloned cfg class. Insert the suffix **before** the `-vN` token. Prefer adding the registration where the source's own registration is picked up at import time; do not mutate the source task's own register call.

### Smoke

Render + run `smoke_clone.py`. It builds `<dest_id>`, steps a short rollout, asserts finite reward, and reports whether `info["detailed_reward"]` (per-term logging) is present. Per-term logging absent is a **warning**, not a failure (reward-tune wires it via `/harbor:reward-add-log` before the loop) — record `per_term_logging: no` and continue.

If the build/rollout smoke FAILS, diagnose once (usually an un-rewired import or a missed unique-rename), fix, re-run. On a second failure: remove all files you created + the registration entry, and return `status: fail`.

### Manifest

Write `<info_out>`:
```json
{
  "source_id": "<source>",
  "dest_id":   "<dest>",
  "created_at":"<iso8601>",
  "cloned_files": ["<repo-relative>", "..."],
  "registration": {"file": "<repo-relative>", "anchor": "<the register entry text>"},
  "reward_path": "<repo-relative>"
}
```
`op=delete` reads this to remove every `cloned_files[]` entry + the registration anchor, then re-checks the source builds.

## Hard rules

- **English-only** comments.
- **Never edit source task files** — only NEW files + one registration entry.
- **Suffix before `-vN`**, no `#` in the id.
- **Copy the reward-editable surface, not the family.** Over-copying bloats the repo; under-copying (sharing the reward module) reintroduces the collision the clone exists to prevent. The independence is what SC verifies.
- **Clean up partial clones on failure** — leave the repo exactly as you found it.

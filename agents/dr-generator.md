---
name: dr-generator
description: |
  Authors §7 (domain randomization) of a task in a benchmark repo. Two modes — **create** (replace the empty DR slot left by task-generator) and **edit** (overwrite an existing DR config). Reads task-implementation.md as a per-benchmark migration aid; relies on its own contracts (smoke template + IsaacLab DR reference) for the actual checks. Phase A authors DR (or skips per the 3-condition gate); Phase B renders the §7 smoke template and runs it. Iterates up to 2× on smoke failure; ambiguity batches into a single AskUserQuestion. PREREQUISITE: the task already builds (`gym.make` succeeds).
tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
model: opus
---

# DR Generator (§7)

Write the §7 DR config at the existing slot — empty (create mode) or populated (edit mode) — then smoke-check it. §1..§6 are already authored; you discover them by scanning the repo. Cross-section edits to §1..§6 are permitted only when §7 genuinely needs them; log them in `dr-history.md`.

`status: skipped` is a valid success outcome — see the skip gate below.

## Inputs

```json
{
  "repo_path":   "<abs path>",
  "task_dir":    "<abs path>/harbor/create-task/<slug>",
  "task_id":     "<TaskID>",
  "description": "<one paragraph>"
}
```

## Output

```json
{
  "phase":            "dr_generator",
  "status":           "pass|fail|skipped",
  "smoke":            {"S7": "pass|fail|skipped"},
  "files_written":    ["<repo-relative>"],
  "decisions_resolved": {"axes": [...], "ranges": {...}, "schedule": "startup|interval|reset"},
  "iterations":       1,
  "errors":           []
}
```

## Permitted reads + writes

- **Read** `<repo>/harbor/create-task/task-implementation.md` — per-benchmark file pointers (NOT the smoke contract).
- **Read** the canonical example file end-to-end + scan the rest of the repo freely.
- **Edit** `task-implementation.md` surgically when you find a bug. Log the edit in `dr-history.md`. Don't rewrite wholesale.
- **Write** the DR config into the new task's env_cfg.

## References (load on demand)

- `${CLAUDE_PLUGIN_ROOT}/references/dr-generator/isaaclab-dr-reference.md` — surface-by-family, EventCfg modes, common `mdp.randomize_*` functions, range conventions, the disable-DR-for-comparison recipe.
- `${CLAUDE_PLUGIN_ROOT}/references/dr-generator/smoke-contract.md` — what S7 verifies + substitution slot specs.

## Smoke template

```
${CLAUDE_PLUGIN_ROOT}/templates/dr-generator/smokes/smoke_s7.py.template
```

Render to `<task_dir>/smokes/smoke_s7.py` substituting `{{TASK_ID}}` and `{{DR_DISABLE_OVERRIDES}}`. Run inside `.venv`. Pass = exit 0 + final stdout line `S7 OK: ...`.

## Step 0 — Pre-flight

```bash
cd "<repo_path>"
test -x .venv/bin/python                                       || exit 1
test -f harbor/create-task/task-implementation.md          || exit 1
.venv/bin/python -c "import gymnasium as gym; gym.make('<task_id>'); print('build ok')" || exit 1
mkdir -p "<task_dir>/smokes"
```

Locate the existing DR slot (empty in create mode, populated in edit mode) by scanning the repo. Note its shape — you'll replace cleanly.

## Skip gate

Skip §7 entirely (return `status: skipped`) if ALL three hold:

1. User description does NOT request randomization, robustness, sim-to-real, or noise.
2. §7 reference task in `task-implementation.md` has no DR wired (`<unsupported>` or zero terms).
3. Family default = no-DR (`dm_control`, `gymnasium-generic`).

If any is false, you wire DR — even if minimal.

## Workflow — two phases

```
- [ ] Read task-implementation.md §7 + canonical example + isaaclab-dr-reference
- [ ] Locate DR slot in the task's env_cfg
- [ ] Skip-or-wire decision (3-condition gate)
- [ ] Phase A: author §7 (resolve decisions → write/Edit DR)
- [ ] Phase B: render + run smoke_s7, with retry budget
- [ ] Persist verdict + return
```

### Phase A — authoring rules

1. **Mirror the §7 reference task** in `task-implementation.md`, OR a closer sibling found by scanning the repo. Substitute `<TaskName>` placeholders.
2. **Resolve "Decisions"** in this order: user `description` → reference task value → minimal preset (mass × U(0.8,1.2) startup; friction × U(0.7,1.3) startup; obs noise σ=0.01). Batch ambiguous into a single `AskUserQuestion` (max 4 items, recommended = reference value).
3. **Range conventions** — multiplicative for scaled quantities (mass, gains); additive for offsets (pose ranges). Default schedule = `startup`. Refuse axes the family marks `n/a`.
4. **Forbidden** — ranges that drop a quantity to zero/negative; axes that change obs structure; cross-section edits to §1..§6 just to make DR work.

### Phase B — render and run smoke

Build the `{{DR_DISABLE_OVERRIDES}}` block: one line per §7 EventCfg term collapsing its range to a point interval. Reset terms (`reset_*`) belong to §3 — do NOT collapse them. Render `smoke_s7.py.template` → `<task_dir>/smokes/smoke_s7.py`, run inside `.venv`.

Retry loop on failure (3 attempts; `task-implementation.md` patches allowed during retry).

## Iteration budget

3 attempts. On the 3rd failure, `AskUserQuestion`:
- **A.** Apply proposed fix → re-run once.
- **B.** Hand back to user → return `status: fail`.
- **C.** Drop to no-op DR — collapse to the canonical example's MINIMAL DR (one mass-randomization term at startup); re-run once.

## Hard rules

- **English-only** for any comments.
- **No registry mutations.** `harbor/benchmark-spec.json` is owned by `benchmark-generator`.
- **No silent edits to sibling tasks.** Touch only the new task's files (and the doc, if buggy).
- **`task-implementation.md` edits are surgical** — one bug at a time, logged.
- **Cross-section edits to §1..§6** require a real need, logged explicitly.

## Process log: `<task_dir>/dr-history.md`

Append-only as you work. Header on entry: `task_id`, `slug`, `benchmark_family`, `dr_slot_path`, `prior_dr_state` (`empty` / `populated`), `started_at`, `status: in progress`. Then append:

- **Skip-or-wire block** — table of the 3 gate conditions + outcome.
- **Authoring block** (wire path only) — Decisions resolved (with source: user / canonical / repo-scan / batched-ask), files written/edited, any User Q&A pasted verbatim.
- **Smoke block** (wire path only) — rendered smoke path, last 50 lines of stdout, max obs delta, verdict; iteration table when attempts > 1; any `task-implementation.md` patches called out.

Final verdict block: `status` (pass / fail / skipped), `axes`, `schedule`, `iterations`, `files_written`, doc patches applied, `finished_at`. Update the header in place.

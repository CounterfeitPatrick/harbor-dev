# Task-library search protocol (run FIRST, before any design)

Loaded by `task-generator`, `reward-generator`, and the `/harbor:task-create` / `/harbor:reward-tune`
orchestrators. Before authoring or tuning anything, search the cross-run **task-library** for a similar
task already designed end-to-end, plus the relevant **experience ledger** — then reuse what fits. This
turns a cold-start design into "adapt a proven sibling," which is faster and higher-quality.

The library is filled by `/harbor:update-experience target=task-library` from `/harbor:probe-task`
specs; each file is a full §1..§7 implementation spec named `<short-task>-<repo>.md`.

## Step 1 — Classify the new task's embodiment

From the task `description` + `task_id` (and the in-repo canonical example if already known), pick the
folder under `${CLAUDE_PLUGIN_ROOT}/experiences/task-library/`:

| Folder | When |
|---|---|
| `manipulation/single-arm-manipulation/` | one arm/hand manipulating objects (pick, place, insert, lift, stack, in-hand) |
| `manipulation/multi-arm-manipulation/`  | two+ arms / bimanual / multi-robot manipulation |
| `locomotion/humanoid/`                   | bipedal humanoid locomotion |
| `locomotion/quadrupedal/`                | quadruped locomotion |

If the task spans/straddles categories, search the closest folder first, then the sibling.

## Step 2 — Find relevant specs (filenames are searchable on purpose)

```bash
LIB="${CLAUDE_PLUGIN_ROOT}/experiences/task-library/<folder>"
ls "$LIB"                                   # short accurate names: stack-three-cube-IsaacLab.md, ...
grep -ril "<verb|object|robot keywords>" "$LIB"   # e.g. "stack", "drawer", "cube", "franka"
```

Rank by overlap with the new task's verb (stack / insert / lift / grasp / walk …), object class, and
robot. Pick the **1–3 best matches**. Skim each match's `Task summary` + the sections you own
(`task-generator` → §1–§5; `reward-generator` → §6) — don't read whole files you don't need.

## Step 3 — Read the matching experience ledger

Also read the caller's own append-only ledger (heuristics distilled across runs):

| Caller | Ledger |
|---|---|
| `task-generator` | `experiences/task-generator/task-experience.md` |
| `reward-generator` / `/harbor:reward-tune` | `experiences/reward-generator/reward-experience.md` |
| `dr-generator` | `experiences/dr-generator/dr-experience.md` |

## Step 4 — Use it, but the destination family wins

- **Reuse** the matched spec's structure and decisions (action mode, reset ranges, reward term ladder,
  composer, gating, DR axes) as the starting point — adapt names/paths to the destination task.
- **The in-repo canonical example + `task-implementation.md` remain ground truth** for the destination
  benchmark's API/idioms. When the library spec and the destination family disagree on *how* to express
  something, follow the destination family; borrow only the *design intent* from the library.
- If a library spec is byte-identical to what you need, prefer `/harbor:task-create from=<that spec>`
  (reproduce mode) over re-authoring — surface this to the user.

## When the library is empty / no match

Note it in the process log ("task-library: no relevant prior task in `<folder>`") and proceed with the
normal canonical-example-driven flow. Never block on an empty library.

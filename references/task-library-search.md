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

## Step 4 — Adapt-first (BINDING): minimal modification of the matched spec

When a relevant match exists, **adapt-first is the rule, not a suggestion**: the best-matched spec is
the BASE implementation, and authoring means computing the **minimal modification** that turns the
proven base into the new task. Do NOT re-derive design choices from scratch that the base already
settles — a worked task encodes dozens of validated decisions (action mode, reset ranges, obs layout,
reward term ladder, weights, composer, gating, DR axes); every gratuitous deviation from it is an
unforced risk.

- **Start from the base**: take the matched spec's sections you own as the starting implementation.
  Change only what the new task's description / scene actually requires (object count/size, poses,
  robot placement, success geometry, stage predicates, asset paths, names).
- **Embodiment swaps do NOT license inheriting the destination cfg's defaults.** When the base's
  robot asset is unavailable and you substitute the in-repo canonical robot, the base's **init
  pose / init qpos**, gains-relevant choices, and other pose-level design decisions must still be
  PORTED (joint values map 1:1 across same-family arms, e.g. FR3 → Panda). The base chose its init
  qpos for a reason (e.g. "EE arcs over the table"); silently taking the substitute cfg's default
  pose is a known failure mode that cripples exploration. If a value genuinely cannot port, that is
  a `changed:` bullet in the Adaptation delta — never an undeclared fallback.
- **The in-repo canonical example + `task-implementation.md` remain ground truth** for the destination
  benchmark's API/idioms. When the library spec and the destination family disagree on *how* to express
  something, follow the destination family; borrow the *design* from the library.
- If a library spec is byte-identical to what you need, prefer `/harbor:task-create from=<that spec>`
  (reproduce mode) over re-authoring — surface this to the user.

**Pure creation mode is the fallback of last resort** — it activates ONLY when the library has no
relevant task at all (empty folder, or no spec sharing the verb/object-class/embodiment). "The match
isn't perfect" is not a reason to go pure-create; it's a reason to adapt with a larger delta.

## Step 5 — Document the adaptation delta in the history file

Every caller MUST record in its history file (`task-history.md` / `reward-history.md` / the
`## Iter <N>` section of a tune) an **Adaptation delta** block:

```markdown
### Adaptation delta
- base: <abs path of the matched library spec>  (or "none — pure creation mode: no relevant task in <folder>")
- kept as-is: <what was reused unchanged — e.g. action mode, composer, gating structure>
- changed: <enumerated list — one bullet per deviation from the base, each with WHY the new task requires it>
```

This is what makes the next run's search useful: the delta shows which knobs actually had to move
between two sibling tasks.

## When the library is empty / no match

Only then does pure creation mode activate. Note it in the process log ("task-library: no relevant
prior task in `<folder>` — pure creation mode") and proceed with the canonical-example-driven flow.
Never block on an empty library.

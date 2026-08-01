# §5 — Observation

What the policy sees, in what order, in what frame.

## What §5 authors

- The `ObservationsCfg` `policy` group: one `ObsTerm` per quantity, **in a deliberate order**
  (the order is the observation vector's layout, and downstream slicing depends on it).
- Per-term noise, as `Unoise(n_min=0, n_max=0)` in create mode — the placeholder `dr-generator`
  widens in §7.
- Any additional groups the benchmark uses (`critic`, `subtask_terms`, …) when the family's
  canonical example has them.

## Decisions to resolve

| Decision | Notes |
|---|---|
| Term list | Everything the policy needs, and nothing it should not see. A reward term reading a signal the policy cannot observe is a partially-observable task by accident. |
| Term order | Fixed by this design; persist it (see the smoke) so iterations do not silently reorder. |
| Frame | Robot-root vs world vs env-local. The plugin default matters — see API surface. |
| Goal exposure | If §4 uses a command manager, the goal usually belongs here. |

## API surface

`references/task-generator/isaaclab-code-reference.md` → **Observation manager**, and
**Frame convention (plugin default)** — the frame rule is the one most often got wrong, since
`root_pos_w` is world-framed and most terms want it relative to the env origin or the robot root.

For full pose (position + orientation) in the robot root frame, use `subtract_frame_transforms`
from `isaaclab.utils.math`; for an EE pose, the cleanest path is `body_pose_w` minus root pose
with quaternion composition.

## Smoke S5

Proves the observation **term order and per-term shapes** match the §5 design, and that at
least one term's value matches an independent computation.

- `{{EXPECTED_TERMS_PY}}` — a Python literal (list of `(name, shape)` tuples) describing the
  designed order for the `policy` group.
- `{{VALUE_CHECK_BLOCK}}` — at least one assertion of the form `obs_slice == derived_value`
  (e.g. `joint_pos_rel == joint_pos - default_joint_pos`).

**Persist the expected terms** to `<task_dir>/smokes/expected_obs.json` when authoring, so a
later iteration re-renders the same expectation instead of re-deriving it from whatever the
env currently returns — which would make the smoke tautological.

Full substitution list: `templates/task-generator/smokes/smoke_s5.py.template`.

## Failure → diagnosis → fix

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| Shape mismatch on one term | term returns per-env scalars vs vectors | check the term function's return shape is `(num_envs, dim)` |
| Order mismatch | terms added in a different order than designed | the cfg's declaration order **is** the observation order; reorder the cfg |
| Value check fails by a constant | frame mismatch (world vs env-local) | subtract `scene.env_origins`, or use `subtract_frame_transforms` |
| Value check fails by a rotation | quaternion convention or frame composition | compose through the root pose rather than comparing raw world quantities |
| Total obs dim changed unexpectedly | a term with a concatenating group | check group `concatenate_terms` and any nested groups |

## Known traps

- **Reordering §5 invalidates every trained checkpoint** for the task — the policy's input
  layout changed. In a tuning loop this makes runs before and after incomparable.
- **A value check derived from the env itself proves nothing.** The independent computation
  must come from raw state, not from another observation term.

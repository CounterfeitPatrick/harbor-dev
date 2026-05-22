# Smoke contracts (S1..S5)

Loaded by `task-generator`. The minimum behavioral check for each section. Templates live at `${CLAUDE_PLUGIN_ROOT}/templates/task-generator/smokes/smoke_s{1..5}.py.template` — render to `<task_dir>/smokes/` with substitutions, run inside the venv.

| Smoke | What it verifies | Required substitutions |
|---|---|---|
| S1 | env instantiates; `action_space`, `observation_space`, `max_episode_length`, term lists are valid | `{{TASK_ID}}` |
| S2 | random action → expected controller target; mode-correct (delta vs absolute, with/without default offset) | `{{TASK_ID}}`, `{{ACTION_TERM_NAME}}`, `{{ACTION_MODE}}` |
| S3 | reset values match simulation state (point-interval injection then read-back) | `{{TASK_ID}}`, `{{INIT_OVERRIDES_BLOCK}}`, `{{EXPECTED_STATE_CHECKS}}` |
| S4 | goal value present in obs at correct slice + forced-failure scenario triggers termination | `{{TASK_ID}}`, `{{GOAL_OVERRIDES_BLOCK}}`, `{{TERMINATION_FORCE_BLOCK}}` |
| S5 | obs term order + per-term shapes match the §5 design + at least one term value matches an independent computation | `{{TASK_ID}}`, `{{EXPECTED_TERMS_PY}}`, `{{VALUE_CHECK_BLOCK}}` |
| S-success | drive the env into the success configuration → confirm the success termination term specifically fires (not just any termination) | `{{TASK_ID}}`, `{{SUCCESS_TERM_NAME}}`, `{{SUCCESS_FORCE_BLOCK}}` |

**Render S-success for every task that has a success-style termination term.** Skip only when the task is purely time-out terminated (no success condition). The S-success smoke is a sibling of S1..S5 in Phase B; the agent renders `templates/task-generator/smokes/smoke_success.py.template` to `<task_dir>/smokes/smoke_success.py` and runs it after S4.

### Visualize sibling (`smoke_success_visualize.py`)

A non-asserting, **never-exits** sibling for visual confirmation of the success geometry. Same task pattern, different intent:

- Defaults to **headed** (`HEADLESS=0`) and **NUM_ENVS=1**.
- Loops on `unw.sim.step(render=True)`, re-pinning every relevant entity to its success pose each frame (so gravity / integration drift never accumulates).
- Substitution slot: `{{SUCCESS_HOLD_BLOCK}}` — a per-frame pin block that MUST also pin the "anchor" / "goal" entity (skipped by `SUCCESS_FORCE_BLOCK` since the smoke runs only one step) AND zero linear + angular velocities each frame.

Render alongside `smoke_success.py` for any task with a success-style termination term. The visualize file does NOT run during Phase B regression — it's an interactive tool for the user.

Run command:
```
cd <repo>
HEADLESS=0 NUM_ENVS=1 .venv/bin/python -u <task_dir>/smokes/smoke_success_visualize.py
```

## Pass criterion

A smoke is pass iff:
- the rendered script exits 0,
- no `Traceback` / `AssertionError` appears in stdout,
- the script's final line reads `S<N> OK: ...`.

## Num envs

All smokes (S1..S5) build the env at **`num_envs=128`** (parallelism stress-tests env-builder bugs that hide at 1 env). Custom value-check blocks the agent fills in the `{{...}}` slots should index `[0]` to pick the first env when comparing scalar reads against expected values — every env at no-op DR sees the same point-interval reset, so any single env is representative. For batched assertions use `torch.allclose` over the full `(128, dim)` tensor.

For S4 specifically: `write_root_pose_to_sim(...)` rejects a `(1, 7)` tensor when num_envs>1 — broadcast the failure pose to `(num_envs, 7)`:

```python
pose = torch.tensor([px, py, pz, qw, qx, qy, qz], device=unw.device)
unw.scene[<obj>].write_root_pose_to_sim(pose.expand(unw.num_envs, -1).contiguous())
```

## What goes in the agent-filled blocks

**S2 — `{{ACTION_MODE}}`**: pick from the known IsaacLab modes (`abs_joint_default_offset`, `abs_joint_no_offset`, `delta_joint`, `abs_ee_pose`, `delta_ee_pose`, `binary_gripper`, `joint_effort`, `non_holonomic`, `ema_delta_joint_pos`, `ema_delta_ee_pose`). The S2 template has the per-mode expected formula already; you just pick the mode. The two `ema_*` modes are the custom EMACumulative* actions — see the IsaacLab code reference for render templates and cfg shapes.

**S3 — `{{INIT_OVERRIDES_BLOCK}}`**: lines that pin `cfg.events.<term>.params["pose_range"]` / `["position_range"]` to point intervals. **`{{EXPECTED_STATE_CHECKS}}`**: assertions reading `unw.scene[<asset>].data.<field>` and comparing against the injected values via `torch.allclose`.

**S4 — `{{GOAL_OVERRIDES_BLOCK}}`**: pin `cfg.commands.<name>.ranges.*` to point intervals. **`{{TERMINATION_FORCE_BLOCK}}`**: code that drives the env into a failure state. Two common shapes:
- *Pose-driven failure* (e.g. `object_dropping`): write below-floor pose with `unw.scene[<obj>].write_root_pose_to_sim(...)`, step once with zero action, assert `term.any()`.
- *Time-out only*: run `max_episode_length + 1` steps with zero actions, assert `trunc.any()`.

**S5 — `{{EXPECTED_TERMS_PY}}`**: Python literal (list of `(name, shape)` tuples) describing the §5-design obs order for the `policy` group. **`{{VALUE_CHECK_BLOCK}}`**: at least one assertion of the form `obs_slice == derived_value` (e.g. `joint_pos_rel == joint_pos - default_joint_pos`).

## When to deviate

`task-implementation.md`'s per-section smoke commands are reference material, not the contract. When the doc's smoke is weaker than the contract here, **use the contract** and (optionally) patch the doc surgically with the contract version.

When a non-IsaacLab family is in play, substitute the family-equivalent API on the same contract surface — the *checks* stay the same; the *call sites* differ.

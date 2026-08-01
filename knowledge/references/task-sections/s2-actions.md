# §2 — Action terms

How a policy action becomes a controller target, and whether the robot can actually reach it.
Two smokes, because those are two different failures: S2 checks the **mapping**, S2.5 checks
the **physics**.

## What §2 authors

- The `ActionsCfg` block: one term per controllable group (arm, gripper, base), each with its
  mode, `scale`, and any offset / clamp the mode takes.
- Custom action terms, when the design calls for a mode IsaacLab does not ship.

## Decisions to resolve

| Decision | Notes |
|---|---|
| Mode, per term | One of: `abs_joint_default_offset`, `abs_joint_no_offset`, `delta_joint`, `abs_ee_pose`, `delta_ee_pose`, `binary_gripper`, `joint_effort`, `non_holonomic`, `ema_delta_joint_pos`, `ema_delta_ee_pose`. |
| `scale` | Sets how far one unit of policy output moves the target. Carry the base task's value when adapting. |
| Default offset | Whether the action is relative to the robot's default joint pos. Changes the S2 expected formula. |
| EMA `alpha` | `ema_*` modes only — the smoothing constant. |

The two `ema_*` modes are the custom `EMACumulative*` action terms shipped with the plugin;
their render templates live at `knowledge/templates/task-generator/action_terms/`.

## API surface

`knowledge/references/task-generator/isaaclab-code-reference.md` → **Action manager**, and for the
custom terms, **Custom action term: EMA cumulative-delta joint position** and **Custom action
term: EMA cumulative-delta EE pose**.

## Smoke S2

Proves a known random action maps to the **expected controller target** for the mode chosen —
delta vs absolute, with or without the default offset. The template already carries the
per-mode expected formula; the agent picks the mode.

Substitutions: see `knowledge/templates/task-generator/smokes/smoke_s2.py.template`.

## Smoke S2.5 — actuator tracking

Proves the actuator **reaches** the target S2 verified: hold a reachable action, let it settle,
then assert achieved `joint_pos` ≈ commanded `joint_pos_target`. A large residual means the
robot's physics parameters are wrong, not the action term.

- **Runs only after S2 passes**, and only for position-control modes. **Skip** for
  `joint_effort` / `non_holonomic` / `binary_gripper` — there is no position target to track.
  Record `S2.5: skipped`.
- **Multi-arm tasks run one S2.5 per arm** (`{{ROBOT_ASSET}}` = `robot_0`, `robot_1`, …).
- `{{HOLD_ACTION_EXPR}}` must be a **reachable static** target. `torch.zeros((NUM_ENVS,
  action_dim))` holds the home pose — the hardest gravity hold, and the right default for
  `abs_joint_default_offset` / `delta_joint` / `ema_*`. For `abs_ee_pose` /
  `abs_joint_no_offset`, zeros may command something unreachable; set a reachable target instead.
- Defaults: `{{SETTLE_STEPS}}` `150`, `{{TRACKING_TOL}}` `0.05` rad for joint space — tighten
  or loosen to the robot.

Full substitution list: `knowledge/templates/task-generator/smokes/smoke_s2_5.py.template`.

## Failure → diagnosis → fix

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| S2 target off by the default joint pos | wrong offset variant of the mode | switch between `abs_joint_default_offset` and `abs_joint_no_offset` |
| S2 target off by a constant factor | `scale` mismatch | align `scale` with the base task's value |
| S2 `KeyError` on the term name | `{{ACTION_TERM_NAME}}` is not in `action_manager._terms` | read the active term list off the built env, not the cfg source |
| **S2.5 residual too large** | improper robot physics params | **fix §1**: raise `stiffness` / `damping` / `effort_limit` (implicit actuators) or `kp` / `kd` (explicit) toward the benchmark's own example for that robot, then re-run |
| S2.5 residual large only under load | `effort_limit` saturating | raise the effort limit before touching gains |

## Known traps

- **S2.5 is the one section smoke whose fix is not in its own section.** Its failure is a §1
  robot/actuator cfg problem; editing the action term to make it pass hides a robot that
  cannot hold its own arm up.
- **Zeros are not always reachable.** For task-space modes, a zero action is a pose command at
  the origin, not "stay put".

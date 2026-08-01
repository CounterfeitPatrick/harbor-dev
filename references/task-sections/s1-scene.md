# §1 — Registration + scene

The task's identity and its physical world: the `gym.register` entry, the env cfg class, and
the scene the simulator builds from it.

## What §1 authors

- The `gym.register(...)` call — id, entry point, `env_cfg_entry_point`, and any kwargs the
  benchmark's own registrations carry. Mirror the canonical example's idiom exactly; a
  registration that differs structurally is the most common reason `gym.make` fails later.
- The env cfg class (`@configclass class <Task>EnvCfg(ManagerBasedRLEnvCfg)`) and its
  `__post_init__`.
- The scene cfg: robot articulation, manipulated objects, table / ground plane, lights,
  sensors, and any frame transformers the later sections read.
- Sim parameters — `dt`, `decimation`, `episode_length_s`, physics material and solver
  settings — when the task needs values other than the family's defaults.

## Decisions to resolve

In precedence order: the user's `description` → the canonical example's value → a closer
sibling found by scanning the repo → ambiguous (batch into one `AskUserQuestion`).

| Decision | Notes |
|---|---|
| Robot asset | A user-supplied asset path is binding, never a preference (task-experience #2). |
| Object assets | Prefer the benchmark's stock cfgs; note spawn source (USD / URDF import path). |
| Init poses | Where every entity starts. This is task **design**, not robot idiom — see traps. |
| Table / ground | The workspace surface the reward's height terms will key on. |
| Sensors | Contact sensors, frame transformers. Author them here if any later section reads them. |
| `dt` / `decimation` / `episode_length_s` | Deviate from the family default only with a reason. |

## API surface

`references/task-generator/isaaclab-code-reference.md` → **Boot + instantiate** (how a smoke
brings the env up) and **Scene state** (reading entity state back out).

## Smoke S1

Proves the env **instantiates**: `gym.make` succeeds, and `action_space`,
`observation_space`, `max_episode_length` and the manager term lists are all valid.

- Runs **first**, always, in every mode — nothing downstream can be verified until the env builds.
- Substitutions: see `templates/task-generator/smokes/smoke_s1.py.template`.
- It is also the build check a `reward-candidate-agent` runs before anything else, whether or
  not its candidate touched §1.

## Failure → diagnosis → fix

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| `gym.error.NameNotFound` | registration not imported, or id typo | check the package `__init__` actually imports the module holding `gym.register` |
| USD / asset not found | wrong path, or an asset that needs the URDF-import path | resolve the path against the benchmark's asset root; use the family's URDF importer for URDF sources |
| Entity missing from the scene at runtime | declared on the wrong cfg, or shadowed by `__post_init__` | confirm the attribute is on the scene cfg and that `__post_init__` does not overwrite it |
| Env builds but everything sinks / explodes | collision props, mass, or solver settings | check collision approximation and physics material before touching `dt` |

## Known traps

- **Init qpos does not come with the robot.** When you substitute a robot because the base
  task's asset is missing, `SomeRobotCfg.replace(...)` silently inherits the substitute's
  default home pose. Port the base's `init_state.joint_pos` — joint values map 1:1 across
  same-family arms. See `experiences/task-generator/task-experience.md` #1 for the full rule,
  including which values are embodiment geometry and must *not* be ported.
- **Actuator params are a §1 concern.** When S2.5 fails, the fix lands here — raise
  `stiffness` / `damping` / `effort_limit` (implicit) or `kp` / `kd` (explicit) toward the
  benchmark's own example for that robot. See `s2-actions.md`.

# IsaacLab domain randomization reference

Loaded by `dr-generator` on demand. Per-family rules for wiring §7 (domain randomization). If a non-IsaacLab family is in play, `task-implementation.md` documents the family-equivalent surface.

## Surface-by-family

| Family | DR surface |
|---|---|
| `isaaclab-manager-based` | `EventCfg` terms with `mode` ∈ {`startup`, `interval`, `reset`} |
| `isaaclab-direct` | hand-coded inside `_setup_scene()` (startup) / `_reset_idx()` (per-reset) — no EventCfg |
| `dexteroushands` | `randomization_params` dict in cfg; `apply_randomizations()` is inherited |
| `loco-mujoco` | `domain_randomization_type` env_param (preset string) |
| `dm_control` | usually `<unsupported in this benchmark>` — honor the doc |
| `gymnasium-generic` | hand-coded inside `reset()` / `step()` |

## isaaclab-manager-based authoring

```python
# <task>/<task>_env_cfg.py
from isaaclab.envs.mdp import randomize_rigid_body_mass, randomize_rigid_body_material
from isaaclab.envs.mdp.events import EventTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass

@configclass
class EventCfg:
    # --- §3 reset terms (already authored by task-generator) live here too; do not touch them
    reset_object_position: EventTerm = ...   # left alone
    reset_robot_joints:    EventTerm = ...   # left alone

    # --- §7 DR terms ---
    randomize_block_mass = EventTerm(
        func=randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("object"),
            "mass_distribution_params": (0.8, 1.2),
            "operation": "scale",
        },
    )
    randomize_finger_friction = EventTerm(
        func=randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="panda_finger_.*"),
            "static_friction_range":  (0.8, 1.2),
            "dynamic_friction_range": (0.8, 1.2),
            "restitution_range":      (0.0, 0.0),
            "num_buckets": 64,
        },
    )
```

## Common mdp.* DR functions

| Function | Mode | Purpose |
|---|---|---|
| `randomize_rigid_body_mass` | startup | scale or add to body mass |
| `randomize_rigid_body_material` | startup | static/dynamic friction + restitution buckets |
| `randomize_actuator_gains` | startup | stiffness / damping multipliers |
| `randomize_joint_default_pos` | startup | jitter the nominal joint pose |
| `apply_external_force_torque` | interval | per-interval kicks (e.g. push the robot) |
| `add_noise_to_action` | per-step | action noise via wrapper |
| `add_noise_to_observation` | per-step | obs noise (usually via Unoise on the obs term) |

When in doubt, search `source/isaaclab/isaaclab/envs/mdp/events.py` for the available `randomize_*` symbols in the installed version.

## Range conventions

- **Multiplicative** by default (`mass *= U(0.8, 1.2)`) — preserves units and signs. `operation="scale"` for mass / actuator gains.
- **Additive** when the quantity is an offset (`pose_range x: (-0.05, 0.05)` adds to the nominal x). `operation="add"`.
- **Default schedule = startup**. Use `interval` only when ongoing perturbation is required ("the robot gets pushed periodically"); use `reset` only when the randomization should resample every episode but stay constant within an episode.

## Decision defaults (when user description is silent)

Minimal preset:
- `mass × U(0.8, 1.2)` startup
- `friction × U(0.7, 1.3)` startup
- obs Gaussian noise `σ = 0.01` (set on §5 obs terms via `Unoise(n_min=-0.01, n_max=0.01)`)

Mentions of "robustness" / "sim-to-real" → mass + friction + observation noise.
"Visual" / "domain gap" → lighting + camera pose (only if §5 has image obs).
"Sensor noise" → action and observation Gaussian noise.

## Forbidden

- DR ranges that drop a quantity to zero or negative (mass = 0, friction < 0) — env will diverge on reset
- DR axes that change obs structure (e.g. enabling/disabling a sensor with DR) — S7 smoke fails on shape mismatch
- Cross-section edits to §1..§6 just to "make DR work" — surface to user instead

## How DR is disabled for the S7 comparison

IsaacLab manager-based has no runtime `dr_enabled` toggle. The contract collapses every DR term's range to a point interval before building the comparison env:

```python
# DR ON cfg (real ranges)
cfg_on = parse_env_cfg("<TaskID>", num_envs=1)

# DR OFF cfg (collapse all §7 terms to no-op)
cfg_off = parse_env_cfg("<TaskID>", num_envs=1)
cfg_off.events.randomize_block_mass.params["mass_distribution_params"] = (1.0, 1.0)
cfg_off.events.randomize_finger_friction.params["static_friction_range"] = (1.0, 1.0)
cfg_off.events.randomize_finger_friction.params["dynamic_friction_range"] = (1.0, 1.0)
# ... one collapse per §7 term
```

The agent fills the collapse block per the actual EventCfg it authored. Reset terms (`reset_*`) are NOT collapsed — they belong to §3, not §7.

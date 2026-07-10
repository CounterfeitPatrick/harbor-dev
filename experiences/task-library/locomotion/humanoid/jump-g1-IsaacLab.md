# Isaac-Jump-G1-v0 — Implementation Spec

- benchmark_family: isaaclab-manager-based
- source_repo: IsaacLab
- source_path: source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/jump
- embodiment: G1 bipedal humanoid (locomotion)

> **CAVEAT:** All dims below are **ANALYTIC** — read from the source, not build-verified in this session. This spec captures the DESIGN for reproduction/adaptation, not a runtime trace. Joint counts (37 DOF), obs width (120), and per-term reward semantics are derived by reading the code; treat them as the intended contract.

**Task summary:** A Unitree G1 humanoid learns to **jump in place** on flat terrain and land back into a stable upright standing stance. This is a bespoke IsaacLab task adapted from the shipped velocity-tracking locomotion base (`manager_based/locomotion/velocity/velocity_env_cfg.py`) by *removing* the velocity command manager and its observation term (a jump-in-place needs no command), forcing flat-only terrain (no height scanner, no terrain curriculum), and adding a base-height fall termination. There is **no goal/command input** — the "target" is baked into the reward: a target-height-band gaussian on peak clearance (peak 1.0 at ~0.17 m over the 0.74 m nominal stance). The reward is a weighted SUM of **17 terms** built by a reward-tuning loop (see §6), dominated by a stateful full-cycle latch (`jump_cycle_reward`, weight 40) that only pays on a real both-feet flight that lands controlled and upright. Trained with RSL-RL PPO (1500 iters, 4096 envs).

---

## §1 Registration + Scene

**Description.** Registered as `Isaac-Jump-G1-v0` (train) and `Isaac-Jump-G1-Play-v0` (play, 50 envs, corruption off), both entry-pointed at the generic `ManagerBasedRLEnv`. Scene = flat plane ground with a marble visual material, the G1 (minimal-collision USD) articulation, a whole-body contact sensor (`track_air_time=True`, used for foot flight detection over `.*_ankle_roll_link`), and a dome sky light. No height scanner. Sim runs at 200 Hz physics (dt=0.005) with decimation 4 → 50 Hz control; 20 s episodes; 4096 envs at 2.5 m spacing.

**Decisions resolved.**

| Decision | Value |
|---|---|
| Gym id (train / play) | `Isaac-Jump-G1-v0` / `Isaac-Jump-G1-Play-v0` |
| Entry point | `isaaclab.envs:ManagerBasedRLEnv` |
| env_cfg_entry_point | `...jump_env_cfg:G1JumpEnvCfg` (play: `G1JumpEnvCfg_PLAY`) |
| rsl_rl_cfg | `G1JumpPPORunnerCfg` |
| Terrain | flat `plane`, `terrain_generator=None`, no curriculum |
| Ground friction (material) | static 1.0 / dynamic 1.0, restitution 0.0 (multiply combine) |
| Robot | `G1_MINIMAL_CFG` → `{ENV_REGEX_NS}/Robot` |
| Robot USD | `{ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/G1/g1_minimal.usd` |
| Base body (G1 has no "base") | `torso_link` (retargeted in binding cfg) |
| Init base height | z = 0.74 m |
| DOF count | 37 (12 legs + 1 torso + 10 arms + 14 fingers) |
| Contact sensor | all `Robot/.*` bodies, history_length=3, track_air_time=True, update_period=sim.dt |
| Height scanner | **none** (flat-only) |
| Lights | dome sky light, intensity 750, kloofendal HDR |
| sim.dt / decimation / control | 0.005 s / 4 / 50 Hz |
| episode_length_s | 20.0 |
| num_envs / env_spacing | 4096 / 2.5 (play: 50 / 2.5) |
| render_interval | = decimation (4) |
| physx gpu_max_rigid_patch_count | 10 * 2**15 |

**Code — registration** (`config/g1/__init__.py`):
```python
gym.register(
    id="Isaac-Jump-G1-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.jump_env_cfg:G1JumpEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:G1JumpPPORunnerCfg",
    },
)

gym.register(
    id="Isaac-Jump-G1-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.jump_env_cfg:G1JumpEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:G1JumpPPORunnerCfg",
    },
)
```

**Code — SceneCfg** (`jump_env_cfg.py`):
```python
@configclass
class JumpSceneCfg(InteractiveSceneCfg):
    """Configuration for a flat-terrain scene with a legged robot jumping in place."""

    # flat ground terrain (jump-in-place is flat-only)
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="plane",
        terrain_generator=None,
        max_init_terrain_level=5,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
        debug_vis=False,
    )
    # robots (filled by the robot-binding cfg)
    robot: ArticulationCfg = MISSING
    # sensors: contact sensor over all robot bodies, air-time tracked for flight detection
    contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=3, track_air_time=True)
    # lights
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=f"{ISAAC_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr",
        ),
    )
```

**Code — sim timing / env post_init** (`jump_env_cfg.py`, `LocomotionJumpEnvCfg.__post_init__`):
```python
    scene: JumpSceneCfg = JumpSceneCfg(num_envs=4096, env_spacing=2.5)

    def __post_init__(self):
        self.decimation = 4
        self.episode_length_s = 20.0
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
        self.sim.physics_material = self.scene.terrain.physics_material
        self.sim.physx.gpu_max_rigid_patch_count = 10 * 2**15
        if self.scene.contact_forces is not None:
            self.scene.contact_forces.update_period = self.sim.dt
```

**Code — G1 binding + retargeting** (`config/g1/jump_env_cfg.py`):
```python
@configclass
class G1JumpEnvCfg(LocomotionJumpEnvCfg):
    """G1 humanoid jumping in place on flat terrain."""

    def __post_init__(self):
        super().__post_init__()
        # Scene: bind the G1 robot (keeps the crouched init pose as the launch stance)
        self.scene.robot = G1_MINIMAL_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
        # G1 has no "base" body — its base link is "torso_link". Retarget the reset
        # external-force term and the fall-contact termination onto it.
        self.events.base_external_force_torque.params["asset_cfg"].body_names = ["torso_link"]
        self.terminations.base_contact.params["sensor_cfg"].body_names = "torso_link"


@configclass
class G1JumpEnvCfg_PLAY(G1JumpEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
```

**Code — G1 robot articulation** (`isaaclab_assets/robots/unitree.py`, `G1_CFG` → `G1_MINIMAL_CFG`):
```python
G1_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=f"{ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/G1/g1.usd",
        activate_contact_sensors=True,
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            disable_gravity=False,
            retain_accelerations=False,
            linear_damping=0.0,
            angular_damping=0.0,
            max_linear_velocity=1000.0,
            max_angular_velocity=1000.0,
            max_depenetration_velocity=1.0,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=False, solver_position_iteration_count=8, solver_velocity_iteration_count=4
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.74),
        joint_pos={
            ".*_hip_pitch_joint": -0.20,
            ".*_knee_joint": 0.42,
            ".*_ankle_pitch_joint": -0.23,
            ".*_elbow_pitch_joint": 0.87,
            "left_shoulder_roll_joint": 0.16,
            "left_shoulder_pitch_joint": 0.35,
            "right_shoulder_roll_joint": -0.16,
            "right_shoulder_pitch_joint": 0.35,
            "left_one_joint": 1.0,
            "right_one_joint": -1.0,
            "left_two_joint": 0.52,
            "right_two_joint": -0.52,
        },
        joint_vel={".*": 0.0},
    ),
    soft_joint_pos_limit_factor=0.9,
    actuators={
        "legs": ImplicitActuatorCfg(
            joint_names_expr=[
                ".*_hip_yaw_joint", ".*_hip_roll_joint", ".*_hip_pitch_joint", ".*_knee_joint", "torso_joint",
            ],
            effort_limit_sim=300,
            stiffness={
                ".*_hip_yaw_joint": 150.0, ".*_hip_roll_joint": 150.0, ".*_hip_pitch_joint": 200.0,
                ".*_knee_joint": 200.0, "torso_joint": 200.0,
            },
            damping={
                ".*_hip_yaw_joint": 5.0, ".*_hip_roll_joint": 5.0, ".*_hip_pitch_joint": 5.0,
                ".*_knee_joint": 5.0, "torso_joint": 5.0,
            },
            armature={".*_hip_.*": 0.01, ".*_knee_joint": 0.01, "torso_joint": 0.01},
        ),
        "feet": ImplicitActuatorCfg(
            effort_limit_sim=20,
            joint_names_expr=[".*_ankle_pitch_joint", ".*_ankle_roll_joint"],
            stiffness=20.0, damping=2.0, armature=0.01,
        ),
        "arms": ImplicitActuatorCfg(
            joint_names_expr=[
                ".*_shoulder_pitch_joint", ".*_shoulder_roll_joint", ".*_shoulder_yaw_joint",
                ".*_elbow_pitch_joint", ".*_elbow_roll_joint",
                ".*_five_joint", ".*_three_joint", ".*_six_joint", ".*_four_joint",
                ".*_zero_joint", ".*_one_joint", ".*_two_joint",
            ],
            effort_limit_sim=300,
            stiffness=40.0, damping=10.0,
            armature={
                ".*_shoulder_.*": 0.01, ".*_elbow_.*": 0.01,
                ".*_five_joint": 0.001, ".*_three_joint": 0.001, ".*_six_joint": 0.001,
                ".*_four_joint": 0.001, ".*_zero_joint": 0.001, ".*_one_joint": 0.001, ".*_two_joint": 0.001,
            },
        ),
    },
)

G1_MINIMAL_CFG = G1_CFG.copy()
G1_MINIMAL_CFG.spawn.usd_path = f"{ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/G1/g1_minimal.usd"
```

---

## §2 Actions

**Description.** Single action term: implicit-actuator joint-position targets for ALL 37 joints, scaled 0.5, added to the default (crouched) joint pose. Control at 50 Hz (decimation 4 over 200 Hz physics).

**Decisions resolved.**

| Decision | Value |
|---|---|
| Action term | `mdp.JointPositionActionCfg` (stdlib) |
| asset / joints | `robot`, `joint_names=[".*"]` (all 37) |
| scale | 0.5 |
| use_default_offset | True (targets are offset from default joint pose) |
| **action_dim** | **37** |

**Code** (`jump_env_cfg.py`):
```python
@configclass
class ActionsCfg:
    joint_pos = mdp.JointPositionActionCfg(asset_name="robot", joint_names=[".*"], scale=0.5, use_default_offset=True)
```

---

## §3 Reset / Events

**Description.** On reset the root is placed exactly at the nominal standing pose (all ranges are point/degenerate — zero randomization), joints are reset exactly to their default crouched launch pose (position scale [1.0, 1.0], zero velocity), and a zero external force/torque is applied to the base body (`torso_link`, retargeted per robot). A startup `physics_material` term exists but with degenerate point ranges (see §7 — no real DR in create mode). All `mdp.*` functions here are stdlib `isaaclab.envs.mdp`.

**Decisions resolved.**

| Term | func | mode | Key params |
|---|---|---|---|
| physics_material | `randomize_rigid_body_material` | startup | static (0.8,0.8), dynamic (0.6,0.6), restitution (0.0,0.0), num_buckets 64 — **degenerate** |
| base_external_force_torque | `apply_external_force_torque` | reset | body `torso_link`, force (0,0), torque (0,0) — zero |
| reset_base | `reset_root_state_uniform` | reset | pose x/y/yaw (0,0); velocity x/y/z/roll/pitch/yaw (0,0) — **no randomization** |
| reset_robot_joints | `reset_joints_by_scale` | reset | position_range (1.0,1.0), velocity_range (0.0,0.0) — exact default pose |

**Code** (`jump_env_cfg.py`, `EventCfg`):
```python
@configclass
class EventCfg:
    """Configuration for events (reset only; no domain randomization in create mode)."""

    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.8, 0.8),
            "dynamic_friction_range": (0.6, 0.6),
            "restitution_range": (0.0, 0.0),
            "num_buckets": 64,
        },
    )

    base_external_force_torque = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base"),  # retargeted to torso_link in binding cfg
            "force_range": (0.0, 0.0),
            "torque_range": (-0.0, 0.0),
        },
    )

    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"x": (0.0, 0.0), "y": (0.0, 0.0), "yaw": (0.0, 0.0)},
            "velocity_range": {
                "x": (0.0, 0.0), "y": (0.0, 0.0), "z": (0.0, 0.0),
                "roll": (0.0, 0.0), "pitch": (0.0, 0.0), "yaw": (0.0, 0.0),
            },
        },
    )

    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_scale,
        mode="reset",
        params={"position_range": (1.0, 1.0), "velocity_range": (0.0, 0.0)},
    )
```

---

## §4 Goal + Command + Termination

**Description.** **No command / no goal input.** `CommandsCfg` is empty — a jump-in-place needs no velocity or height command, and there is no command observation term. The jump "target" lives entirely in the reward (§6): the stateful `jump_cycle_reward` pays a gaussian peaking at 0.17 m peak clearance over the 0.74 m nominal stance. Termination = time-out (20 s), torso-hits-ground illegal contact (>1 N on `torso_link`), or base height dropping below 0.5 m (catches falls onto a limb that the contact sensor misses). All `mdp.*` are stdlib.

**Decisions resolved.**

| Term | func | Params | time_out? |
|---|---|---|---|
| time_out | `time_out` | — | True |
| base_contact | `illegal_contact` | sensor `torso_link`, threshold 1.0 N | False |
| base_height | `root_height_below_minimum` | minimum_height 0.5 m, asset robot | False |

Command: `CommandsCfg` is an empty configclass (no terms).

**Code** (`jump_env_cfg.py`):
```python
@configclass
class CommandsCfg:
    """No commands — jump in place needs no velocity command."""


@configclass
class TerminationsCfg:
    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    # fall detection: torso hits the ground (sensor body retargeted per robot in the binding cfg)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 1.0},
    )
    # fall detection: base height drops below a floor threshold (catches falls onto a limb)
    base_height = DoneTerm(
        func=mdp.root_height_below_minimum,
        params={"minimum_height": 0.5, "asset_cfg": SceneEntityCfg("robot")},
    )
```

---

## §5 Observation

**Description.** Single `policy` group, proprioceptive-only (no command term, no privileged/critic group). Terms in fixed order: base linear velocity (3), base angular velocity (3), projected gravity (3), joint positions relative to default (37), joint velocities relative to default (37), last action (37). Concatenated → **120-dim** flat vector. Corruption enabled but ALL noise ranges are zeroed (`Unoise(0,0)`) in create mode — dr-generator would widen later. Play cfg disables corruption. All obs funcs are stdlib `isaaclab.envs.mdp`.

**Decisions resolved.**

| Term | func | dim | noise |
|---|---|---|---|
| base_lin_vel | `base_lin_vel` | 3 | Unoise(0,0) |
| base_ang_vel | `base_ang_vel` | 3 | Unoise(0,0) |
| projected_gravity | `projected_gravity` | 3 | Unoise(0,0) |
| joint_pos | `joint_pos_rel` | 37 | Unoise(0,0) |
| joint_vel | `joint_vel_rel` | 37 | Unoise(0,0) |
| actions | `last_action` | 37 | — |
| **total** | | **120** | enable_corruption=True, concatenate_terms=True |

No critic/privileged group. Play: `enable_corruption=False`.

**Code** (`jump_env_cfg.py`):
```python
@configclass
class ObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        base_lin_vel = ObsTerm(func=mdp.base_lin_vel, noise=Unoise(n_min=0.0, n_max=0.0))
        base_ang_vel = ObsTerm(func=mdp.base_ang_vel, noise=Unoise(n_min=0.0, n_max=0.0))
        projected_gravity = ObsTerm(func=mdp.projected_gravity, noise=Unoise(n_min=0.0, n_max=0.0))
        joint_pos = ObsTerm(func=mdp.joint_pos_rel, noise=Unoise(n_min=0.0, n_max=0.0))
        joint_vel = ObsTerm(func=mdp.joint_vel_rel, noise=Unoise(n_min=0.0, n_max=0.0))
        actions = ObsTerm(func=mdp.last_action)

        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()
```

---

## §6 Reward

**Description.** Weighted SUM of **17 terms** (RewardManager default composer). Weights are NOMINAL per-step magnitudes applied directly (harbor's benchmark-generator strips the `* dt` from `RewardManager.compute()`, so each declared weight IS the effective per-step magnitude — NO `__post_init__` dt-cancellation). The ladder was authored by a reward-tuning loop through iter 7; the dominant payday is the stateful `jump_cycle_reward` (weight 40), a target-height-band gaussian that only fires on a real both-feet flight landing controlled/upright, so a giant over-powered leap OVERSHOOTS the band (≈0) and an un-landed leap earns 0. Farmable dense terms are deliberately gutted (apex once-per-jump events, small bootstrap weights). Failure penalty −40. Four custom jump funcs live in `mdp/rewards.py` (verbatim below); the rest are stdlib `isaaclab.envs.mdp`.

**Decisions resolved — full reward ladder.**

| # | Term | func | weight | source | key params |
|---|---|---|---|---|---|
| 1 | jump_cycle_reward | `mdp.jump_cycle_reward` (custom, STATEFUL) | **+40.0** | rewards.py | sensor `.*_ankle_roll_link`, asset robot |
| 2 | jump_apex_clear | `mdp.jump_apex_clear` (custom) | +0.5 | rewards.py | sensor `.*_ankle_roll_link`, asset robot |
| 3 | flight_apex_height | `mdp.flight_apex_height` (custom) | +0.5 | rewards.py | nominal_height 0.74, cap 0.25 |
| 4 | jump_takeoff_count | `mdp.jump_takeoff_count` (custom) | +1.0 | rewards.py | sensor `.*_ankle_roll_link` |
| 5 | takeoff_vertical_velocity | `mdp.takeoff_vertical_velocity` (custom) | +0.3 | rewards.py | cap 1.5 |
| 6 | alive | `mdp.is_alive` (stdlib) | +0.4 | — | — |
| 7 | upright | `mdp.flat_orientation_l2` (stdlib) | −1.0 | — | — |
| 8 | horizontal_velocity | `mdp.horizontal_velocity_l2` (custom) | −1.0 | rewards.py | asset robot |
| 9 | ang_vel_xy | `mdp.ang_vel_xy_l2` (stdlib) | −0.05 | — | — |
| 10 | action_rate | `mdp.action_rate_l2` (stdlib) | −0.003 | — | — |
| 11 | joint_acc | `mdp.joint_acc_l2` (stdlib) | −2.5e-7 | — | — |
| 12 | joint_torques | `mdp.joint_torques_l2` (stdlib) | −1.0e-6 | — | — |
| 13 | joint_pos_limits | `mdp.joint_pos_limits` (stdlib) | −1.0 | — | — |
| 14 | joint_deviation_arms | `mdp.joint_deviation_l1` (stdlib) | −0.3 | — | shoulder×3, elbow×2 joints |
| 15 | joint_deviation_torso | `mdp.joint_deviation_l1` (stdlib) | −0.3 | — | `torso_joint` |
| 16 | joint_deviation_fingers | `mdp.joint_deviation_l1` (stdlib) | −0.1 | — | 7 finger joints/side |
| 17 | termination_penalty | `mdp.is_terminated` (stdlib) | −40.0 | — | — |

Note: legs are deliberately EXCLUDED from the joint_deviation posture terms (they must move to jump).

**Code — RewardsCfg** (`jump_env_cfg.py`):
```python
@configclass
class RewardsCfg:
    # --- full-cycle (stateful) ---
    jump_cycle_reward = RewTerm(
        func=mdp.jump_cycle_reward,
        weight=40.0,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
            "asset_cfg": SceneEntityCfg("robot"),
        },
    )

    # --- SUCCESS / flight terms ---
    jump_apex_clear = RewTerm(
        func=mdp.jump_apex_clear,
        weight=0.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
            "asset_cfg": SceneEntityCfg("robot"),
        },
    )
    flight_apex_height = RewTerm(
        func=mdp.flight_apex_height,
        weight=0.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
            "asset_cfg": SceneEntityCfg("robot"),
            "nominal_height": 0.74,
            "cap": 0.25,
        },
    )
    jump_takeoff_count = RewTerm(
        func=mdp.jump_takeoff_count,
        weight=1.0,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link")},
    )
    takeoff_vertical_velocity = RewTerm(
        func=mdp.takeoff_vertical_velocity,
        weight=0.3,
        params={"asset_cfg": SceneEntityCfg("robot"), "cap": 1.5},
    )

    # --- survival ---
    alive = RewTerm(func=mdp.is_alive, weight=0.4)

    # --- stability / jump-in-place ---
    upright = RewTerm(func=mdp.flat_orientation_l2, weight=-1.0)
    horizontal_velocity = RewTerm(
        func=mdp.horizontal_velocity_l2, weight=-1.0, params={"asset_cfg": SceneEntityCfg("robot")},
    )
    ang_vel_xy = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)

    # --- regularizers ---
    action_rate = RewTerm(func=mdp.action_rate_l2, weight=-0.003)
    joint_acc = RewTerm(func=mdp.joint_acc_l2, weight=-2.5e-7)
    joint_torques = RewTerm(func=mdp.joint_torques_l2, weight=-1.0e-6)
    joint_pos_limits = RewTerm(func=mdp.joint_pos_limits, weight=-1.0)

    # --- upper-body natural posture (iter 7) ---
    joint_deviation_arms = RewTerm(
        func=mdp.joint_deviation_l1, weight=-0.3,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=[
            ".*_shoulder_pitch_joint", ".*_shoulder_roll_joint", ".*_shoulder_yaw_joint",
            ".*_elbow_pitch_joint", ".*_elbow_roll_joint",
        ])},
    )
    joint_deviation_torso = RewTerm(
        func=mdp.joint_deviation_l1, weight=-0.3,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names="torso_joint")},
    )
    joint_deviation_fingers = RewTerm(
        func=mdp.joint_deviation_l1, weight=-0.1,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=[
            ".*_five_joint", ".*_three_joint", ".*_six_joint", ".*_four_joint",
            ".*_zero_joint", ".*_one_joint", ".*_two_joint",
        ])},
    )

    # --- failure ---
    termination_penalty = RewTerm(func=mdp.is_terminated, weight=-40.0)
```

**Code — custom jump reward functions** (`mdp/rewards.py`, verbatim):
```python
def flight_apex_height(
    env, sensor_cfg, asset_cfg=SceneEntityCfg("robot"), nominal_height=0.74, cap=0.25,
) -> torch.Tensor:
    """Gated base clearance above nominal standing height while airborne.
    Fires only when BOTH feet off the ground; value clip(base_z - nominal_height, 0, cap)."""
    contact_sensor = env.scene.sensors[sensor_cfg.name]
    asset = env.scene[asset_cfg.name]
    air_time = contact_sensor.data.current_air_time[:, sensor_cfg.body_ids]
    both_feet_airborne = (air_time > 0.0).all(dim=1)
    clearance = torch.clip(asset.data.root_pos_w[:, 2] - nominal_height, min=0.0, max=cap)
    return clearance * both_feet_airborne.float()


def jump_apex_clear(
    env, sensor_cfg=SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
    asset_cfg=SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Success counter: fires ~once per jump at the near-apex (vertical velocity ~0).
    Both feet airborne AND base_z > 0.89 (0.15 over 0.74 stance) AND |vz| <= 0.5."""
    contact_sensor = env.scene.sensors[sensor_cfg.name]
    air = contact_sensor.data.current_air_time[:, sensor_cfg.body_ids]
    both_air = (air > 0.0).all(dim=1)
    asset = env.scene[asset_cfg.name]
    base_z = asset.data.root_pos_w[:, 2]
    vz = asset.data.root_lin_vel_w[:, 2]
    near_apex = both_air & (base_z > 0.89) & (vz <= 0.5) & (vz >= -0.5)
    return near_apex.float()


def jump_cycle_reward(
    env, sensor_cfg=SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
    asset_cfg=SceneEntityCfg("robot"),
) -> torch.Tensor:
    """Latched full-cycle reward — the ONLY stateful term. Maintains env._jc_peak (peak base
    height this airborne phase) and env._jc_flight (latch of a genuine both-feet flight >0.78 m),
    lazily allocated and reset on episode_length_buf<=1 (stands in for a reset hook).
    Pays only on the step BOTH feet re-contact after a latched flight, torso upright, base
    recovered near standing, and nearly still. Payment = target-height-band gaussian on
    peak_clear = peak - 0.74: exp(-((peak_clear - 0.17)/0.10)**2)."""
    contact_sensor = env.scene.sensors[sensor_cfg.name]
    asset = env.scene[asset_cfg.name]
    if not hasattr(env, "_jc_peak"):
        env._jc_peak = torch.zeros(env.num_envs, device=env.device)
        env._jc_flight = torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
    newep = env.episode_length_buf <= 1
    env._jc_peak[newep] = 0.0
    env._jc_flight[newep] = False
    air = contact_sensor.data.current_air_time[:, sensor_cfg.body_ids]
    both_air = (air > 0.0).all(dim=1)
    both_contact = (air <= 0.0).all(dim=1)
    base_z = asset.data.root_pos_w[:, 2]
    env._jc_flight = env._jc_flight | (both_air & (base_z > 0.78))
    env._jc_peak = torch.where(both_air, torch.maximum(env._jc_peak, base_z), env._jc_peak)
    landed = (
        both_contact
        & env._jc_flight
        & (asset.data.projected_gravity_b[:, 2] < -0.6)
        & (base_z > 0.55) & (base_z < 0.90)
        & (torch.linalg.norm(asset.data.root_lin_vel_w, dim=1) < 3.0)
    )
    peak_clear = env._jc_peak - 0.74
    reward = torch.where(
        landed, torch.exp(-(((peak_clear - 0.17) / 0.10) ** 2)), torch.zeros_like(env._jc_peak),
    )
    env._jc_flight = env._jc_flight & (~landed)
    env._jc_peak = torch.where(landed, torch.zeros_like(env._jc_peak), env._jc_peak)
    return reward


def jump_takeoff_count(
    env, sensor_cfg=SceneEntityCfg("contact_forces", body_names=".*_ankle_roll_link"),
) -> torch.Tensor:
    """One-step pulse at each GENUINE upward takeoff (jump cadence). Both feet just left ground
    (current_air_time>0, max air_time<=0.03 s) AND base rising (vz>0.3)."""
    contact_sensor = env.scene.sensors[sensor_cfg.name]
    air = contact_sensor.data.current_air_time[:, sensor_cfg.body_ids]
    both_air = (air > 0.0).all(dim=1)
    just_started = both_air & (air.max(dim=1).values <= 0.03)
    vz = env.scene["robot"].data.root_lin_vel_w[:, 2]
    return (just_started & (vz > 0.3)).float()


def takeoff_vertical_velocity(env, asset_cfg=SceneEntityCfg("robot"), cap=2.0) -> torch.Tensor:
    """Reward upward base velocity only: clip(base_lin_vel_z, 0.0, cap). Dense bootstrap bridge."""
    asset = env.scene[asset_cfg.name]
    return torch.clip(asset.data.root_lin_vel_w[:, 2], min=0.0, max=cap)


def horizontal_velocity_l2(env, asset_cfg=SceneEntityCfg("robot")) -> torch.Tensor:
    """Penalize planar base drift: vx^2 + vy^2 of the base linear velocity."""
    asset = env.scene[asset_cfg.name]
    v = asset.data.root_lin_vel_w[:, :2]
    return torch.sum(torch.square(v), dim=1)
```

Note: `rewards.py` also defines `safe_landing`, `flight_airtime_credit`, and `flight_phase` — these are NOT wired as RewTerms in the current cfg (retained for reference/diagnostics; `flight_phase` was removed at iter 2 after being farmed by tuck-hang).

---

## §7 DR (Domain Randomization)

**Description.** **`<no DR>` in create mode.** Every event term (§3) uses point/degenerate ranges: the `physics_material` startup term has zero-width friction/restitution ranges (static 0.8/0.8, dynamic 0.6/0.6, restitution 0.0/0.0), and all reset terms are zero-range (no base-pose noise, no push, no joint-scale noise). No `push_by_setting_velocity`, no mass randomization, no actuator-gain randomization, and observation noise is all `Unoise(0,0)`. The docstrings note dr-generator would widen these later, but as-shipped there is **no effective domain randomization**.

**Decisions resolved.**

| DR category | Status |
|---|---|
| Robot mass / inertia | none |
| Friction / material | present as startup term but DEGENERATE (0.8/0.8, 0.6/0.6, 0.0/0.0) → no randomization |
| Actuator gains (stiffness/damping) | none |
| External push (`push_by_setting_velocity`) | none |
| Reset pose/velocity noise | none (all ranges (0,0)) |
| Observation noise | none (all `Unoise(0,0)`; play disables corruption entirely) |

(See §3 for the verbatim `EventCfg` — the only startup term is `physics_material` with degenerate ranges.)

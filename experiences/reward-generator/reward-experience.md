# Reward Tuning Experience

Cross-run advice from human-in-the-loop reward tuning. These are **heuristics, not rules** — they reflect patterns that have helped on real training runs, but every task is different and you should weigh them against the specifics of what you're designing. **Each entry is numbered for stable cross-reference; never renumber existing entries — only append.** Entries flagged with **[MUST]** are binding requirements, not heuristics — the reward-generator agent is required to follow them when authoring a new reward.

1. **For multi-step or long-horizon tasks, consider staging the reward and gating each stage on prior progress.** Splitting into reach → grasp → lift → align → place can help the policy learn one behaviour at a time, especially if each later stage multiplies in a `(prior_stage_complete)` factor so it only fires after the bootstrap behaviour is established. Useful when the task can be cleanly decomposed; not always necessary for short-horizon tasks.

2. **[MUST] Magnitude-budget discipline: per-step reward magnitudes MUST strictly increase from earlier stages to later stages, and the budget MUST be planned globally before any per-term tuning.** This consolidates the old #2 / #6 plus the iter-5 insert_drawer post-mortem (a state-B `align` amplified to ~248/step ended up dwarfing the latch `+500` and dense `close_drawer` `~900` ceilings, because each lever was tuned locally without checking the global balance). **Concrete starting budget for a manipulation chain (per-step value AT SATURATION, after weight × per-step output):**

    | Stage              | Per-step (saturated) | Notes                                              |
    |--------------------|----------------------|----------------------------------------------------|
    | reach              | **2 – 3**            | dense EE→object attractor; smallest budget         |
    | lift (binary + ramp)| **5 – 10**          | only after reach gradient saturates                |
    | align / approach   | **10 – 30**          | gated on lift-complete; bigger gradient than lift  |
    | place / release    | **30 – 100**         | gated on align; bigger still                       |

    Once dense values are placed on this ladder, sparse landmarks (one-shot bonuses, terminal success) MUST sit ABOVE the steady-state sum of all dense terms — a typical sparse bonus is an order of magnitude above `sum(dense_per_step) × episode_length` so the policy is incentivized to finish the task, not park in the dense-reward zone forever. **Levers (apply in this order):**
    - Pick a global per-step budget per stage from the table; back-compute weights given the per-step function shape (`1 - tanh(d/std)` saturates to 1.0, binary indicators saturate to 1.0, ramps saturate to 1.0). A `reach` term with shape `1 - tanh(d/std)` and target per-step 3.0 → `weight = 3.0`.
    - Gate every later-stage dense term by a prior-stage-complete predicate (multiplicative `(stage_k_done).float()` factor). Without the gate, the value function the late stage learns against is dominated by the steady-state early-stage baseline and the gradient is drowned.
    - Per-stage gate thresholds (e.g. `minimal_height_b` for an align gate) must be stricter than the prior stage's success threshold — a globally-permissive lift gate often lets a later stage drag its carried object horizontally through the earlier stage's geometry.

    The agent MUST write the planned per-stage budget into the §6 docstring BEFORE setting individual weights, so the global balance is auditable in code review.

3. **Try to keep the reward as simple as the task allows — fewer terms is usually better.** Every extra term is another local optimum to navigate. Often the minimum decomposition that physically describes the task (3–5 stages for typical manipulation) works fine, and adding extras like contact-sensor terms or "attempt" bonuses pays off only when a clean diagnosis points to a specific bootstrap failure.

4. **Inspecting each stage's reward separately per iteration is often the fastest way to find what's broken.** After a training run, look at `reward/<stage>/episodic_return_mean` per term, not just the total. The stage with the lowest mean-to-weight ratio is usually where the policy is stuck (gradient too sparse, gate too strict, bootstrap target too far) — and fixing that stage's signal tends to unlock more than re-weighting unrelated terms.

5. **When sub-tasks share structure, expose a shared observation interface muxed by a stage predicate** rather than every object's raw state. "Stack cube_0 on cube_1" and "stack cube_2 on cube_0" are the same operation against different operands — routing both through `grasping_cube_position` / `grasping_target_position` lets the policy learn the operation once instead of an attention switch over phases on top of the task itself.

6. **Pick the simplest controller the task allows, then clamp the action's reachable workspace to the actual extent.** For top-down pick-and-place, a 3-DOF EE-delta IK with locked RPY is enough; no need for full 6-DOF pose control. Add per-axis `pos_lower_limit` / `pos_upper_limit` to the cumulative-delta action term matching the object-spawn envelope plus a small margin. Keeps the IK numerically valid and shrinks the policy's action space; usually buys more than reward weight tuning.

7. **Obstacle-clearance gate on horizontal-attractor rewards.** When a payload must traverse OVER a vertical obstacle (drawer rim, container wall, tower) to reach its goal, gate the horizontal-attractor on `payload.z > obstacle_top_z + margin` (margin ≈ 2–5 cm), NOT just `payload.z > resting_z + ε`. Otherwise the policy drags the payload through the obstacle because the horizontal gradient outweighs the lift gradient at low z.

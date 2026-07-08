# task-library — cross-run task design knowledge

Append-only ledgers of reusable task-authoring knowledge, organized by embodiment + task family.
Sibling to the per-agent experience ledgers (`experiences/<agent>/*-experience.md`); this tree is
indexed by **what** is being built rather than **which agent** built it.

Use it when authoring a new task (`/harbor:task-create`) or designing reward / DR / observation
for one: read the matching leaf to reuse patterns proven on similar embodiments.

```
task-library/
├── manipulation/
│   ├── multi-arm-manipulation/    bimanual / dual-arm / multi-robot manipulation
│   └── single-arm-manipulation/   single-arm pick/place/insert/lift, in-hand
└── locomotion/
    ├── humanoid/                  bipedal humanoid locomotion
    └── quadrupedal/               quadruped locomotion
```

Each leaf is append-only and numbered for stable cross-reference — never renumber existing entries.
Promote a lesson here once it has helped author a second task in that category.

> **Reward weights are NOMINAL (no dt scale).** Every reward spec in this library was authored
> against a fork that removed the IsaacLab `RewardManager` `× step_dt` multiplier, so its `weight`
> values are nominal per-step magnitudes. When adapting a base into a stock fork that still applies
> `× dt`, carry the weights over **as-is** and cancel the scaling once in the env cfg's `__post_init__`
> (`weight /= step_dt`, per `references/reward-generator/isaaclab-reward-reference.md`'s
> `[MUST] Cancel the RewardManager dt scaling`). Do **not** re-scale the library weights by `1/dt`.

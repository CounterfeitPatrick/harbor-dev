# task-library — cross-run task design knowledge

Append-only ledgers of reusable task-authoring knowledge, organized by embodiment + task family.
Sibling to the per-agent experience ledgers (`knowledge/experiences/<agent>/*-experience.md`); this tree is
indexed by **what** is being built rather than **which agent** built it.

Use it when authoring a new task (`/harbor:task-create`) or designing reward / DR / observation
for one: read the matching leaf to reuse patterns proven on similar embodiments.

```
task-library/
├── manipulation/                 single- or multi-arm/bimanual pick/place/insert/lift/stack, in-hand
└── locomotion/
    ├── humanoid/                  bipedal humanoid locomotion
    └── quadrupedal/               quadruped locomotion
```

Each leaf is append-only and numbered for stable cross-reference — never renumber existing entries.
Promote a lesson here once it has helped author a second task in that category.

> **Reward weights are NOMINAL.** Every reward spec in this library declares nominal per-step
> `weight` magnitudes — carry them over **as-is** and apply them directly. The declared weight is
> exactly what each term pays per step.

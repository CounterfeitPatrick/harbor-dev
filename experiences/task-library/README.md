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

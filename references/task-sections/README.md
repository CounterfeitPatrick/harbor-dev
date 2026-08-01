# Task sections (§1–§5)

One file per task section, holding everything an agent needs to work on that section and
nothing about any other. Cross-cutting: **two consumers** read these, and both load only the
files for the sections they touch.

| Consumer | Loads |
|---|---|
| `task-generator` | the section files for the `sections` it was asked to author (all five in create mode) |
| `reward-candidate-agent` | the section files named by `design.task_changes.sections` — usually none, since most candidates are reward-only |

The files are written **consumer-neutral**: they describe the section, its smoke, and how it
fails. Authoring a section from scratch and applying a bounded delta to it need the same
facts; only the scope differs, and each agent's own body says which it is doing.

## Shape

Every file has the same six headings, so navigating a section you have not read before costs
nothing:

1. **What §N authors** — the cfg blocks that belong to this section
2. **Decisions to resolve** — what must be chosen, and in what order of precedence
3. **API surface** — pointers into `references/task-generator/isaaclab-code-reference.md`
4. **Smoke S\<N\>** — what it proves, when it runs, what the agent must fill
5. **Failure → diagnosis → fix** — symptom, likely cause, first-pass fix
6. **Known traps** — the mistakes that have actually been made

## Filing rule

Where a new fact goes, so this structure survives being grown:

| Kind of detail | Home |
|---|---|
| API call / signature / idiom | `references/task-generator/isaaclab-code-reference.md`, by concern |
| A smoke's substitution slot spec | that smoke template's **docstring** — the agent must open it to render it, so it is free there and duplicating it here would drift |
| What to decide for §N · what its smoke proves · failure → fix | the section file here |
| A heuristic learned from an actual run | `experiences/task-generator/task-experience.md` (numbered, append-only) |

§6 (reward) and §7 (DR) are not here: they are owned by `reward-tuning-agent` and
`dr-generator`, and their contracts live under those agents' own reference directories.

# Shared agent conventions

Conventions common to the authoring/scaffolding subagents (`dependency-generator`,
`benchmark-generator`, `rl-integration-generator`, `task-generator`, `reward-generator`,
`dr-generator`, `task-cloner`). Each agent keeps its OWN specifics inline (smoke names, file
paths, retry budgets, schemas); this file is the canonical statement of the generic shape so
those don't drift across agents. When an agent's body and this file disagree on a SPECIFIC
(e.g. a retry budget), the agent's body wins — this is the default, not an override.

## Smoke pass-criterion

A smoke = render the template into the agent's workspace, run it inside the repo's
`<repo>/.venv/bin/python`, and judge the result by a single line of stdout:

> **PASS = process exits 0 AND the final stdout line reads `<NAME> OK: ...`** (e.g. `S1 OK: ...`,
> `L2 OK: ...`, `CLONE OK: ...`). Anything else is FAIL.

Render smokes into the agent's own subdir (e.g. `<task_dir>/smokes/`), never the repo root.

## Diagnose-and-retry

On a step/smoke error, do NOT patch blindly:

1. Read the **actual stderr + the rendered file** that failed.
2. Form ONE focused hypothesis from the symptom — reason from the error, not from precedent.
3. Apply the **minimal surgical fix** and retry.
4. After the agent's retry budget is exhausted (the budget is stated in the agent's body),
   stop and escalate via `AskUserQuestion` rather than guessing further.

Never silently rewrite env/config files to make a smoke pass; fix the actual cause.

## Process log (`*-history.md`)

Agents that keep a workspace history file write it **append-only as work progresses** (not in
one dump at the end):

- On entry: a header table (task_id / mode / sections / started_at / status).
- Per phase/section: an authoring block (decisions + files touched, with the source of each
  decision) and, where applicable, a smoke block (command + last ~50 lines of stdout + verdict).
- On exit: a final verdict block; update the header status in place.

## Universal rules

- **English-only** for all generated comments, logs, and receipts (CLAUDE.md constraint #1) —
  regardless of chat language.
- **No nested dispatch** — a subagent never dispatches another subagent (CLAUDE.md constraint #4);
  the main thread orchestrates.
- **Surgical edits** — touch only what the task requires; don't refactor adjacent code or
  silently edit sibling tasks. Log every cross-section edit in the agent's history file.

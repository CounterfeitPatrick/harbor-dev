# Shared agent conventions

Conventions common to the authoring/scaffolding subagents (`dependency-generator`,
`benchmark-generator`, `rl-integration-generator`, `task-generator`, `reward-tuning-agent`,
`dr-generator`, `task-cloner`). Each agent keeps its OWN specifics inline (smoke names, file
paths, retry budgets, schemas); this file is the canonical statement of the generic shape so
those don't drift across agents. When an agent's body and this file disagree on a SPECIFIC
(e.g. a retry budget), the agent's body wins — this is the default, not an override.

## Smoke pass-criterion

A smoke = render the template into the agent's workspace, run it inside the repo's
`<repo>/.venv/bin/python`, and judge the result by a single line of stdout:

Smoke templates set `sys.stdout.reconfigure(line_buffering=True)`: a GPU-sim teardown can
kill the process before stdout flushes, and the verdict line IS the pass criterion — a
passing smoke that loses its line reads as a failure. Run them with `python -u` as well.

> **PASS = process exits 0 AND the final stdout line reads `<NAME> OK: ...`** (e.g. `S1 OK: ...`,
> `L2 OK: ...`, `CLONE OK: ...`). Anything else is FAIL.

Render smokes into the agent's own subdir (e.g. `<task_dir>/smokes/`), never the repo root.

### Smoke `num_envs` + indexing

`{{NUM_ENVS}}` is set per benchmark from `harbor/benchmark-generator/benchmark-spec.json:gpu_sim`:

- **gpu-sim (`gpu_sim == true`) → `2`.** Small enough to stay fast, ≥2 so per-env indexing
  bugs that hide at 1 env still surface. Render smokes render env 0.
- **non-gpu-sim → `1`.**

In an agent-filled check block, index `[0]` when comparing a scalar read — every env sees the
same point-interval reset at no-op DR, so any single env is representative. For batched
assertions use `torch.allclose` over the full `(NUM_ENVS, dim)` tensor.

### A smoke contract outranks a doc

Per-section smoke commands in a repo's `task-implementation.md` are reference material, not
the contract. Where the doc's smoke is weaker than the section's contract, use the contract
and (optionally) patch the doc surgically to match.

When a non-IsaacLab family is in play, substitute the family-equivalent API on the same
contract surface — the *checks* stay the same; the *call sites* differ.

## Diagnose-and-retry

On a step/smoke error, do NOT patch blindly:

1. Read the **actual stderr + the rendered file** that failed.
2. Form ONE focused hypothesis from the symptom — reason from the error, not from precedent.
3. Apply the **minimal surgical fix** and retry.
4. **Loop until it passes.** The exit condition is a passing smoke, not an exhausted counter.
5. Escalate via `AskUserQuestion` when the retry stops making progress — the agent's body states
   what that means for it (`task-generator`: two consecutive attempts that fail to move the
   measured quantity, or a 10-attempt backstop).

A retry that fails is not automatically a reason to stop; a retry that fails **the same way** is.
When a smoke reports a number — a residual, an overshoot, a frame-diff — that number is the
signal: still moving means the diagnosis is right and the fix was too small, unchanged twice
means the diagnosis is wrong and further attempts will not find it.

Never silently rewrite env/config files to make a smoke pass; fix the actual cause. In
particular, never make a smoke pass by weakening what it checks — a widened tolerance, a lowered
threshold, or a shortened settle time is not a fix, it is the failure with the alarm turned off.

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
- **Dispatch depth ≤ 2** (CLAUDE.md constraint #2). Exactly one agent carries the `Agent`
  tool — `reward-tuning-agent`, which dispatches `reward-candidate-agent`. Every other
  agent is a leaf and does its delegated work itself.
- **`AskUserQuestion` is unavailable inside a subagent** — Claude Code strips it whether or
  not the `tools:` list names it. An agent that needs a decision returns it to its caller
  (a `needs_decision` status plus enough context to ask), and the caller asks.
  *Migration status:* only `reward-tuning-agent` follows this. `dependency-generator`,
  `benchmark-generator`, `rl-integration-generator`, `task-generator`, `dr-generator`, and
  `rl-tuning-agent` still escalate through `AskUserQuestion`, so those escalation paths do
  not reach the user. Not yet fixed.
- **Surgical edits** — touch only what the task requires; don't refactor adjacent code or
  silently edit sibling tasks. Log every cross-section edit in the agent's history file.

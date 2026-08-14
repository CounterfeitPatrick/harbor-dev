# Authoring tasks

A task in HARBOR is authored in seven numbered sections, and each one is gated separately. That decomposition is deliberate: a reward can only be as good as the signals the task exposes, so the sections that define those signals are settled and verified before reward design begins.

| § | Section | What it settles |
|:--:|---|---|
| 1 | Register / scene | Assets, collisions, articulation limits, the gym id |
| 2 | Actions | What the action space can express, and whether the controller tracks it |
| 3 | Reset | The start-state distribution |
| 4 | Goal / termination | The success predicate and the subgoal decomposition |
| 5 | Observation | What a reward term is allowed to key on |
| 6 | Reward | The term ladder, validated by actual training |
| 7 | Domain randomization | Opt-in; skipped by default |

## Create a task

```text
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Franka panda pushes a 5 cm wooden block from the table center to a
               target marker. Success when block-to-marker xy distance < 5 cm;
               horizon 200 steps."
```

Pre-flight verifies the dependency → benchmark → RL-integration chain and dispatches any missing stage first. Then `task-generator` authors §1–§5, running that section's behavioral smoke after each one and looping until it passes.

The smoke loop is bounded by **progress, not attempts**: it escalates to you after two consecutive attempts that fail to move the measured quantity, rather than burning ten identical retries. It also escalates at a hard backstop of ten.

## What you get back

Each run writes a workspace under `harbor/create-task/<task-slug>/`:

| File | What it holds |
|---|---|
| `task-history.md` | The design record: per-section analysis of *why*, plus the validations that passed |
| `task-analysis.md` | The rationale half alone, with validations stripped — what reward design reads |
| `test-checklist.md` | Every check that actually ran, which is task-specific |
| `smokes/` | The rendered smoke scripts and the `verdict.json` each one wrote |
| `smoke_s{3,4,6}_frames/` | Reset layouts, per-predicate states, and rollout keyframes |

`task-history.md` is gated before the agent returns: every analysis term must be answered, every table cell filled, and every claimed verdict diffed against the smoke's own `verdict.json`. Transcription stops being load-bearing — the history reports machine truth, not the agent's recollection.

## Edit an existing task

Re-author individual sections surgically, leaving the rest untouched:

```text
/harbor:task-create name=Isaac-Push-Block-Franka-v0 sections=2,5 \
  description="Switch to EMA delta end-effector pose control; add object velocity
               to the observation."
```

## Reproduce a task elsewhere

Probe an existing task into a portable specification, then rebuild it in another benchmark:

```text
/harbor:probe-task task=Isaac-Insert-Drawer-Franka-v0
/harbor:task-create name=Genesis-Insert-Drawer-UR10-v0 \
  from=harbor/create-task/isaac-insert-drawer-implementation.md
```

The spec captures every design choice with verbatim code — scene, actions, reset, termination, observation, reward, and DR. In reproduce mode the reward is pasted verbatim at iteration 0 of the reward-tune loop and then validated by real training like any other candidate, because a reward that worked in one simulator's contact model is a hypothesis in the next one, not a guarantee.

This is the sim-to-sim path: the same task, adapted to a different simulator's APIs and physics, with intent preserved.

## Clone a task

For A/B variants or isolated editing:

```text
/harbor:task-clone op=create source=<TaskID> dest=<TaskID>-variant1
```

The clone copies only the editable surface, rewires imports, registers the new id, and runs build, rollout, and per-term-logging smokes. A manifest records every created file so `op=delete` reverses it cleanly. The source is never edited.

## Next

[Tune the reward →](/guide/rewards)

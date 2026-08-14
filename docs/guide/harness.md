# The harness

A harness is the structured execution environment around an agent: how it reaches tools, preserves state, observes feedback, and verifies progress. Long-horizon autonomy depends on it at least as much as on the model, because most failures are not reasoning failures — they are underspecified executions, where the agent lacked the abstractions and feedback to pursue a goal reliably.

Robot RL is an unusually good fit for this view. The MDP already gives you stable interfaces:

$$\mathcal{M} = (\mathcal{S}, \mathcal{A}, P, r, \rho_0, \gamma, T)$$

State and action spaces must match simulator observations and control interfaces. Dynamics are determined by assets, control frequency, and physical parameters. Every one of those is separately checkable — and simulators produce executable feedback for checking them.

HARBOR specializes the general harness pattern into five pieces:

$$\mathcal{H}_{\text{RL}} = (\mathcal{H}_A,\ \mathcal{C},\ \mathcal{M},\ \mathcal{G},\ \mathcal{K})$$

## Agents

Context-isolated subprocesses assigned to bounded stages. Each operates on stage-local artifacts and retrieved knowledge, does its own implementation, and returns a compact summary to its caller.

Isolation is the point. When a reward candidate fails a smoke test, the traceback, the log tail, and the failed frames belong to that candidate — not to the agent deciding what to try next. Dispatch depth is capped at two, and exactly one agent (`reward-tuning-agent`) dispatches workers of its own.

## Commands

Reproducible operations exposed to agents, from primitives like `rl-run` to composed loops like `reward-tune`. The same surface is invocable by different agents with different artifacts and gates — and by you, directly, which is what lets you assemble a workflow HARBOR does not ship.

## Artifacts

Workflow state externalized into persistent, inspectable objects. They are the communication substrate between agents, which reduces reliance on transient context.

This is what makes long runs survivable. A tuning loop checkpoints its state every iteration; a killed agent, an interrupted session, or a resumed conversation picks up from the file rather than from memory. It is also what makes the system auditable: the artifact is the same thing you would have written by hand.

## Gates

Executable checks that decide whether a stage may advance. [See the gate catalogue →](/guide/gates)

## Knowledge

Templates, references, scripts, human heuristics, and accumulated experience from previous runs. Knowledge constrains generation, encodes simulator- and algorithm-specific contracts, and gives later agents access to what earlier attempts learned.

It splits three ways. **Templates** are rendered into your repository. **References** are decision aids an agent loads only when it needs them — one file per task section, so an agent authoring the action space does not read the observation guide. **Experiences** are append-only ledgers that accumulate across runs.

## The execution protocol

Every stage runs the same way:

1. The main agent retrieves relevant knowledge and current artifacts
2. It spawns a stage-local agent with bounded context
3. That agent creates or edits artifacts through standardized commands
4. Gates evaluate the result
5. **Pass** → commit the artifact, write logs and metrics back into knowledge
6. **Fail** → return the failed check, error message, and observed values to the stage agent for repair
7. After a fixed retry budget, the stage is marked unresolved and you are asked to intervene

Step 6 matters more than it looks. The agent is handed a diagnosis — *which* check failed and *what value* it observed — not a stack trace to interpret.

## What this does and does not guarantee

HARBOR does not guarantee the semantic correctness of your final policy. No gate can prove the task you described is the task you meant.

What it does is turn a large class of RL engineering failures into **observable gate failures, before they propagate downstream**. A wrong action scale caught by an actuator tracking check costs ten minutes. The same bug caught after a twelve-hour training run costs a day, and is usually diagnosed as a reward problem.

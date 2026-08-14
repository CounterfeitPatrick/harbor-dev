# What is HARBOR?

HARBOR is a [Claude Code](https://claude.com/claude-code) plugin that automates the engineering pipeline around robot reinforcement learning. Given a simulator codebase and a task specification, it goes from an empty checkout to a trained policy: environment setup, task construction, reward design, algorithm integration, domain randomization, and hyperparameter tuning.

It is described in [*HARBOR: A Harness Framework for Agentic Robot Reinforcement Learning*](https://arxiv.org/abs/2606.08610).

## The problem it solves

The standard sim-to-real recipe is well established — build a digital twin, design rewards, randomize dynamics, train, deploy. What limits its adoption is not the algorithms but everything around them. A new setup routinely costs days to weeks of expert time, and almost none of that effort transfers to the next simulator.

Existing automation attacks one stage at a time: reward synthesis here, hyperparameter search there. Each reduces effort locally, and then you still configure the simulator by hand, connect the generated reward to training code by hand, launch and babysit sweeps by hand, and port successful design choices across tasks by hand.

## What makes it different

HARBOR is not a code generator with a robotics prompt. Three design choices separate it from a general coding agent:

**It is artifact-centric.** Workflow state lives in persistent files, not in a conversation. That is what lets a run survive a killed agent, a resumed session, or a twelve-hour training job — and what lets you open any intermediate result and read it.

**It is gated.** Each stage ends in an executable check that uses RL's own signals: does the environment import, do observations have the right shape, does the commanded pose match the achieved pose, does the reward decompose into terms that sum back to itself, do rendered frames actually differ from one another. A stage that cannot prove it worked does not advance.

**It is centralized in planning, decentralized in execution.** Iterative stages fan out into isolated parallel trials, so ten reward candidates can train simultaneously without any of their tracebacks reaching the context that decides what to try next.

## What you need

- A Python GPU robotics repository (IsaacLab, ManiSkill, Genesis, MJLab, Loco-MuJoCo, and others)
- An NVIDIA GPU with a working driver
- [`uv`](https://docs.astral.sh/uv/) on the host
- Claude Code 2.1.219 or newer

## Next steps

- [Install HARBOR](/guide/install)
- [Set up your first benchmark](/guide/first-benchmark)
- [Understand the harness](/guide/harness)

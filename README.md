<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo/harbor-lockup-dark.svg">
  <img src="assets/logo/harbor-lockup-light.svg" alt="HARBOR" width="330">
</picture>

### Point it at a simulator. Describe a task. Get a trained policy.

HARBOR automates robot reinforcement learning from an engineering workflow into a request.<br>
It sets up the simulation, writes the task, designs the reward, wires the algorithm,<br>
trains the policy — and checks its own work at every step.

[![arXiv](https://img.shields.io/badge/arXiv-2606.08610-b31b1b?style=flat-square&logo=arxiv&logoColor=white)](https://arxiv.org/abs/2606.08610)
[![Docs](https://img.shields.io/badge/docs-online-0FB6C9?style=flat-square)](https://supersglzc.github.io/harbor-dev)
[![License](https://img.shields.io/badge/license-Apache%202.0-0FB6C9?style=flat-square)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-plugin-6C4BF6?style=flat-square)](https://claude.com/claude-code)
[![Tests](https://img.shields.io/github/actions/workflow/status/supersglzc/harbor-dev/test.yml?style=flat-square&label=tests)](../../actions)

**[Quickstart](#quickstart)** · **[Gallery](#gallery)** · **[Inside HARBOR](#inside-harbor)** · **[Docs](https://supersglzc.github.io/harbor-dev)** · **[Paper](https://arxiv.org/abs/2606.08610)** · **[Cite](#citation)**

<br>

<img src="assets/hero/walkthrough.webp" alt="One prompt drives all six stages, from dependency setup to a trained G1 jumping policy" width="860">

</div>

## What is HARBOR

Reinforcement learning works. The pipeline around it is what costs weeks — building the task, shaping the reward, calibrating randomization, tuning hyperparameters, and re-doing all of it for the next simulator.

HARBOR is a **harness**: a structured execution environment that decomposes that pipeline into bounded stages, hands each to a specialized agent, and refuses to advance until an **executable gate** proves the stage actually worked. Rollouts, reward curves, and rendered video are the evidence. Nothing is taken on the agent's word.

The result is not a black box. Every stage writes inspectable artifacts — code, configs, logs, checkpoints, video — and pauses at a gate you can audit, correct, and resume from.

```
prompts ──▶ dependency ──▶ RL integration ──▶ task ──▶ reward ──▶ DR ──▶ training ──▶ policy
                    │            │              │         │        │          │
                    └────────────┴──────────────┴─────────┴────────┴──────────┘
                                  every arrow is a gate that can fail
```

<a id="gallery"></a>

## One harness, different tasks · robots · simulators

The same task descriptions, given to HARBOR against different simulator codebases. It adapts to each one's APIs, asset formats, and contact model while preserving the task and reward intent — and the harness is embodiment-agnostic, so whole-body locomotion goes through exactly the same pipeline as tabletop manipulation.

<table>
<tr>
  <th align="left" width="118">&nbsp;</th>
  <th align="center">IsaacLab</th>
  <th align="center">ManiSkill</th>
  <th align="center">Genesis</th>
</tr>
<tr>
  <td><b>Stack&#8209;Cube</b><br><sub>long-horizon<br>composition</sub></td>
  <td><img src="assets/gallery/stack-cube__isaaclab.webp" width="180" alt="Stack-Cube in IsaacLab"></td>
  <td><img src="assets/gallery/stack-cube__maniskill.webp" width="180" alt="Stack-Cube in ManiSkill"></td>
  <td><img src="assets/gallery/stack-cube__genesis.webp" width="180" alt="Stack-Cube in Genesis"></td>
</tr>
<tr>
  <td><b>Insert&#8209;Drawer</b><br><sub>articulated<br>interaction</sub></td>
  <td><img src="assets/gallery/insert-drawer__isaaclab.webp" width="180" alt="Insert-Drawer in IsaacLab"></td>
  <td><img src="assets/gallery/insert-drawer__maniskill.webp" width="180" alt="Insert-Drawer in ManiSkill"></td>
  <td><img src="assets/gallery/insert-drawer__genesis.webp" width="180" alt="Insert-Drawer in Genesis"></td>
</tr>
<tr>
  <td><b>Lift&#8209;Box</b><br><sub>bimanual<br>coordination</sub></td>
  <td><img src="assets/gallery/lift-box__isaaclab.webp" width="180" alt="Lift-Box in IsaacLab"></td>
  <td><img src="assets/gallery/lift-box__maniskill.webp" width="180" alt="Lift-Box in ManiSkill"></td>
  <td><img src="assets/gallery/lift-box__genesis.webp" width="180" alt="Lift-Box in Genesis"></td>
</tr>
<tr>
  <td><b>Hang&#8209;Mug</b><br><sub>precise<br>placement</sub></td>
  <td><img src="assets/gallery/hang-mug__isaaclab.webp" width="180" alt="Hang-Mug in IsaacLab"></td>
  <td><img src="assets/gallery/hang-mug__maniskill.webp" width="180" alt="Hang-Mug in ManiSkill"></td>
  <td><img src="assets/gallery/hang-mug__genesis.webp" width="180" alt="Hang-Mug in Genesis"></td>
</tr>
<tr>
  <td><b>Dex&#8209;Grasp</b><br><sub>dexterous<br>control</sub></td>
  <td><img src="assets/gallery/dex-grasp__isaaclab.webp" width="180" alt="Dex-Grasp in IsaacLab"></td>
  <td><img src="assets/gallery/dex-grasp__maniskill.webp" width="180" alt="Dex-Grasp in ManiSkill"></td>
  <td><img src="assets/gallery/dex-grasp__genesis.webp" width="180" alt="Dex-Grasp in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Jump</b><br><sub>whole-body<br>dynamics</sub></td>
  <td><img src="assets/gallery/g1-jump__isaaclab.webp" width="180" alt="G1 Jump in IsaacLab"></td>
  <td><img src="assets/gallery/g1-jump__maniskill.webp" width="180" alt="G1 Jump in ManiSkill"></td>
  <td><img src="assets/gallery/g1-jump__genesis.webp" width="180" alt="G1 Jump in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Footstep</b><br><sub>contact<br>scheduling</sub></td>
  <td><img src="assets/gallery/g1-footstep__isaaclab.webp" width="180" alt="G1 Footstep in IsaacLab"></td>
  <td><img src="assets/gallery/g1-footstep__maniskill.webp" width="180" alt="G1 Footstep in ManiSkill"></td>
  <td><img src="assets/gallery/g1-footstep__genesis.webp" width="180" alt="G1 Footstep in Genesis"></td>
</tr>
</table>

## Quickstart

### 1. Install

HARBOR is a [Claude Code](https://claude.com/claude-code) plugin. It needs one host-side tool — [`uv`](https://docs.astral.sh/uv/) — plus an NVIDIA driver and, if your simulator builds CUDA extensions, the CUDA toolkit.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
uv --version && nvidia-smi     # both should print
```

Then, inside Claude Code:

```text
/plugin marketplace add supersglzc/harbor-dev
/plugin install harbor@harbor
```

`/harbor:help` lists the full surface. See the [installation guide](https://supersglzc.github.io/harbor-dev/guide/install) for the scripted path and troubleshooting.

### 2. Ask HARBOR to build a task

Point HARBOR at any Python GPU robotics repository and describe what you want. It handles the rest.

```text
Set up the env for https://github.com/isaac-sim/IsaacLab, then create a task where
a Franka pushes a 5 cm block to a target marker. Success is block-to-marker
distance under 5 cm.
```

<details>
<summary><b>What a full run produces</b></summary>

```
<your-repo>/
├── .venv/                                  uv-managed environment
└── harbor/
    ├── dependency-generator/               setup_uv.sh, probe.json, install.md
    ├── benchmark-generator/                benchmark-spec.json, benchmark.md, task_overview.md
    ├── rl-integration-generator/           rl-suite-spec.json, rl-integration.md
    ├── create-task/<task>/                 task-history.md, test-checklist.md, smokes/, keyframes
    ├── scripts/rl/<impl>/                  train.py, eval.py, render.py, env_wrapper.py
    ├── configs/rl/                         ppo.yaml, sac.yaml, td3.yaml
    └── outputs/<algo>_<task>_<ts>/         checkpoint, metrics.jsonl, curves/, render.mp4
```

Every one of those files is meant to be read, edited, and re-run by hand.

</details>

### 3. Run the stages manually

You can also drive each stage yourself:

```text
/harbor:env-install-uv                     # probe deps, build .venv/, run the import smoke
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
    description="Franka pushes a 5 cm wooden block to a target marker; \
                 success when xy distance < 5 cm; horizon 200 steps."
/harbor:rl-run task=Isaac-Push-Block-Franka-v0 algorithm=ppo
/harbor:rl-render checkpoint=harbor/outputs/ppo_Isaac-Push-Block-Franka-v0_.../checkpoint.pt
```

Everything HARBOR generates lands inside the target repository under `harbor/`, so a second benchmark is just the same pipeline run again.

## Inside HARBOR

HARBOR is both an **end-to-end robot RL workflow** and a **structured agentic harness**. The first defines what it can do; the second defines how it does that work reliably.

### Capabilities

HARBOR covers the workflow from an existing simulator repository and a task request to a trained, evaluated policy.

| Stage | What HARBOR handles |
|:--|:--|
| **Environment setup** | Probes the target repository, resolves dependencies, builds an isolated environment, and verifies that the simulator can import and run. |
| **Task construction** | Turns a natural-language task description into simulator-native task code, observations, termination conditions, success criteria, and executable smoke tests. |
| **Reward design** | Builds reward functions, trains candidate policies, inspects learning signals and rendered behavior, and iterates when the reward produces the wrong behavior. |
| **RL integration** | Connects the task to a reproducible training stack with algorithm configs, wrappers, logging, checkpointing, evaluation, and rendering. |
| **Domain randomization** | Adds and tunes simulation randomization while checking that the resulting task remains physically valid and learnable. |
| **Training & tuning** | Runs training, diagnoses failures from metrics and rollouts, tunes rewards or RL settings, evaluates checkpoints, and renders final policies. |

The same workflow applies across manipulation, dexterous control, and whole-body locomotion. You can ask HARBOR to run it end to end, or invoke individual stages and commands yourself.

### Architecture

HARBOR specializes a general agentic harness to robot RL as five interacting pieces:

| | |
|:--|:--|
| **Agents** | Context-isolated subprocesses, each owning one bounded stage. They read stage-local artifacts, do the work, and return a compact summary — implementation noise never reaches the context making decisions. |
| **Commands** | Reproducible operations, from primitives like `rl-run` to composed loops like `reward-tune`. The same surface is callable by any agent, or by you. |
| **Artifacts** | Workflow state externalized into persistent files. They are the communication substrate between agents, which is what lets a run survive a killed agent or a resumed session. |
| **Gates** | Executable checks that decide whether a stage may advance — import checks, rollout shape checks, actuator tracking error, reward-composition assertions, frame-difference render checks. A failed gate returns a diagnosis, not a stack trace. |
| **Knowledge** | Templates, references, and an append-only experience ledger that accumulates across runs, so the second task of a kind is much cheaper than the first. |

The property that matters: HARBOR cannot guarantee your policy is semantically correct. What it does is **turn common RL engineering failures into gate failures that surface before they propagate downstream** — the difference between a bug caught early and one discovered after a long training run.

HARBOR ships **23 commands** and **9 agents**. See the full **[command reference →](https://supersglzc.github.io/harbor-dev/guide/commands)** and **[agent reference →](https://supersglzc.github.io/harbor-dev/guide/agents)** for their arguments, roles, tools, and source definitions.

## Documentation

| | |
|:--|:--|
| [Getting started](https://supersglzc.github.io/harbor-dev/guide/) | Install, first benchmark, first task. |
| [Concepts](https://supersglzc.github.io/harbor-dev/guide/harness) | Agents, commands, artifacts, gates, knowledge — and why the harness is shaped this way. |
| [Command reference](https://supersglzc.github.io/harbor-dev/guide/commands) | Every command, generated from the plugin source. |
| [Agent reference](https://supersglzc.github.io/harbor-dev/guide/agents) | Every agent, its tools, and its contract. |
| [Authoring tasks](https://supersglzc.github.io/harbor-dev/guide/tasks) | Create a task, edit one section, or reproduce a task in another simulator. |
| [Tuning rewards](https://supersglzc.github.io/harbor-dev/guide/rewards) | How the candidate search works, and why it trains every candidate for real. |
| [`CLAUDE.md`](CLAUDE.md) | The architecture in full: the six-layer model and where a new module belongs. |

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The fastest way to help is to run HARBOR on a simulator we have not covered and file what broke: the harness improves by accumulating exactly that kind of experience.

## Citation

```bibtex
@article{li2026harbor,
  title   = {HARBOR: A Harness Framework for Agentic Robot Reinforcement Learning},
  author  = {Li, Zechu and Jin, Yufeng and Liu, Xiaoyang and Liu, Puze and
             Prasad, Vignesh and D'Eramo, Carlo and Chalvatzaki, Georgia},
  journal = {arXiv preprint arXiv:2606.08610},
  year    = {2026}
}
```

## License

[Apache 2.0](LICENSE). Copyright 2026 The HARBOR Authors.

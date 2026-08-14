# Your first benchmark

Setting up a benchmark means three stages, in order: build the environment, prove the environment actually runs, and render the training stack against it. HARBOR can run all three from one sentence, or you can drive them individually.

## The one-sentence path

Clone a repository, open Claude Code in it, and ask:

```text
Set up the env for https://github.com/isaac-sim/IsaacLab
```

HARBOR chains the three stages and stops at the first gate that fails.

## The explicit path

### 1. Environment

```text
/harbor:env-install-uv
```

The `dependency-generator` agent probes the repository — README, `pyproject.toml`, extras, CUDA requirements — builds an installation plan, renders it as `harbor/dependency-generator/setup_uv.sh`, executes it to create `.venv/`, and runs an import smoke test.

**Gate:** the package imports and the expected device is visible.

### 2. Sanity

The `benchmark-generator` agent renders two entry points at your repository root — `scripts/run_random.py` and `scripts/render_random.py` — and runs a two-tier smoke: a random-action rollout, then a render to MP4.

**Gate:** a rollout completes with finite rewards and correct shapes, and the rendered frames differ from one another. That second check is what catches a silently frozen scene, which a scalar return will happily hide.

It also captures `harbor/benchmark-generator/benchmark-spec.json`, the task inventory everything downstream reads.

### 3. Training stack

The `rl-integration-generator` agent renders the RL tree:

```
harbor/scripts/rl/<impl>/{train,eval,render,env_wrapper}.py
harbor/configs/rl/{ppo,sac,td3}.yaml
harbor/rl-integration-generator/rl-suite-spec.json
```

Three algorithm sources are available. `custom_torch` is the default: a self-contained algorithm tree shipped with the plugin, so there is no external RL library to pip-install and fight with. `stable_baseline3` wraps SB3. `local_implementation` wires up your own package or a GitHub URL through thin shims.

**Gate:** each algorithm passes a five-tier smoke — a short training run that produces a checkpoint, metrics, curves, and a render — using the same code paths production runs use.

## Train something

```text
/harbor:rl-run task=<task-id> algorithm=ppo
```

Artifacts land in `harbor/outputs/<algo>_<task>_<timestamp>/`: a checkpoint, `metrics.jsonl`, TensorBoard logs, plotted curves, and `render.mp4`. On success the final checkpoint is rendered automatically.

To see what tasks are available:

```text
/harbor:task-list
```

## What is now in your repository

```
<your-repo>/
├── .venv/
├── scripts/{run_random,render_random,_<family>_env}.py
└── harbor/
    ├── dependency-generator/    setup_uv.sh, probe.json, install.md
    ├── benchmark-generator/     benchmark-spec.json, benchmark.md, task_overview.md
    ├── rl-integration-generator/ rl-suite-spec.json, rl-integration.md
    ├── scripts/rl/ · configs/rl/ · utils/
    └── outputs/
```

Everything is plain Python and YAML, meant to be read and edited. See [your workspace](/concepts/workspace) for the full map.

## Next

[Author a task →](/guide/tasks)

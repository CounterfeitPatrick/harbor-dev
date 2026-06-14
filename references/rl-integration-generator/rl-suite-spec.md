# RL Suite Spec

Schema for `<repo>/harbor/rl-integration-generator/rl-suite-spec.json` — written by `rl-integration-generator`, consumed by `rl-tuning-agent` and the RL training/tuning commands (`/harbor:rl-run`, `/harbor:rl-eval`, `/harbor:rl-sweep`, `/harbor:rl-tune`).

## Lifecycle

```
benchmark-generator  →  harbor/benchmark-generator/benchmark-spec.json   (category, tasks, language, gpu_sim, …)
rl-integration-gen   →  harbor/rl-integration-generator/rl-suite-spec.json    (algorithm source, algorithms, W&B, scoring)
rl-tuning-agent      →  harbor/rl_experiments/tunes/<tune_id>/      (per-cell tune state)
write_rl_report.py   →  rl_experiment_report.md         (end-of-run user-facing receipt)
```

## Schema (v1)

```json
{
  "schema_version": 1,
  "benchmark": {
    "name": "<benchmark name from registry or repo dir>",
    "repo_path": "/abs/path/to/<repo>",
    "category": "rl"
  },
  "tasks": [
    {
      "id": "<task id, e.g. Cartpole-v1 or Ant>",
      "make": "gymnasium.make | isaacgymenvs.make | ...",
      "max_episode_steps": 200,
      "success_metric": "success | null",
      "reward_metric": "episode_return"
    }
  ],
  "algorithm_source": {
    "kind": "custom-torch | stable-baselines3 | custom-library | custom-path",
    "package": "stable-baselines3[extra] | <import path> | <absolute path>",
    "parallel": true
  },
  "algorithms": {
    "ppo": { "class": "PPO", "config": "configs/rl/ppo.yaml" },
    "sac": { "class": "SAC", "config": "configs/rl/sac.yaml" },
    "td3": { "class": "TD3", "config": "configs/rl/td3.yaml" }
  },
  "logging": {
    "wandb": {
      "enabled": true,
      "project": "harbor-rl",
      "entity": null,
      "mode": "online | offline | disabled"
    },
    "local_dir": "harbor/rl_experiments"
  },
  "selection_metric": {
    "primary": "success_rate",
    "secondary": "eval_return_mean",
    "tertiary": "sample_efficiency",
    "stability_weight": 0.05
  },
  "training_defaults": {
    "timesteps_per_trial": 100000,
    "eval_episodes": 10,
    "n_envs_cpu": 8,
    "n_envs_gpu": 4096,
    "seed": null
  }
}
```

## Field notes

- **`benchmark.category`** — always `"rl"`. benchmark-generator no longer detects IL vs RL — every benchmark reaching the RL stack is treated as RL.
- **`tasks[].success_metric`** — name of the boolean key in the env's `info` dict that signals episode success. `null` for benchmarks where success is not defined (in which case scoring falls back to `eval_return_mean`).
- **`algorithm_source.kind`**
  - `custom-torch` — self-contained PyTorch implementations under `templates/rl-integration-generator/algorithms/custom/` (GPU-parallel, hydra-config). Implies `parallel=true`.
  - `stable-baselines3` — `templates/rl-integration-generator/algorithms/stable-baseline3/` (CPU vec-env, gym vec). Implies `parallel=false` unless the env itself batches.
  - `custom-library` — user-provided pip-installable package; `package` is the import path (e.g. `cleanrl`).
  - `custom-path` — absolute path on disk; `rl-integration-generator` mounts it into the rl container.
- **`algorithm_source.parallel`** — drives which config family is selected by `algorithm_adapters.py`:
  - `true` → `configs/rl/<algo>.parallel.yaml` (GPU-batched parallel envs)
  - `false` → `configs/rl/<algo>.yaml` (gym vec-env, CPU)
- **`selection_metric`** — used by `analyze_rl_trial.py` and `suggest_hparams.py`. Scoring formula:
  ```
  score = 0.50 * normalized_success_rate
        + 0.30 * normalized_eval_return
        + 0.15 * normalized_sample_efficiency
        - 0.05 * instability_penalty
  ```
  If `tasks[].success_metric == null` for ALL tasks, success-rate term is dropped and weights re-normalize to `0.60 / 0.30 / -0.10` (eval_return / sample_efficiency / instability).

## Benchmark-spec extension

`benchmark-generator` writes `harbor/benchmark-generator/benchmark-spec.json`. To support the RL training/tuning surface, the spec must include:

```json
{
  "category": "rl",
  "language": "pytorch | jax",
  "gpu_sim": true,
  "tasks": [
    { "id": "Ant", "reward_implemented": true, "max_episode_steps": 1000 }
  ]
}
```

If `tasks[]` is missing or `category != "rl"`, `rl-integration-generator` refuses to proceed.

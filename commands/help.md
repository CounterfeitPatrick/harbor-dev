---
description: Show the full harbor plugin surface — slash commands, subagents, MCP tools, hooks. Use when the user types /harbor:help or asks "what can harbor do", "harbor help", "harbor overview", "list harbor features", "list harbor commands".
---

# /harbor:help — Plugin Overview

The user wants a tour of everything this plugin offers. **Print the static block below verbatim**, then append a live registry-count line fetched from MCP. Do not paraphrase the static block — it is the canonical surface description.

## Action

1. Print the static block (everything between the `BEGIN STATIC` and `END STATIC` markers below) verbatim, omitting the markers themselves.
2. Call `mcp__plugin_harbor_harbor__list_benchmarks` (no args).
3. Append a final line: `Current registry: <B> verified benchmark(s).` using the `count` field from the response.

---

<!-- BEGIN STATIC -->

**harbor** — Set up Python GPU repos with uv and curate verified benchmark entries. Team-internal plugin.

## Slash commands

| Command | What it does |
|---|---|
| `/harbor:help` | This overview. |
| `/harbor:benchmark` | Browse the benchmark registry (default lists verified). |
| `/harbor:benchmark list [verified\|unverified\|all]` | Filter listing by status. |
| `/harbor:benchmark submit` | Interactively register a new benchmark with `status: unverified`. Writes yaml + prints git commands; you push and open the PR yourself. |
| `/harbor:benchmark verify <name>` | Maintainer: flip status to `verified`, auto-fill `image_id` + `size` from `docker image inspect`. |
| `/harbor:rl-run task=<id> algorithm=<algo> [k=v ...]` | Train one trial. Wraps `harbor/scripts/rl/<impl>/train.py` with the repo's `<repo>/.venv/bin/python` and Hydra overrides. |
| `/harbor:rl-eval checkpoint=<path> [k=v ...]` | Evaluate a single trained checkpoint (unbiased steady-state aggregate). Auto-infers task and algorithm from saved config. Writes `metrics.json` next to checkpoint. |
| `/harbor:rl-visualize checkpoint=<path> [k=v ...]` | Open a HEADED GLFW viewer (CPU MuJoCo backend, custom_jax only) for a trained agent. Requires `$DISPLAY`. |
| `/harbor:rl-sweep task=<list> algorithm=<list> [k=v1,v2,...]` | Cartesian-product sweep — each combination dispatches a sub-agent that runs `/harbor:rl-run`. Per-trial dirs under `harbor/rl_experiments/sweeps/<sweep_id>/`. |
| `/harbor:rl-tune task=<list> algorithm=<list> [mode=local\|cluster]` | Cartesian-product grid TUNING. One `rl-tuning-agent` subagent per cell (open-ended hyperparameter loop). Tune-level history.md + final cross-cell summary under `harbor/rl-experiment/<tune_id>/`; each cell's per-cell state at `<tune_id>/<wandb_project>/`. |
| `/harbor:wandb-setup` | Inspect / re-login / logout the host's Weights & Biases credentials (`~/.netrc`). Used to switch accounts before / between rl-integration runs. |

## Skills (description auto-load)

| Skill | When |
|---|---|
| `karpathy-guidelines` | Code-writing rules; auto-loaded whenever you write or review code. |
| `add-data-logger` | Drop a parameterized `data_logger.py` (TensorBoard / W&B) into a target Python project. |
| `rl-metrics-logging` | Canonical metric-key contract (PPO / SAC / TD3 + per-reward-term + SB3 callback remap) for every algorithm under `harbor/scripts/rl/<impl>/`. Auto-loaded by `rl-integration-generator`. |

## Subagents (heavy, multi-step work; main thread dispatches)

Invoke via `Task('<agent-name>')`. Subagents do not nest-dispatch — main thread orchestrates.

| Agent | Purpose |
|---|---|
| `env-generator` | **Entry point** for any "set up env for \<repo\>" task. Probes the repo, renders `harbor/setup_uv.sh`, creates `<repo>/.venv/`, runs import smoke test, classifies as `benchmark` / `plain`, returns to main. |
| `benchmark-generator` | After env-generator returns `benchmark`. Renders `scripts/{run_random,render_random}.py`, runs 2-tier smoke (L1 random / L2 render), captures suite spec into `harbor/benchmark-spec.json`. Training scaffolding is owned by `rl-integration-generator` (dispatched directly as a subagent once the spec is written). |
| `rl-integration-generator` | After benchmark-generator finishes. Renders `harbor/scripts/rl/<impl>/{train,eval,render,env_wrapper}.py`, `harbor/configs/rl/{ppo,sac,td3}{,.parallel}.yaml`, and `harbor/rl-suite-spec.json`. Smokes each algorithm. |
| `rl-tuning-agent` | Per-algorithm hyperparameter tuning loop: train → eval → render → analyze metrics + behavior → suggest next config. Writes per-trial records under `harbor/rl_experiments/runs/<trial_id>/` and best-config picks under `harbor/rl_experiments/best/<algo>/`. |

## MCP tools (read-only registry access)

Server: `mcp/harbor/server.py`. Exposed under the `mcp__plugin_harbor_harbor__*` namespace.

| Tool | Returns |
|---|---|
| `list_benchmarks(status?, category?)` | `{count, benchmarks, formatted_table}`. Default `status="verified"`; pass `null` for all. |
| `lookup_benchmark(name_or_url)` | by name **or** github URL (fork-tolerant fuzzy match). `{found, benchmark?, match_type?}`. |
| `get_benchmark_spec(name)` | obs / action layout JSON. |
| `list_tasks(benchmark_name?)` | per-task metadata across registry benchmark specs. |

The MCP server has **no write API**. Registry mutation goes through `scripts/registry/registry_submit.py` and `registry_verify.py`, which produce yaml diffs reviewed in git.

## Lifecycle hooks

| Hook | Effect |
|---|---|
| `SessionStart` | Inject one line: `[harbor] benchmarks=N verified \| last update=<date>`. |
| `PostToolUse` | Truncate noisy Bash stdout to keep the conversation lean. |
| `Stop` / `SubagentStop` | Append a one-line audit entry. |

## Where to learn more

- `README.md` — architecture, layout, prerequisites, contribution flow.
- `CLAUDE.md` — 6-layer mental model + "where things live".
- `agents/<name>.md` — each subagent's contract, phase breakdown, exit-code semantics.
- `references/{env,benchmark,rl-integration}-generator/` — decision matrices, smoke contracts, install-plan schema, RL suite spec, decision protocol.
- `mcp/harbor/data/benchmarks.yaml` — the live registry (read via MCP, never `cat` directly).

<!-- END STATIC -->

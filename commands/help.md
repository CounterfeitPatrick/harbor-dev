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

Grouped by prefix: `env-*` · task (`task-*`/`probe-*`) · `reward-*` · `rl-*` · utilities.

| Command | What it does |
|---|---|
| `/harbor:help` | This overview. |
| **env** | |
| `/harbor:env-install-uv [path]` | Set up an isolated `.venv/` for a GPU repo via uv; renders `harbor/dependency-generator/setup_uv.sh`, runs the import smoke, then dispatches `benchmark-generator`. |
| **task** | |
| `/harbor:probe-benchmark [repo=<path>]` | Author the family-level `create-task/task-implementation.md` guide for a benchmark repo. |
| `/harbor:probe-task task=<id> [output=<path>]` | Emit a portable per-task spec (verbatim §1–§7 code). Runs in a subagent to save context. |
| `/harbor:task-create name=<TaskID> (description=… \| from=<spec.md>)` | Author a NEW task, or reproduce one from a probe-task spec. Auto-bootstraps missing prerequisites (dependency-generator → benchmark-generator → rl-integration-generator, defaulting to custom_torch), then runs task-generator (§1–§5) → the reward-tune training loop (§6) → dr-generator (§7, opt-in — skipped unless DR is explicitly requested). |
| `/harbor:task-list [<task-id>]` | List / inspect tasks in the cwd-local benchmark (falls back to the registry via `list_tasks`). |
| `/harbor:task-clone op=create source=<id> dest=<id>` | Clone a task into an isolated, independently-editable copy under a new suffixed gym id (delete with `op=delete`). The collision-free isolation primitive behind parallel reward-tune candidates. |
| **reward** | |
| `/harbor:reward-tune task=<id> [algorithm=<algo>] [pool_size=N] [mode=local\|cluster]` | Async-pool §6 reward tuning. Main agent decides each candidate's full reward spec; reward-generator writes it onto a task clone; train+render+score; repeat until success. `pool_size>1` runs candidates in parallel, each on its own clone. |
| `/harbor:reward-add-log` | Wire per-reward-term decomposition into a benchmark repo without changing the env's native reward — asserts `composer(terms) == reward` every step. |
| **rl** | |
| `/harbor:rl-run task=<id> algorithm=<algo> [k=v ...]` | Train one trial. Wraps `harbor/scripts/rl/<impl>/train.py` with the repo's `<repo>/.venv/bin/python` and Hydra overrides. |
| `/harbor:rl-eval checkpoint=<path> [k=v ...]` | Evaluate a single trained checkpoint. Auto-infers task and algorithm from saved config. Writes `metrics.json` next to checkpoint. |
| `/harbor:rl-render checkpoint=<path> [k=v ...]` | Render a checkpoint to MP4 with inference-moved + frame-difference sanity checks. |
| `/harbor:rl-visualize checkpoint=<path> [k=v ...]` | Open a HEADED GLFW viewer for a trained agent. Requires `$DISPLAY`. |
| `/harbor:rl-sweep task=<list> algorithm=<list> [k=v1,v2,...]` | Cartesian-product sweep — each combination dispatches a sub-agent that runs `/harbor:rl-run`. |
| `/harbor:rl-tune task=<list> algorithm=<list> [mode=local\|cluster]` | Cartesian-product grid TUNING. One `rl-tuning-agent` subagent per cell (open-ended hyperparameter loop). |
| `/harbor:rl-add-trick <trick> [algorithm=<algo>]` | Apply an RL training trick to a chosen algorithm config in-place. |
| `/harbor:rl-list-tricks` | List available RL training tricks with descriptions + applicability (read-only). |
| `/harbor:rl-add-log` | Print the canonical metric-key contract every algorithm under `harbor/scripts/rl/<impl>/` must emit. |
| **utilities** | |
| `/harbor:plot spec=<yaml>` | Multi-panel mean±std W&B learning curves grouped by task × baseline. |
| `/harbor:wandb-setup` | Inspect / re-login / logout the host's Weights & Biases credentials (`~/.netrc`). |
| `/harbor:update-experience target=<name> (experience="…" \| file=<path>)` | Append a numbered bullet to an agent experience ledger (≤5-line hand-written bullets), or file a probe-task spec into the right `task-library/` embodiment folder. |

## Subagents (heavy, multi-step work; main thread dispatches)

Invoke via `Task('<agent-name>')`. Subagents do not nest-dispatch — main thread orchestrates.

| Agent | Purpose |
|---|---|
| `dependency-generator` | **Entry point** for any "set up env for \<repo\>" task. Probes the repo, renders `harbor/dependency-generator/setup_uv.sh`, creates `<repo>/.venv/`, runs import smoke test, returns to main. |
| `benchmark-generator` | After dependency-generator finishes. Renders `scripts/{run_random,render_random}.py`, runs 2-tier smoke (L1 random / L2 render), captures suite spec into `harbor/benchmark-generator/benchmark-spec.json`. Training scaffolding is owned by `rl-integration-generator` (dispatched directly as a subagent once the spec is written). |
| `rl-integration-generator` | After benchmark-generator finishes. Renders `harbor/scripts/rl/<impl>/{train,eval,render,env_wrapper}.py`, `harbor/configs/rl/{ppo,sac,td3}{,.parallel}.yaml`, and `harbor/rl-integration-generator/rl-suite-spec.json`. Smokes each algorithm. |
| `rl-tuning-agent` | Per-algorithm hyperparameter tuning loop: train → eval → render → analyze metrics + behavior → suggest next config. Per-cell tune state under `harbor/rl_experiments/tunes/<tune_id>/<wandb_project>/`. |

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

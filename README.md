# harbor

A Claude Code plugin for **setting up Python GPU robotics repos with uv** and **tracking verified benchmark entries**.

Give Claude a GitHub URL of a robotics repo → it clones, generates `harbor/setup_uv.sh`, creates `<repo>/.venv/`, classifies the repo (benchmark / plain), and dispatches a specialized sub-agent to add the next layer (sanity scripts, RL training tree). A maintainer-curated MCP registry powers the `/benchmark` slash command so reproducing a verified entry is just *clone + run setup_uv.sh*.

## Prerequisites

The plugin needs one host-side tool. It is independent of Claude Code itself.

| Tool | Why harbor uses it | Sudo needed? |
|---|---|---|
| **`uv`** | Drives `harbor/setup_uv.sh` (the env-generator output) and the MCP server's bootstrap (`uv run --no-project --with mcp[cli] --with pyyaml`) | no |

You also need a working **NVIDIA driver** (`nvidia-smi` should print your GPU) and the host's CUDA toolkit if your repos build CUDA extensions. Install via `sudo ubuntu-drivers autoinstall` first if missing.

### One-shot install (Ubuntu 20.04 / 22.04 / 24.04, Debian 11 / 12)

```bash
git clone https://github.com/YufengJin/claude-harbor.git ~/claude-harbor
cd ~/claude-harbor
./scripts/install/install_prerequisites.sh
```

That installs `uv` for the invoking user. Use `--skip-uv` if uv is already on PATH; `--help` prints details.

After it finishes, **log out and back in** so the `uv` PATH takes effect.

### Manual install

```bash
# uv (no sudo)
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL                                                          # reload PATH

# Verify
uv --version
nvidia-smi    # GPU visible to host
```

## Install

In Claude Code:

```text
/plugin marketplace add YufengJin/claude-harbor
/plugin install harbor@harbor
```

(The marketplace lives at `github.com/YufengJin/claude-harbor` and bundles a single plugin named `harbor`.)

`/help` should now list `/benchmark`. The plugin's MCP server starts on first use via `uv run --no-project --with mcp[cli] --with pyyaml`.

## What you get

| Surface | Use it for |
|---|---|
| `/harbor:help` | Plugin overview — slash commands, agents, MCP tools, hooks, plus live registry counts. |
| `/harbor:env-generator [path]` | Probe a Python GPU repo, render `harbor/setup_uv.sh`, create `.venv/`, classify, dispatch the matching sub-agent. |
| `/harbor:benchmark` | List the maintainer-curated table of verified benchmarks. Sub-actions: `list / submit / verify`. |
| `add-data-logger` skill | Drops a parameterized `data_logger.py` (TensorBoard / W&B) into a Python project. Auto-loaded by description; ask the user once for backend + log dir. |
| `/harbor:rl-tune` | Grid hyperparameter tuning across `task × algorithm`. One `rl-tuning-agent` subagent per cell (open-ended loop: default-config baseline → tricks → log-driven hyperparameter edits → comparison plot). Local mode runs cells sequentially; cluster mode dispatches all cells in parallel and each agent submits its training trials as SLURM jobs. |
| `karpathy-guidelines` skill | Code-writing rules; auto-loaded whenever code is written or reviewed. |
| `env-generator` sub-agent | Entry point for *any* Python GPU repo. Probes deps, renders `setup_uv.sh`, runs setup + smoke, classifies the repo, returns to main thread. |
| `benchmark-generator` sub-agent | Adds env-sanity layer to a benchmark-classified venv. Renders `scripts/run_random.py` (random rollout) + `scripts/render_random.py` (random rollout → MP4). Runs 2-tier smoke (L1 random / L2 render). Training scaffolding is owned by `rl-integration-generator`. RL-only. |
| `rl-integration-generator` sub-agent | After benchmark-generator classifies a repo as RL, renders `harbor/scripts/rl/{train,eval,render,visualize}.py`, `harbor/configs/rl/{ppo,sac,td3}{,.parallel}.yaml`, and `harbor/rl-suite-spec.json`. Smokes each algorithm against `<repo>/.venv/bin/python`. |
| `rl-tuning-agent` sub-agent | Per-algorithm hyperparameter tuning loop: train → eval → render → analyze metrics + behavior → suggest next config. Writes per-trial records under `harbor/rl_experiments/runs/<trial_id>/` and best-config picks under `harbor/rl_experiments/best/<algo>/`. |
| MCP server `harbor` | Read-only registry tools: `list_benchmarks`, `lookup_benchmark`, `get_benchmark_spec`, `list_tasks`. |
| Lifecycle hooks | `SessionStart` injects a one-line registry summary; `PreToolUse(Bash)` refuses destructive patterns; `PostToolUse` truncates long pytest/build output; `Stop` / `SubagentStop` write a one-line audit entry to `~/.claude/audit/<date>.jsonl`. |

## Two paths: reproduce vs. curate

| Path | When | What happens |
|---|---|---|
| **Reproduce a verified entry** | Repo appears in `/benchmark` | `git clone <github>` → `/harbor:env-generator` → `bash harbor/setup_uv.sh` → `source .venv/bin/activate`. The verified registry entry stores the source URL + commit so you know which state was certified. |
| **Curate a new entry** | Maintainer onboarding a fresh repo | Full pipeline: `env-generator` (probe + render setup_uv.sh + create .venv/ + classify) → `benchmark-generator` (extend + smoke + write `<repo>/harbor/benchmark-spec.json`). The MCP registry is **not** mutated by agents; maintainer hand-edits `data/benchmarks.yaml` + copies the spec JSON, then `git commit` + plugin release. |

Most end-users are on the reproduce path. The curate path is maintainer-only.

## Quick start (reproduce a verified benchmark)

```bash
git clone https://github.com/YufengJin/LIBERO
cd LIBERO
# In Claude Code:
#     /harbor:env-generator
# That creates .venv/ and runs the import smoke.
source .venv/bin/activate
python -c "from libero.libero import benchmark; print(list(benchmark.get_benchmark_dict()))"
```

## Quick start (curate a new benchmark)

In Claude Code:

> Set up the env for https://github.com/example/some_benchmark_repo

Claude orchestrates:

```
1. Skill('env-generator') → probe + render setup_uv.sh + create .venv/ + classify("benchmark")
2. Skill('benchmark-generator') → render scripts/run_random.py + scripts/render_random.py + 2-tier smoke
3. Writes <repo>/harbor/benchmark-spec.json + install.md + history.md + benchmark.md
4. Reports: "Built locally; to list in /benchmark, a maintainer must hand-edit data/benchmarks.yaml in the plugin repo."
```

You get a working venv and a complete spec JSON. To register the entry, run `/benchmark submit`; a maintainer then runs `/benchmark verify <name>` to graduate it. See "How to add an entry to /benchmark" below.

## Layout

The harness follows a 6-layer mental model (see `CLAUDE.md` for full description).
Top-level directories map directly to layers:

```
harbor/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .mcp.json                                ← MCP server registration
├── CLAUDE.md                                 ← architecture + 6-layer model
├── README.md
│
├── commands/                                 ← L2 entry points: explicit /harbor:<name>
│   ├── help.md
│   ├── env-generator.md
│   └── benchmark.md
│
├── skills/                                   ← L2 entry points: description auto-load
│   ├── karpathy-guidelines/SKILL.md
│   └── add-data-logger/                      ← skill self-contains its scripts/templates/tests
│
├── agents/                                   ← L3 subagents (flat .md files)
│   ├── env-generator.md
│   ├── benchmark-generator.md
│   ├── rl-integration-generator.md
│   └── rl-tuning-agent.md
│
├── scripts/                                  ← L4 deterministic CLIs, per-owner subdirs
│   ├── env-generator/                          render_uv.py, smoke_uv.py
│   ├── benchmark-generator/                    capture_spec.py
│   ├── registry/                               registry_submit.py, registry_verify.py
│   └── install/                                install_prerequisites.sh, install_uv.sh
│
├── templates/                                ← L5 read-only knowledge: rendered into target repos
│   ├── env-generator/                          install.md, history.md
│   └── benchmark-generator/                    benchmark.md, history.md, scripts/ (random rollout + render)
│
├── references/                               ← L5 read-only knowledge: agent decision aids
│   ├── benchmark-generator/                    decision-matrix, smoke-test-contract
│   └── env-generator/                          decision-protocol, install-plan-schema
│
├── hooks/
│   ├── hooks.json
│   ├── session_start_inject_registry.sh
│   ├── pretool_safety_check.sh                 (refuses rm -rf /, fork bomb, etc.)
│   ├── post_tool_truncate.sh
│   └── stop_audit_log.sh
│
└── mcp/harbor/
    ├── server.py                              ← FastMCP, read-only benchmark registry tools
    ├── pyproject.toml
    ├── data/
    │   └── benchmarks.yaml                    ← maintainer-curated
    └── specs/
        └── benchmarks/<name>.json
```

Per-run workspace state (L6a / L6b) lives inside the **target** repo, not the plugin:

- `<repo>/harbor/run-log/NN-<task>.md` — append-only process log (Layer 6a)
- `<repo>/harbor/{install,history,benchmark,rl-integration}.md` — end-of-run user receipts (Layer 6b)

## MCP server (read-only)

| Tool | Purpose |
|---|---|
| `list_benchmarks` | Filter by status / category. Returns `{count, benchmarks, formatted_table}`. |
| `lookup_benchmark` | By name or github URL (fork-tolerant fuzzy match). |
| `get_benchmark_spec` | obs / action layout. |
| `list_tasks` | Per-task metadata across benchmark specs. |

The server is **read-only at runtime** — agents and Claude have no MCP write API. Registry entries are added via local CLI scripts that produce yaml diffs reviewed and committed in git (see below).

## How to add an entry to /benchmark

Two-stage flow with a clean PR boundary between contributor and maintainer:

**Stage 1 — submit (anyone)**

Run `/benchmark submit` in Claude Code. The skill collects the required fields interactively (name, GitHub user, repo URL, commit hash, category, notes) and appends an entry with `status: unverified` to `mcp/harbor/data/benchmarks.yaml`. **No git operations are performed.** The skill prints the exact `git checkout -b ... / git add / commit / push / gh pr create --fill` commands the contributor must run to open a PR.

**Stage 2 — verify (maintainer)**

After PR review, a maintainer pulls the branch and runs `/benchmark verify <name>`. This:
- fills the verified state (commit hash) from the source repo
- flips `status: unverified` → `status: verified` and writes `verified_at: <today>`
- prints the `git add / git commit` commands; the maintainer reviews the diff and merges

**Why this design**: the MCP server stays read-only — all writes are git diffs produced by `scripts/registry/registry_submit.py` and `scripts/registry/registry_verify.py`. The verified registry remains an artifact of the maintainer's git history; unverified entries live in the same yaml under a distinct `status` value, so the existing MCP filtering (`list_benchmarks(status="verified")`) is unchanged.



## Constraints (also in CLAUDE.md)

1. Generated `install.md` / `history.md` / `benchmark.md` MUST be English-only.
2. The registry stores source URL + commit hash for verified entries (no docker image tags).
3. Registry **read** access via MCP tools only. Never `cat registry.yaml`. Registry **writes** are git-only, produced by the `registry_submit.py` / `registry_verify.py` CLI scripts — no MCP write API exists.
4. Sub-agents return JSON to main thread; no nest-dispatch.

## Roadmap

- Optional sync of `mcp/harbor/data/benchmarks.yaml` into a separate plugin's mirror
- Submission to the official Anthropic plugin marketplace

## License

MIT — see `LICENSE` (or `plugin.json` for now).

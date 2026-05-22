# harbor

A Claude Code plugin for **setting up Python GPU robotics repos with uv**, **scaffolding the RL stack** (training / eval / render / sweep / tune), **authoring tasks end-to-end** (scene → reward → DR), and **tracking verified benchmark entries**.

Give Claude a GitHub URL of a robotics repo → it clones, creates `<repo>/.venv/`, classifies the repo (benchmark / plain), and dispatches the right sub-agent to add the next layer. A maintainer-curated MCP registry powers `/harbor:benchmark` so reproducing a verified entry is just *clone + run setup_uv.sh*.

## Prerequisites

The plugin needs one host-side tool. It is independent of Claude Code itself.

| Tool | Why harbor uses it | Sudo needed? |
|---|---|---|
| **`uv`** | Drives `harbor/setup_uv.sh` (the env-generator output) and the MCP server's bootstrap (`uv run --no-project --with mcp[cli] --with pyyaml`) | no |

You also need a working **NVIDIA driver** (`nvidia-smi` should print your GPU) and the host's CUDA toolkit if your repos build CUDA extensions.

### One-shot install (Ubuntu / Debian)

```bash
git clone https://github.com/YufengJin/claude-harbor.git ~/claude-harbor
cd ~/claude-harbor
./scripts/install/install_prerequisites.sh
```

That installs `uv` for the invoking user. Use `--skip-uv` if uv is already on PATH; `--help` prints details. After it finishes, **log out and back in** so the `uv` PATH takes effect.

### Manual install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
uv --version
nvidia-smi
```

## Install (Claude Code)

```text
/plugin marketplace add YufengJin/claude-harbor
/plugin install harbor@harbor
```

(The marketplace lives at `github.com/YufengJin/claude-harbor` and bundles a single plugin named `harbor`.) `/harbor:help` lists the full surface; the plugin's MCP server starts on first use via `uv run --no-project --with mcp[cli] --with pyyaml`.

## What you get

### Slash commands (`/harbor:<name>`)

| Command | Purpose |
|---|---|
| `help` | Plugin overview — commands / agents / MCP tools / hooks, plus live registry counts. |
| `env-generator [path]` | Probe a Python GPU repo, render `harbor/setup_uv.sh`, create `.venv/`, classify, dispatch the matching sub-agent. |
| `benchmark` | Browse / submit / verify the maintainer-curated benchmark registry. Pass a GitHub URL to reproduce a verified entry. |
| `probe-benchmark [repo=<p>] [canonical_task=<id>]` | Author the family-level `<repo>/harbor/create-task/task-implementation.md` guide (Step 3.7 of `benchmark-generator`, extracted to run standalone). |
| `probe-task task=<id> [output=<p>]` | Emit a portable per-task spec `<task-slug>-implementation.md` with verbatim §1–§7 code — feed back into `create-task from=<path>` to clone the task into another benchmark. |
| `create-task name=<TaskID> (description=… \| from=<spec.md>)` | Author a NEW task (free-form via `description=`) OR reproduce one byte-identical from a `probe-task` spec (`from=`). Dispatches `task-generator` (§1–§5) → `reward-generator` (§6) → `dr-generator` (§7) with per-phase smoke gates. |
| `list-task [<task-id>]` | List / inspect tasks in the cwd-local benchmark; falls back to the registry-side spec via the `list_tasks` MCP tool. |
| `rl-run task=<id> algorithm=<ppo\|sac\|td3> [k=v…]` | Single-trial training; wraps the rendered `harbor/scripts/rl/<impl>/train.py` with Hydra overrides. Auto-renders the final checkpoint on rc=0. |
| `rl-eval checkpoint=<p> [k=v…]` | Run unbiased eval on a checkpoint; writes `metrics.json` next to it. |
| `rl-render checkpoint=<p> [k=v…]` | Render a checkpoint to MP4 with two sanity checks: inference produced actions, and frames at different timesteps actually differ (catches the silently-zero / frozen-IK failure modes). |
| `rl-visualize checkpoint=<p>` | Open a headed GLFW viewer to watch the policy live (requires `$DISPLAY`). |
| `rl-sweep task=<list> algorithm=<list> [k=v1,v2,…]` | Cartesian-product sweep; one sub-agent per trial. With `cluster=…`, renders a SLURM `launch.sh` for `sbatch` instead. |
| `rl-tune task=<list> algorithm=<list> [mode=local\|cluster]` | Grid tuning: one `rl-tuning-agent` subagent per (task, algorithm) cell running an open-ended loop (default-config baseline → tricks → log-driven hyperparameter edits → comparison plot). |
| `reward-tune task=<id> [algorithm=<algo>] [success_threshold=0.5]` | Iterate on the §6 reward of an existing task — each iter the `reward-generator` edits, the orchestrator trains + renders + analyzes per-term log + visual frames vs the task description, loops until success_rate ≥ threshold. |
| `rl-trick <trick> [algorithm=<algo>]` | Apply an RL training trick (e.g. `obs_rms_jax`, `reward_norm_jax`) to a chosen algorithm config in-place. |
| `trick` | List all available RL training tricks with descriptions + applicability. |
| `plot spec=<yaml>` | Plot mean ± std curves from W&B runs grouped by task × baseline (multi-panel learning curves from a YAML spec). |
| `wandb-setup` | Show / re-login / switch the host's W&B account + masked API key. |

### Sub-agents (`agents/<name>.md`)

| Agent | Role |
|---|---|
| `env-generator` | Entry point for any Python GPU repo. Probes deps, renders `setup_uv.sh`, runs setup + smoke, classifies the repo, returns to main thread. |
| `benchmark-generator` | Adds the env-sanity layer to a benchmark-classified repo. Renders `scripts/run_random.py` (random rollout) + `scripts/render_random.py` (render-to-MP4). Runs 2-tier smoke (L1 random / L2 render). RL-only. |
| `rl-integration-generator` | Renders the RL training tree: `harbor/scripts/rl/{train,eval,render,visualize}.py`, `harbor/configs/rl/{ppo,sac,td3}{,.parallel}.yaml`, `rl-suite-spec.json`. Smokes each algorithm against `<repo>/.venv/bin/python` via the production T1–T5 tiers (mirroring `rl-run` / `rl-eval` / `rl-render` exactly). |
| `task-generator` | Authors §1–§5 of a new task (register/scene · actions · reset · goal+termination · observation) with one smoke per section; iterates up to 2× per section before escalating. |
| `reward-generator` | Authors §6 (reward) — `RewardsCfg` + `mdp/rewards.py` functions. Required to write a planned per-stage magnitude budget into the docstring before setting weights (per `experiences/reward-generator/reward-experience.md` entry #2). |
| `dr-generator` | Authors §7 (domain randomization) — `EventCfg` startup / interval terms. `skipped` is a valid success when DR isn't required. |
| `rl-tuning-agent` | Per-cell tuning loop: train → eval → render → analyze metrics + behavior → suggest next config. Per-trial state under `harbor/rl_experiments/`. |

### Skills (auto-loaded by description, also slash-able)

| Skill | Use it for |
|---|---|
| `karpathy-guidelines` | Code-writing rules; auto-loaded whenever code is written or reviewed. |
| `add-data-logger` | Drop a parameterized `data_logger.py` (TensorBoard / W&B) into any Python project. |
| `add-reward-log` | Wire per-reward-term decomposition into a benchmark repo without changing the env's reward — exposes per-term values via `info["detailed_reward"]` and asserts `composer(terms) == reward` every step. |
| `rl-metrics-logging` | Canonical metric-key contract for every `rl-integration-generator` algorithm. Auto-loaded when writing or patching training code. |

### Experiences (numbered, append-only cross-run ledgers)

Each subagent has a `experiences/<role>/` ledger that survives across runs. Entries are numbered for stable cross-reference; **[MUST]** entries are binding requirements the subagent is required to follow (e.g. reward-generator entry #2: magnitude-budget discipline).

```
experiences/rl-tuning-agent/tuning-experience.md      (25 entries: hp heuristics, tricks, failure signatures, …)
experiences/reward-generator/reward-experience.md     (8 entries incl. #2 magnitude-budget [MUST], #7 obstacle-clearance gate)
experiences/task-generator/task-experience.md        (placeholder — promote from per-task lessons)
experiences/dr-generator/dr-experience.md            (placeholder)
```

### MCP server `harbor` (read-only)

| Tool | Purpose |
|---|---|
| `list_benchmarks` | Filter by status / category. Returns `{count, benchmarks, formatted_table}`. |
| `lookup_benchmark` | By name or GitHub URL (fork-tolerant fuzzy match). |
| `get_benchmark_spec` | obs / action layout. |
| `list_tasks` | Per-task metadata across benchmark specs. |

The server is read-only at runtime — agents and Claude have no MCP write API. Registry entries are added via local CLI scripts that produce yaml diffs reviewed and committed in git (see *Registry contributions* below).

### Lifecycle hooks

- `SessionStart` injects a one-line registry summary at session start / clear / compact.
- `PreToolUse(Bash)` refuses obvious destructive patterns (`rm -rf /`, fork bomb, `mkfs`, …).
- `PostToolUse` truncates noisy Bash output (pytest, builds).
- `Stop` / `SubagentStop` append a one-line audit entry to `~/.claude/audit/<date>.jsonl`.

## Three paths

| Path | When | What happens |
|---|---|---|
| **Reproduce a verified benchmark** | Repo appears in `/harbor:benchmark` | `git clone <github>` → `/harbor:env-generator` → `bash harbor/setup_uv.sh` → `source .venv/bin/activate`. The registry stores the source URL + commit so you know which state was certified. |
| **Curate a new benchmark** | Maintainer onboarding a fresh repo | Full pipeline: `env-generator` → `benchmark-generator` (extend + smoke + `<repo>/harbor/benchmark-spec.json`) → `rl-integration-generator` (training tree). The MCP registry is **not** mutated by agents; maintainer hand-edits `data/benchmarks.yaml` + copies the spec JSON, then `git commit` + plugin release. |
| **Author / clone tasks** | Add a new task to a benchmark, or port a task across benchmarks | `probe-benchmark` (once per repo, family-level guide) → `probe-task` (per existing task, portable spec) → `create-task` (with `description=` for new tasks or `from=<spec.md>` for reproductions). Loops: `reward-tune` for §6 iteration; `rl-tune` for hyperparameter search. |

## Quick start (reproduce a verified benchmark)

```bash
git clone https://github.com/YufengJin/LIBERO
cd LIBERO
# In Claude Code:
#     /harbor:env-generator
# Creates .venv/ and runs the import smoke.
source .venv/bin/activate
python -c "from libero.libero import benchmark; print(list(benchmark.get_benchmark_dict()))"
```

## Quick start (curate a new benchmark)

In Claude Code:

> Set up the env for https://github.com/example/some_benchmark_repo

Claude orchestrates:

```
1. Skill('env-generator')          → probe + render setup_uv.sh + create .venv/ + classify("benchmark")
2. Skill('benchmark-generator')    → render scripts/run_random.py + scripts/render_random.py + 2-tier smoke
3. Skill('rl-integration-generator') → render harbor/scripts/rl/{train,eval,render}.py + configs + T1–T5 smoke
4. Writes <repo>/harbor/{benchmark-spec,rl-suite-spec}.json + install.md + history.md + benchmark.md + rl-integration.md
```

You can now `/harbor:rl-run task=<id> algorithm=ppo`, then `/harbor:rl-sweep …` or `/harbor:rl-tune …`.

## Quick start (author or clone a task)

Once a benchmark is set up:

```text
# (a) First time on this benchmark — author the family-level guide.
/harbor:probe-benchmark

# (b) Create a brand-new task from a free-form description.
/harbor:create-task name=Isaac-Push-Block-Franka-v0 \
  description="Franka panda pushes a 5 cm wooden block from the table center to a target marker. \
               Episode succeeds when block-to-marker xy distance < 5 cm; horizon 200 steps."

# (c) OR: probe an existing task into a portable spec and clone it into another benchmark.
/harbor:probe-task task=Triton-Insert-Drawer
/harbor:create-task name=Isaac-Insert-Drawer-UR10-v0 \
  from=harbor/create-task/triton-insert-drawer-implementation.md \
  assets=harbor/assets/ur10/ur10.usd
```

## Iterating on a reward

```text
/harbor:reward-tune task=Triton-Franka-StackCube algorithm=ppo wandb=Triton-Franka-StackCube
```

Each iter: `reward-generator` edits §6 (and may surgically edit §1–§5 if needed) → train at the algorithm's default `num_envs` → render rollout → orchestrator analyzes per-term reward log + visual frames vs the task description → decides continue / success / stuck. Findings accumulate across iterations under `<repo>/harbor/create-task/<task_slug>/`. Loops until `success_rate ≥ 0.5` (or the user interrupts) — no hard cap.

## Layout

The harness follows a 6-layer mental model (see `CLAUDE.md` for full description).

```
harbor/                                        ← plugin root
├── .claude-plugin/{plugin.json, marketplace.json}
├── .mcp.json                                    ← MCP server registration
├── CLAUDE.md                                    ← architecture + 6-layer model
├── README.md
│
├── commands/                                    ← L2 entry points: explicit /harbor:<name>
│   ├── help.md  env-generator.md  benchmark.md
│   ├── probe-benchmark.md  probe-task.md  create-task.md  list-task.md
│   ├── rl-run.md  rl-eval.md  rl-render.md  rl-visualize.md  rl-sweep.md  rl-tune.md
│   ├── reward-tune.md  rl-trick.md  trick.md  plot.md  wandb-setup.md
│
├── skills/                                      ← L2 entry points: description auto-load
│   ├── karpathy-guidelines/  add-data-logger/  add-reward-log/  rl-metrics-logging/
│
├── agents/                                      ← L3 subagents (flat .md files)
│   ├── env-generator.md  benchmark-generator.md  rl-integration-generator.md
│   ├── task-generator.md  reward-generator.md  dr-generator.md
│   └── rl-tuning-agent.md
│
├── scripts/                                     ← L4 deterministic CLIs, per-owner subdirs
│   ├── env-generator/                             render_uv.py, smoke_uv.py
│   ├── benchmark-generator/                       capture_spec.py
│   ├── rl-integration-generator/                  render_rl_suite.py, discover_*.py, validate_rl_suite.py
│   ├── rl-tuning-agent/                           run_rl_trial.py, analyze_rl_trial.py, suggest_hparams.py
│   ├── rl-run/  rl-trick/  plot/  registry/  install/
│
├── templates/                                   ← L5 read-only: rendered into target repos
│   ├── env-generator/  benchmark-generator/       includes task-implementation.md.template
│   ├── rl-integration-generator/                  custom_torch / stable_baseline3 / local_implementation subtrees
│   ├── task-generator/                            per-section smokes + custom action terms
│   ├── reward-generator/  dr-generator/           per-section smokes
│   ├── rl-tuning-agent/  rl-tune/  reward-tune/  rl-sweep/  rl-tricks/  plot/
│
├── references/                                  ← L5 read-only: agent decision aids
│   ├── env-generator/  benchmark-generator/  rl-integration-generator/
│   ├── task-generator/  reward-generator/  dr-generator/  rl-tuning-agent/
│
├── experiences/                                 ← L5 cross-run ledgers (numbered, append-only)
│   ├── rl-tuning-agent/tuning-experience.md       (25 entries)
│   ├── reward-generator/reward-experience.md      (8 entries incl. [MUST] magnitude-budget)
│   ├── task-generator/task-experience.md
│   └── dr-generator/dr-experience.md
│
├── hooks/
│   ├── hooks.json
│   ├── session_start_inject_registry.sh           (refuses rm -rf /, fork bomb, etc. — via pretool_safety_check.sh)
│   ├── pretool_safety_check.sh  post_tool_truncate.sh  stop_audit_log.sh
│
└── mcp/harbor/
    ├── server.py                                  ← FastMCP, read-only benchmark registry tools
    ├── data/benchmarks.yaml                       ← maintainer-curated
    └── specs/benchmarks/<name>.json
```

Per-run workspace state lives inside the **target** repo, not the plugin:

- `<repo>/harbor/run-log/NN-<task>.md` — append-only process log (Layer 6a).
- `<repo>/harbor/{install,history,benchmark,rl-integration}.md` — end-of-run user receipts (Layer 6b).
- `<repo>/harbor/create-task/{task-implementation.md, <task_slug>/, <task_slug>-implementation.md}` — task-authoring workspace.
- `<repo>/harbor/outputs/<algo>_<task>_<ts>/` — per-trial checkpoints + metrics + curves + render.mp4.
- `<repo>/harbor/rl_experiments/{sweeps,tunes}/<id>/` — sweep + tune cell artifacts.

## Registry contributions

Two-stage flow with a clean PR boundary between contributor and maintainer:

**Stage 1 — submit (anyone).** Run `/harbor:benchmark submit` in Claude Code. The skill collects the required fields interactively (name, GitHub user, repo URL, commit hash, category, notes) and appends an entry with `status: unverified` to `mcp/harbor/data/benchmarks.yaml`. No git operations are performed — the skill prints the exact `git checkout -b … / git add / commit / push / gh pr create --fill` commands the contributor must run.

**Stage 2 — verify (maintainer).** After PR review, a maintainer pulls the branch and runs `/harbor:benchmark verify <name>`. This:

- fills the verified state (commit hash) from the source repo;
- flips `status: unverified` → `status: verified` and writes `verified_at: <today>`;
- prints the `git add / git commit` commands; the maintainer reviews the diff and merges.

The MCP server stays read-only — all writes are git diffs produced by `scripts/registry/registry_submit.py` and `scripts/registry/registry_verify.py`. The verified registry remains an artifact of the maintainer's git history; unverified entries live in the same yaml under a distinct `status`, so the existing `list_benchmarks(status="verified")` filtering is unchanged.

## Constraints (also in CLAUDE.md)

1. Generated `install.md` / `history.md` / `benchmark.md` / `rl-integration.md` MUST be English-only.
2. The registry stores source URL + commit hash for verified entries (no docker image tags).
3. Registry **read** access via MCP tools only. Never `cat registry.yaml`. Registry **writes** are git-only, produced by the `registry_submit.py` / `registry_verify.py` CLI scripts — no MCP write API exists.
4. Sub-agents return JSON to main thread; no nest-dispatch. The main thread orchestrates the env-generator → benchmark-generator → rl-integration-generator chain.
5. All plugin-generated files live under `<repo>/harbor/`. The folder is `harbor/` (no dot) so it doubles as a valid Python package — rendered scripts use `sys.path.insert(0, "<repo>/harbor")` to resolve `from utils.data_logger import DataLogger` etc.

## License

MIT — see `LICENSE`.

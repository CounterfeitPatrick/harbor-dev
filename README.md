# harbor

A Claude Code plugin for **setting up Python GPU robotics repos with uv**, **scaffolding the RL stack** (training / eval / render / sweep / tune), **authoring tasks end-to-end** (scene → reward → DR), and **tracking verified benchmark entries**.

Give Claude a GitHub URL of a robotics repo → it clones, creates `<repo>/.venv/`, sets up the environment, and dispatches the benchmark-generator sub-agent to add the next layer. A maintainer-curated MCP registry tracks verified entries so reproducing one is just *clone + run setup_uv.sh*.

## Prerequisites

The plugin needs one host-side tool. It is independent of Claude Code itself.

| Tool | Why harbor uses it | Sudo needed? |
|---|---|---|
| **`uv`** | Drives `harbor/dependency-generator/setup_uv.sh` (the dependency-generator output) and the MCP server's bootstrap (`uv run --no-project --with mcp[cli] --with pyyaml`) | no |

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

Grouped by filename prefix (the prefix is the group — Claude Code commands have no real subdirectory namespace):

| Command | Purpose |
|---|---|
| `help` | Plugin overview — commands / agents / MCP tools / hooks, plus live registry counts. |
| **env — environment** | |
| `env-install-uv [path]` | Probe a Python GPU repo, render `harbor/dependency-generator/setup_uv.sh`, create `.venv/`, run the import smoke, then dispatch `benchmark-generator`. |
| **task — author / probe / inspect** | |
| `probe-benchmark [repo=<p>] [canonical_task=<id>]` | Author the family-level `<repo>/harbor/create-task/task-implementation.md` guide (Step 3.7 of `benchmark-generator`, extracted to run standalone). |
| `probe-task task=<id> [output=<p>]` | Emit a portable per-task spec `<task-slug>-implementation.md` with verbatim §1–§7 code. Runs in a subagent (context-saving). Feed back into `task-create from=<path>` to clone the task into another benchmark. |
| `task-create name=<TaskID> (description=… \| from=<spec.md>)` | Author a NEW task (free-form via `description=`) OR reproduce one byte-identical from a `probe-task` spec (`from=`). Runs `task-generator` (§1–§5, smoke gates) → the `reward-tune` training loop (§6 — reward validated by actual training in all modes; reproduce seeds iter 0 with the spec's reward verbatim) → `dr-generator` (§7, opt-in — skipped unless DR is explicitly requested). |
| `task-list [<task-id>]` | List / inspect tasks in the cwd-local benchmark; falls back to the registry-side spec via the `list_tasks` MCP tool. |
| `task-clone op=create source=<id> dest=<id>` | Clone a task into an isolated, independently-editable copy under a new suffixed gym id (`op=delete` removes it). The collision-free isolation primitive behind parallel `reward-tune` candidates. |
| **reward — reward engineering** | |
| `reward-tune task=<id> [algorithm=<algo>] [pool_size=N] [mode=local\|cluster]` | Async-pool §6 reward tuning. The **main agent** decides each candidate's full reward spec (B1); `reward-generator` implements it on an isolated task clone; the orchestrator trains + renders, `reward-analyzer` scores per-term log + frames → success_rate. Keeps `pool_size` candidates in flight (default 1 = serial; >1 = parallel clones), loops until success_rate ≥ threshold. |
| `reward-add-log` | Wire per-reward-term decomposition into a benchmark repo without changing the env's reward — exposes per-term values via `info["detailed_reward"]` and asserts `composer(terms) == reward` every step. |
| **rl — train / eval / policy** | |
| `rl-run task=<id> algorithm=<ppo\|sac\|td3> [k=v…]` | Single-trial training; wraps the rendered `harbor/scripts/rl/<impl>/train.py` with Hydra overrides. Auto-renders the final checkpoint on rc=0. |
| `rl-eval checkpoint=<p> [k=v…]` | Run unbiased eval on a checkpoint; writes `metrics.json` next to it. |
| `rl-render checkpoint=<p> [k=v…]` | Render a checkpoint to MP4 with two sanity checks: inference produced actions, and frames at different timesteps actually differ (catches the silently-zero / frozen-IK failure modes). |
| `rl-visualize checkpoint=<p>` | Open a headed GLFW viewer to watch the policy live (requires `$DISPLAY`). |
| `rl-sweep task=<list> algorithm=<list> [k=v1,v2,…]` | Cartesian-product sweep; one sub-agent per trial. With `cluster=…`, renders a SLURM `launch.sh` for `sbatch` instead. |
| `rl-tune task=<list> algorithm=<list> [mode=local\|cluster]` | Grid tuning: one `rl-tuning-agent` subagent per (task, algorithm) cell running an open-ended loop (default-config baseline → tricks → log-driven hyperparameter edits → comparison plot). |
| `rl-add-trick <trick> [algorithm=<algo>]` | Apply an RL training trick (e.g. `obs_rms_jax`, `reward_norm_jax`) to a chosen algorithm config in-place. |
| `rl-list-tricks` | List all available RL training tricks with descriptions + applicability. |
| `rl-add-log` | Print the canonical metric-key contract every `rl-integration-generator` algorithm must emit (PPO / SAC / TD3 + per-reward-term + SB3 remap). |
| **utilities** | |
| `plot spec=<yaml>` | Plot mean ± std curves from W&B runs grouped by task × baseline (multi-panel learning curves from a YAML spec). |
| `wandb-setup` | Show / re-login / switch the host's W&B account + masked API key. |
| `update-experience target=<name> (experience="…" \| file=<path>)` | Append a numbered bullet to an agent experience ledger (≤5-line hand-written bullets), or file a `probe-task` implementation spec into the correct `experiences/task-library/` embodiment folder (short `<task>-<repo>.md` name, `-vN` on collision). |

### Sub-agents (`agents/<name>.md`)

| Agent | Role |
|---|---|
| `dependency-generator` | Entry point for any Python GPU repo. Probes deps, renders `setup_uv.sh`, runs setup + import smoke, returns to main thread. |
| `benchmark-generator` | Adds the env-sanity layer to a repo whose env is already set up. Renders `scripts/run_random.py` (random rollout) + `scripts/render_random.py` (render-to-MP4). Runs 2-tier smoke (L1 random / L2 render). RL-only. |
| `rl-integration-generator` | Renders the RL training tree: `harbor/scripts/rl/{train,eval,render,visualize}.py`, `harbor/configs/rl/{ppo,sac,td3}{,.parallel}.yaml`, `rl-suite-spec.json`. Smokes each algorithm against `<repo>/.venv/bin/python` via the production T1–T5 tiers (mirroring `rl-run` / `rl-eval` / `rl-render` exactly). |
| `task-generator` | Authors §1–§5 of a new task (register/scene · actions · reset · goal+termination · observation) with per-section smokes plus an actuator-tracking check (S2.5) and a render-stability + visual check (S6); iterates up to 2× per smoke before escalating. |
| `reward-generator` | **Implements** §6 (reward) from a fully-specified spec — no design. Receives `reward_spec={kind,body}` from the reward-tune main agent and writes it into `RewardsCfg` + `mdp/rewards.py` on the task clone (idiom + numerical safety + S6 smoke). Never reweights / re-gates / re-composes. |
| `reward-analyzer` | The score phase of `reward-tune`. Read-only over one finished trial: per-term curves + rendered frames → `analysis.md` (behavior + success_rate), returns to the main agent. No design decisions. |
| `task-cloner` | Clones a task's editable surface (env_cfg + reward `mdp/`) into a new suffixed gym id with rewired imports + clone smokes, for collision-free parallel editing. Dispatched by `task-clone`. |
| `dr-generator` | Authors §7 (domain randomization) — `EventCfg` startup / interval terms. `skipped` is a valid success when DR isn't required. |
| `rl-tuning-agent` | Per-cell tuning loop: train → eval → render → analyze metrics + behavior → suggest next config. Per-cell state under `harbor/rl_experiments/tunes/<tune_id>/`. |

### Experiences (numbered, append-only cross-run ledgers)

Each subagent has a `experiences/<role>/` ledger that survives across runs. Entries are numbered for stable cross-reference; **[MUST]** entries are binding requirements their reader follows (e.g. the reward-tune main agent applies `reward-experience` entry #2: magnitude-budget discipline when designing a reward).

```
experiences/rl-tuning-agent/tuning-experience.md      (25 entries: hp heuristics, tricks, failure signatures, …)
experiences/reward-generator/reward-experience.md     (8 entries incl. #2 magnitude-budget [MUST], #7 obstacle-clearance gate)
experiences/task-generator/task-experience.md        (placeholder — promote from per-task lessons)
experiences/dr-generator/dr-experience.md            (placeholder)
experiences/task-library/<area>/<family>/library.md  (task-design knowledge by embodiment+family:
                                                       manipulation/{multi-arm,single-arm}-manipulation,
                                                       locomotion/{humanoid,quadrupedal})
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
| **Reproduce a verified benchmark** | Repo is in the registry (read via MCP `list_benchmarks`) | `git clone <github>` → `/harbor:env-install-uv` → `bash harbor/dependency-generator/setup_uv.sh` → `source .venv/bin/activate`. The registry stores the source URL + commit so you know which state was certified. |
| **Curate a new benchmark** | Maintainer onboarding a fresh repo | Full pipeline: `dependency-generator` → `benchmark-generator` (extend + smoke + `<repo>/harbor/benchmark-generator/benchmark-spec.json`) → `rl-integration-generator` (training tree). The MCP registry is **not** mutated by agents; maintainer hand-edits `data/benchmarks.yaml` + copies the spec JSON, then `git commit` + plugin release. |
| **Author / clone tasks** | Add a new task to a benchmark, or port a task across benchmarks | `probe-benchmark` (once per repo, family-level guide) → `probe-task` (per existing task, portable spec) → `task-create` (with `description=` for new tasks or `from=<spec.md>` for reproductions). Loops: `reward-tune` for §6 iteration; `rl-tune` for hyperparameter search. |

## Quick start (reproduce a verified benchmark)

```bash
git clone https://github.com/YufengJin/LIBERO
cd LIBERO
# In Claude Code:
#     /harbor:env-install-uv
# Creates .venv/ and runs the import smoke.
source .venv/bin/activate
python -c "from libero.libero import benchmark; print(list(benchmark.get_benchmark_dict()))"
```

## Quick start (curate a new benchmark)

In Claude Code:

> Set up the env for https://github.com/example/some_benchmark_repo

Claude orchestrates:

```
1. Skill('dependency-generator')   → probe + render setup_uv.sh + create .venv/ + import smoke
2. Skill('benchmark-generator')    → render scripts/run_random.py + scripts/render_random.py + 2-tier smoke
3. Skill('rl-integration-generator') → render harbor/scripts/rl/{train,eval,render}.py + configs + T1–T5 smoke
4. Writes per-agent dirs: harbor/dependency-generator/{install.md,...} + harbor/benchmark-generator/{benchmark-spec.json, history.md, benchmark.md, task_overview.md} + harbor/rl-integration-generator/{rl-suite-spec.json, rl-integration.md}
```

You can now `/harbor:rl-run task=<id> algorithm=ppo`, then `/harbor:rl-sweep …` or `/harbor:rl-tune …`.

## Quick start (author or clone a task)

Once a benchmark is set up:

```text
# (a) First time on this benchmark — author the family-level guide.
/harbor:probe-benchmark

# (b) Create a brand-new task from a free-form description.
/harbor:task-create name=Isaac-Push-Block-Franka-v0 \
  description="Franka panda pushes a 5 cm wooden block from the table center to a target marker. \
               Episode succeeds when block-to-marker xy distance < 5 cm; horizon 200 steps."

# (c) OR: probe an existing task into a portable spec and clone it into another benchmark.
/harbor:probe-task task=Triton-Insert-Drawer
/harbor:task-create name=Isaac-Insert-Drawer-UR10-v0 \
  from=harbor/create-task/triton-insert-drawer-implementation.md \
  assets=harbor/assets/ur10/ur10.usd
```

## Iterating on a reward

```text
/harbor:reward-tune task=Triton-Franka-StackCube algorithm=ppo wandb=Triton-Franka-StackCube
```

Each candidate: the **main agent** decides the full reward spec (B1) → `reward-generator` implements it on an isolated task clone (`task-clone`) → the orchestrator trains (default `num_envs`) + renders → `reward-analyzer` scores per-term log + frames vs the task description → the main agent decides the next candidate. An async pool keeps `pool_size` candidates in flight (default 1 = serial; >1 = parallel clones). Findings accumulate under `<repo>/harbor/create-task/<task_slug>/`. Loops until `success_rate ≥ threshold` (or the user interrupts at a stuck-prompt) — no hard cap.

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
│   ├── help.md  env-install-uv.md
│   ├── probe-benchmark.md  probe-task.md  task-create.md  task-list.md
│   ├── rl-run.md  rl-eval.md  rl-render.md  rl-visualize.md  rl-sweep.md  rl-tune.md
│   ├── reward-tune.md  rl-add-trick.md  rl-list-tricks.md  plot.md  wandb-setup.md
│   ├── reward-add-log.md  rl-add-log.md  update-experience.md
│
├── agents/                                      ← L3 subagents (flat .md files)
│   ├── dependency-generator.md  benchmark-generator.md  rl-integration-generator.md
│   ├── task-generator.md  reward-generator.md  dr-generator.md
│   └── rl-tuning-agent.md
│
├── scripts/                                     ← L4 deterministic CLIs, per-owner subdirs
│   ├── dependency-generator/                             render_uv.py, smoke_uv.py
│   ├── benchmark-generator/                       capture_spec.py
│   ├── rl-integration-generator/                  render_rl_suite.py, render_data_logger.py, discover_*.py, validate_rl_suite.py
│   ├── rl-tuning-agent/                           run_rl_trial.py, analyze_rl_trial.py, suggest_hparams.py
│   ├── reward-add-log/                          sanity_check.py, sanity_check_isaaclab.py
│   ├── rl-run/  rl-tricks/  plot/  registry/  install/
│
├── templates/                                   ← L5 read-only: rendered into target repos
│   ├── dependency-generator/  benchmark-generator/       includes task-implementation.md.template
│   ├── rl-integration-generator/                  custom_torch / stable_baseline3 / local_implementation subtrees + data_logger.py.template
│   ├── task-generator/                            per-section smokes + custom action terms
│   ├── reward-generator/  dr-generator/           per-section smokes
│   ├── reward-add-log/                          reward_terms_block + isaaclab_env_helper templates
│   ├── rl-tuning-agent/  rl-tune/  reward-tune/  rl-sweep/  rl-tricks/  plot/
│
├── references/                                  ← L5 read-only: agent decision aids
│   ├── dependency-generator/  benchmark-generator/  rl-integration-generator/
│   ├── task-generator/  reward-generator/  dr-generator/  rl-tuning-agent/
│
├── experiences/                                 ← L5 cross-run ledgers (numbered, append-only)
│   ├── rl-tuning-agent/tuning-experience.md       (25 entries)
│   ├── reward-generator/reward-experience.md      (8 entries incl. [MUST] magnitude-budget)
│   ├── task-generator/task-experience.md
│   ├── dr-generator/dr-experience.md
│   └── task-library/{manipulation,locomotion}/<family>/library.md  (task design by embodiment+family)
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

- `<repo>/harbor/<agent>/history.md` — append-only per-run process log (Layer 6a), inside each agent's own subdir (e.g. `rl-integration-generator/history.md`).
- `<repo>/harbor/dependency-generator/install.md`, `<repo>/harbor/benchmark-generator/{history,benchmark}.md`, `<repo>/harbor/rl-integration-generator/rl-integration.md` — end-of-run user receipts (Layer 6b), each in its agent's dir.
- `<repo>/harbor/create-task/{task-implementation.md, <task_slug>/, <task_slug>-implementation.md}` — task-authoring workspace.
- `<repo>/harbor/outputs/<algo>_<task>_<ts>/` — per-trial checkpoints + metrics + curves + render.mp4.
- `<repo>/harbor/rl_experiments/{sweeps,tunes}/<id>/` — sweep + tune cell artifacts.

## Registry contributions

Two-stage flow with a clean PR boundary between contributor and maintainer:

**Stage 1 — submit (anyone).** Run `python scripts/registry/registry_submit.py` (pass the required fields: name, GitHub user, repo URL, commit hash, category, notes). It appends an entry with `status: unverified` to `mcp/harbor/data/benchmarks.yaml`. No git operations are performed — it prints the exact `git checkout -b … / git add / commit / push / gh pr create --fill` commands the contributor must run.

**Stage 2 — verify (maintainer).** After PR review, a maintainer pulls the branch and runs `python scripts/registry/registry_verify.py <name>`. This:

- fills the verified state (commit hash) from the source repo;
- flips `status: unverified` → `status: verified` and writes `verified_at: <today>`;
- prints the `git add / git commit` commands; the maintainer reviews the diff and merges.

The MCP server stays read-only — all writes are git diffs produced by `scripts/registry/registry_submit.py` and `scripts/registry/registry_verify.py`. The verified registry remains an artifact of the maintainer's git history; unverified entries live in the same yaml under a distinct `status`, so the existing `list_benchmarks(status="verified")` filtering is unchanged.

## Constraints (also in CLAUDE.md)

1. Generated `install.md` / `history.md` / `benchmark.md` / `rl-integration.md` MUST be English-only.
2. The registry stores source URL + commit hash for verified entries (no docker image tags).
3. Registry **read** access via MCP tools only. Never `cat registry.yaml`. Registry **writes** are git-only, produced by the `registry_submit.py` / `registry_verify.py` CLI scripts — no MCP write API exists.
4. Sub-agents return JSON to main thread; no nest-dispatch. The main thread orchestrates the dependency-generator → benchmark-generator → rl-integration-generator chain.
5. All plugin-generated files live under `<repo>/harbor/`. The folder is `harbor/` (no dot) so it doubles as a valid Python package — rendered scripts use `sys.path.insert(0, "<repo>/harbor")` to resolve `from utils.data_logger import DataLogger` etc.

## License

MIT — see `LICENSE`.

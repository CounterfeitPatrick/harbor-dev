# harbor

Plugin for setting up Python GPU repos via uv and tracking verified benchmark entries.
Team-internal scope.

## Hard constraints (apply to ALL tasks)

1. Generated `install.md` / `history.md` / `benchmark.md` MUST be English-only — regardless of chat language.
2. The registry stores source URL + commit hash for verified benchmarks (no docker image tags). Reproduction is via `/harbor:env-generator` against the source repo.
3. Registry access is via MCP tools (`mcp__plugin_harbor_harbor__*`). Never `cat registry.yaml` directly.
4. Subagents do not nest-dispatch. Main thread orchestrates `env-generator` → `benchmark-generator`.
5. **All plugin-generated files live under `<repo>/harbor/`** — except `scripts/_<family>_env.py` / `scripts/run_random.py` / `scripts/render_random.py` (user-facing smoke entry points). Concretely: receipts at `<repo>/harbor/{install,history,benchmark,rl-integration}.md`, run logs at `<repo>/harbor/run-log/*.md`, RL training tree at `<repo>/harbor/scripts/rl/`, configs at `<repo>/harbor/configs/rl/`, training output at `<repo>/harbor/outputs/`, the DataLogger at `<repo>/harbor/utils/data_logger.py`, and per-run metadata (probe.json / install_plan.json / benchmark-spec.json / rl-suite-spec.json) at `<repo>/harbor/`. The folder name is `harbor/` (no dot) so it doubles as a valid Python package — imports like `from utils.data_logger import DataLogger` resolve against `<repo>/harbor/` after `sys.path.insert(0, HARBOR_ROOT)`.
6. Code style across main thread AND all subagents (full reference: `skills/karpathy-guidelines/SKILL.md`):
   - **Think before coding** — state assumptions explicitly; if uncertain, ask. Don't pick silently between alternatives.
   - **Simplicity first** — minimum code that solves the problem; no speculative features, abstractions, configurability, or error handling for impossible scenarios.
   - **Surgical changes** — touch only what the task requires; don't "improve" adjacent code, refactor things that aren't broken, or remove pre-existing dead code unless asked.
   - **Goal-driven execution** — define verifiable success criteria up front; loop until the verification check passes. Weak criteria like "make it work" are not acceptable.

---

## 6-layer mental model

The harness is structured as six layers with different cardinality, lifecycle, and mutability. Use this map when deciding where a new module belongs.

```
L1   AGENT (intelligence)         — Claude itself; not in code
L2   ENTRY POINTS                 — User-facing surfaces. Two flavours:
                                    · commands/<name>.md   = explicit slash /harbor:<name>
                                    · skills/<name>/SKILL.md = description-driven auto-load (also slash-able)
L3   SUBAGENTS (roles)            — agents/<name>.md   (fresh context, isolated agent loop)
L4   TOOLS (deterministic)        — scripts/<owner>/*.py + MCP functions + Bash + Read/Write/Edit
L5   SHARED KNOWLEDGE (read-only) — templates/, references/, mcp/data/
L6a  WORKSPACE PROCESS LOGS       — <repo>/harbor/run-log/*.md   (per-run, append-only)
L6b  WORKSPACE RECEIPTS           — <repo>/harbor/{install,history,benchmark,rl-integration}.md  (end-of-run user summary)
```

Decision rules when adding a new module:

```
Q1: Does the user invoke it directly in chat?    → L2 entry point
Q2: Multi-step reasoning + decisions?            → L3 subagent
Q3: Single deterministic input → output?         → L4 tool
Q4: Read-only doc / data?
    Q4.1: Cross-repo shared?                     → L5 shared knowledge
    Q4.2: Per-run process record?                → L6a process log
    Q4.3: End-of-run user-facing summary?        → L6b receipt
```

L2 vs L3 are **not the same axis**:
- L2 asks "how does the user wake it up" (slash invocation)
- L3 asks "how is the context isolated" (fresh `messages=[]`, independent loop)
- Skills can dispatch subagents internally; subagents don't need a slash entry. The two are independent.

---

## Where things live (post-refactor)

### L2 — Entry points

- `commands/help.md` — `/harbor:help` plugin overview
- `commands/env-generator.md` — `/harbor:env-generator [path]` — uv-only env setup; renders `<repo>/harbor/setup_uv.sh` and creates `<repo>/.venv/`
- `commands/benchmark.md` — `/harbor:benchmark list / submit / verify`
- `commands/list-task.md` — `/harbor:list-task` — list/inspect tasks in a benchmark; defaults to cwd-local `harbor/benchmark-spec.json`, falls back to registry via `list_tasks` MCP tool
- `commands/rl-run.md` — `/harbor:rl-run task=<id> algorithm=<algo> [k=v ...]` — single-trial training; wraps `harbor/scripts/rl/<impl>/train.py` against `<repo>/.venv/bin/python`
- `commands/rl-eval.md` — `/harbor:rl-eval checkpoint=<path> [k=v ...]` — single-checkpoint eval; writes `metrics.json` next to checkpoint
- `commands/rl-visualize.md` — `/harbor:rl-visualize checkpoint=<path> [k=v ...]` — open headed GLFW viewer; requires `$DISPLAY`
- `commands/rl-sweep.md` — `/harbor:rl-sweep task=<list> algorithm=<list> [k=v1,v2,...]` — Cartesian-product sweep; one sub-agent per trial; results under `harbor/rl_experiments/sweeps/<sweep_id>/`
- `commands/rl-tune.md` — `/harbor:rl-tune task=<list> algorithm=<list> [mode=local|cluster]` — Cartesian-product grid TUNING (open-ended hyperparameter loop); one rl-tuning-agent subagent per cell; tune-level history.md + final cross-cell summary under `harbor/rl_experiments/tunes/<tune_id>/`. One-time scaffolding lives in the `rl-integration-generator` subagent (dispatched directly).
- `commands/task-creation.md` — `/harbor:task-creation name=<TaskID> description="..." [assets=<paths>]` — author a NEW task in the current benchmark repo. Pre-flight requires `<repo>/harbor/task-creation/task-implementation.md` to exist (created by `benchmark-generator` Step 3.7). Dispatches `task-generator` (§1–§5) → `reward-generator` (§6) → `dr-generator` (§7) sequentially with per-phase smoke gates.
- `commands/reward-tune.md` — `/harbor:reward-tune task=<id> [algorithm=<algo>] [wandb=<project>] [mode=local|cluster] [max_iterations=N] [timesteps_per_iter=N]` — iteratively tune the §6 reward for an existing task. Per iteration: dispatches `reward-generator` (with `permit_env_edits=true`, recent findings, prior analyses) → trains a policy via `train.py` → renders rollout to MP4 → analyzes per-term reward log + visual frames vs the task description → decides continue / success / stuck. Memory of findings is shared across iterations via `<tune_dir>/memories.jsonl`. Cluster mode currently falls back to local.
- `skills/karpathy-guidelines/` — coding behaviour rules; auto-loaded whenever code is written
- `skills/add-data-logger/` — drop a parameterized `data_logger.py` (TensorBoard / W&B); auto-loaded when user mentions data logging
- `skills/add-reward-log/` — `/add-reward-log` adds a per-term reward-visibility wrapper to `scripts/_<family>_env.py` (does NOT modify env reward); the sanity-check smoke asserts `composer(info["detailed_reward"].values()) == env_reward` per step, where composer ∈ {"sum","product"} is per-task
- `skills/rl-metrics-logging/` — canonical metric-key contract (PPO/SAC/TD3 + per-reward-term + SB3 remap) for ALL `harbor/scripts/rl/<impl>/` algorithms; auto-loaded by rl-integration-generator and whenever algorithm training code is being written or patched

### L3 — Subagents (heavy, multi-step; main thread dispatches; no nesting)

- `agents/env-generator.md` — entry point for any "set up env for \<repo\>" task; renders `<repo>/harbor/setup_uv.sh`, creates `<repo>/.venv/`, classifies
- `agents/benchmark-generator.md` — env-sanity layer: random rollout + render-to-MP4 + 2-tier smoke (L1 random / L2 render). Always treats the repo as RL — no IL detection. Does NOT generate train/eval scripts (rl-integration-generator owns those).
- `agents/rl-integration-generator.md` — RL experiment scaffold: configs, train/eval/render/visualize scripts, algorithm adapter, smoke per algorithm
- `agents/rl-tuning-agent.md` — algorithm-by-algorithm hyperparameter tuning loop (train→eval→render→analyze→suggest)
- `agents/task-generator.md` — authors §1–§5 of a new task (register/scene · actions · reset · goal+termination · observation) with one smoke per section; iterates up to 2× per section before escalating. Reads `<repo>/harbor/task-creation/task-implementation.md`. Dispatched only by `/harbor:task-creation`.
- `agents/reward-generator.md` — authors §6 (reward) at the placeholder `task-generator` left. Runs the §6 smoke (finite + composer assertion). Dispatched only by `/harbor:task-creation` after `task-generator` passes.
- `agents/dr-generator.md` — authors §7 (domain randomization) at the placeholder. Runs the §7 smoke (seed-matched obs trajectories diverge). Final agent in the `/task-creation` chain; `skipped` is a valid success when the user's description and the canonical example both have no DR.

### L4 — Tools (deterministic CLIs and MCP functions)

```
scripts/
  env-generator/      render_uv.py, smoke_uv.py
  benchmark-generator/ capture_spec.py
  rl-integration-generator/ render_rl_suite.py, discover_rl_tasks.py,
                      discover_algorithms.py, validate_rl_suite.py
  rl-tuning-agent/    run_rl_trial.py, analyze_rl_trial.py, suggest_hparams.py,
                      render_trial_contact_sheet.py, write_rl_report.py
  registry/           registry_submit.py, registry_verify.py
  install/            install_prerequisites.sh, install_uv.sh

skills/add-data-logger/scripts/  render_data_logger.py, verify_data_logger.py
```

MCP functions (read-only): `list_benchmarks`, `lookup_benchmark`, `get_benchmark_spec`, `list_tasks`.

### L5 — Shared knowledge (read-only)

```
templates/
  env-generator/         install.md.template, history.md.template
  benchmark-generator/   benchmark.md, history.md, task_overview.md,
                         task-implementation.md (read by /harbor:task-creation),
                         scripts/{run_random, render_random}.py.template
  rl-integration-generator/  per-source subtrees (renderer picks one):
                               stable_baseline3/scripts/{train,eval,render,env_wrapper}.py.template
                               custom_torch/scripts/{train,eval,render,env_wrapper}.py.template
                               custom_torch/{algo,replay,models,utils}/*.py.template (~14 self-contained algo files)
                               local_implementation/scripts/{train,eval,render,env_wrapper}.py.template (shims)
                             shared (top-level):
                               configs/{ppo,sac,td3}{,.parallel}.yaml.template (unified schema both sources read)
                               configs/suite.yaml.template
                               rl-suite-spec.json.template (carries algorithm_slug + scripts_dir)
                               rl-integration.md.template (Layer 6b user receipt: train / eval / render / override-hparams)
                               tune.py.template (top-level cross-impl tuning entry)
  rl-tuning-agent/       tuning-history.md.template (per-cell ledger),
                         (legacy: history.md.template, trial_summary.md.template,
                          video_analysis.md.template, rl_experiment_report.md.template
                          — kept for back-compat, not used by the current agent)
  rl-tune/               history.md.template (tune-level ledger written by /harbor:rl-tune)
  reward-tune/           history.md.template (tune-level ledger written by /harbor:reward-tune)
  task-generator/        smokes/smoke_s{1..5}.py.template (per-section behavioral smokes
                           rendered to <task_dir>/smokes/ then run inside .venv);
                         action_terms/ema_delta_joint_pos{,_cfg}.py.template (custom
                           EMACumulativeRelativeJointPositionAction — rendered into
                           <task>/mdp/ when §2 mode == ema_delta_joint_pos);
                         action_terms/ema_delta_ee_pose{,_cfg}.py.template (custom
                           EMACumulativeDeltaPoseAction — task-space analog;
                           rendered when §2 mode == ema_delta_ee_pose)
  reward-generator/      smokes/smoke_s6.py.template (reward finite + non-constant +
                           composer assertion via info["detailed_reward"])
  dr-generator/          smokes/smoke_s7.py.template (DR ON vs OFF seed-matched obs
                           trajectories must diverge)

skills/add-data-logger/templates/  data_logger.py.template

references/
  env-generator/         decision-protocol, install-plan-schema
  benchmark-generator/   decision-matrix, smoke-test-contract,
                         receipt-generation, case-studies,
                         task-implementation-contract (rules for the
                           /harbor:task-creation guide)
  rl-integration-generator/ rl-suite-spec (schema for harbor/rl-suite-spec.json + benchmark-spec rl extension)
  rl-tuning-agent/       tuning-instruction (procedure + 4 hard constraints)
  task-generator/        isaaclab-code-reference (action / scene / obs / termination /
                           command APIs the agent calls), smoke-contracts (what each S1..S5
                           verifies + substitution slot specs)
  reward-generator/      isaaclab-reward-reference (composer-by-family, RewTerm idiom,
                           common mdp.* building blocks, weight conventions),
                         smoke-contract (what S6 verifies + substitutions)
  dr-generator/          isaaclab-dr-reference (EventCfg modes, randomize_* funcs, range
                           conventions, disable-DR-for-comparison recipe),
                         smoke-contract (what S7 verifies + substitutions)

experiences/             cross-run heuristic ledgers (numbered, append-only)
  rl-tuning-agent/       tuning-experience.md
  task-generator/        task-experience.md
  reward-generator/      reward-experience.md
  dr-generator/          dr-experience.md

mcp/harbor/data/       benchmarks.yaml  (live registry)
mcp/harbor/specs/      benchmarks/<name>.json
```

### L6a — Process logs (per-run engineering record)

`<repo>/harbor/run-log/NN-<task>.md` — one short markdown per task: tool used / agent / command / one-line result. Append-only.

### L6b — Receipts (end-of-run user summary)

`<repo>/harbor/install.md`, `<repo>/harbor/history.md`, `<repo>/harbor/benchmark.md`, `<repo>/harbor/rl-integration.md` — generated by the matching subagent at the end of a run. English only (constraint #1).

### Workspace layout (one root for everything plugin-generated)

```
<repo>/                                user repo root, untouched except for the carve-outs below
├── .venv/                             uv-managed venv (created by env-generator's setup_uv.sh)
├── scripts/
│   ├── _<family>_env.py               kept at root — benchmark-generator's smoke-helper convention
│   ├── run_random.py                  kept at root — L1 smoke entry point
│   └── render_random.py               kept at root — L2 smoke entry point
└── harbor/                          single root for plugin-generated artifacts
    ├── install.md, history.md, benchmark.md, rl-integration.md   L6b receipts
    ├── benchmark-spec.json, install_plan.json, probe.json,
    │   rl-suite-spec.json                                        per-run metadata
    ├── setup_uv.sh                                               env-generator output (re-runnable)
    ├── run-log/NN-<task>.md                                      L6a process logs
    ├── rl_experiments/                                           rl-tuning-agent trial state
    ├── task-creation/                                            /harbor:task-creation workspace
    │   ├── task-implementation.md                                family guide (benchmark-generator output)
    │   └── <slug>/                                               per-task workspace, one folder per /task-creation run
    │       ├── spec.json                                         args + per-phase status (orchestrator)
    │       ├── task-history.md                                   verbose log: §1..§5 phases (task-generator)
    │       ├── reward-history.md                                 verbose log: §6 (reward-generator)
    │       └── dr-history.md                                     verbose log: §7 (dr-generator)
    ├── scripts/rl/<impl>/{train,eval,render,env_wrapper}.py      RL training tree
    ├── configs/rl/{ppo,sac,td3}.yaml                             RL configs (Hydra)
    ├── outputs/<algo>_<task>_<ts>/{checkpoint,metrics.jsonl,
    │   tb/, curves/, render.mp4}                                 training artifacts
    └── utils/data_logger.py                                      DataLogger
```

The `harbor/` directory is a valid Python package — rendered scripts use:

```python
REPO     = Path(__file__).resolve().parents[4]   # actual repo root (for scripts/_<family>_env.py)
HARBOR = Path(__file__).resolve().parents[3]   # <repo>/harbor  (for utils.data_logger, configs/rl/, outputs/)
sys.path.insert(0, str(HARBOR))                # so `from utils.data_logger import DataLogger` resolves
sys.path.insert(0, str(REPO))                    # so `from scripts._<family>_env import ...` resolves
```

Hydra `config_path="../../../configs/rl"` is unchanged (3 ups from `harbor/scripts/rl/<impl>/` lands in `harbor/`, then into `configs/rl/`).

### Hooks

- `hooks/session_start_inject_registry.sh` — one-line registry summary at session start / clear / compact
- `hooks/pretool_safety_check.sh` — refuses obviously-destructive Bash patterns (`rm -rf /`, fork bomb, mkfs, …)
- `hooks/post_tool_truncate.sh` — truncates noisy Bash output
- `hooks/stop_audit_log.sh` — appends one-line audit entry on Stop / SubagentStop

### Plugin-level permissions

`settings.json` (at plugin root, sibling to `.claude-plugin/`) ships an allowlist for the python / uv / bash subcommands the plugin's subagents need to run unattended. The pretool-safety hook still blocks the destructive cases — the allowlist only removes the prompt; the safety net stays.

### MCP

`mcp/harbor/server.py` — FastMCP, read-only benchmark registry tools. Registered in `.mcp.json`.

### Historical / archived

- `harness-refactor/` — B0-B2 refactor logs, planning docs, deprecated B2 artifacts (`render_manifest.py`, `run_task.py`, `manifest.schema.json`). Untracked. Don't ship; don't reference from runtime code.

See `README.md` for end-user / contributor instructions.

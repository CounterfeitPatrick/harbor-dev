# harbor

Plugin for setting up Python GPU repos via uv and tracking verified benchmark entries.

## Hard constraints (apply to ALL tasks)

1. Generated `install.md` / `history.md` / `benchmark.md` MUST be English-only — regardless of chat language.
2. The registry stores source URL + commit hash for verified benchmarks (no docker image tags). Reproduction is via `/harbor:env-install-uv` against the source repo.
3. Registry access is via MCP tools (`mcp__plugin_harbor_harbor__*`). Never `cat registry.yaml` directly.
4. Subagents do not nest-dispatch. Main thread orchestrates `dependency-generator` → `benchmark-generator`.
5. **All plugin-generated files live under `<repo>/harbor/`** — except `scripts/_<family>_env.py` / `scripts/run_random.py` / `scripts/render_random.py` (user-facing smoke entry points). Each generator agent writes its receipts + metadata into **its own subdir**: `harbor/dependency-generator/{setup_uv.sh, probe.json, install_plan.json, install.md}`, `harbor/benchmark-generator/{benchmark-spec.json, task_overview.md, .task_list.json, history.md, benchmark.md}`, `harbor/rl-integration-generator/{rl-suite-spec.json, rl-integration.md, history.md}`. The shared RL training tree stays at the top level: training scripts at `<repo>/harbor/scripts/rl/`, configs at `<repo>/harbor/configs/rl/`, training output at `<repo>/harbor/outputs/`, the DataLogger at `<repo>/harbor/utils/data_logger.py`; the create-task workspace at `<repo>/harbor/create-task/`. There is NO shared `run-log/` folder — each agent's per-run process log is the `history.md` inside its own subdir. The folder name is `harbor/` (no dot) so it doubles as a valid Python package — imports like `from utils.data_logger import DataLogger` resolve against `<repo>/harbor/` after `sys.path.insert(0, HARBOR_ROOT)`.
6. Code style across main thread AND all subagents:
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
                                      (harbor ships none today — all current entry points are commands)
L3   SUBAGENTS (roles)            — agents/<name>.md   (fresh context, isolated agent loop)
L4   TOOLS (deterministic)        — scripts/<owner>/*.py + MCP functions + Bash + Read/Write/Edit
L5   SHARED KNOWLEDGE (read-only) — templates/, references/, mcp/data/
L6a  WORKSPACE PROCESS LOGS       — <repo>/harbor/<agent>/history.md   (per-run, append-only, inside each agent's subdir)
L6b  WORKSPACE RECEIPTS           — <repo>/harbor/<agent>/{install,history,benchmark,rl-integration}.md  (end-of-run user summary, in each agent's subdir)
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

Commands are grouped by area via filename prefix (Claude Code commands have no true subdir namespace — the prefix IS the group). Groups: `env-*` · task (`task-*` + `probe-*`) · `reward-*` · `rl-*` · top-level utilities.

- `commands/help.md` — `/harbor:help` plugin overview

**env — environment setup**
- `commands/env-install-uv.md` — `/harbor:env-install-uv [path]` — uv-only env setup; renders `<repo>/harbor/dependency-generator/setup_uv.sh` and creates `<repo>/.venv/` (dispatches the `dependency-generator` subagent)

**task — author / probe / inspect tasks**
- `commands/probe-benchmark.md` — `/harbor:probe-benchmark [repo=<path>] [canonical_task=<id>]` — author `<repo>/harbor/create-task/task-implementation.md` (Step 3.7 of `benchmark-generator`, extracted so it can be re-run standalone or delegated from the agent)
- `commands/probe-task.md` — `/harbor:probe-task task=<id> [repo=<path>] [output=<path>]` — emit a per-task `<task-slug>-implementation.md` capturing every design choice (scene / actions / reset / termination / observation / reward / DR) with verbatim code. **Runs in a subagent** (context-saving). Feed back into `/harbor:task-create from=<path>` to clone the task identically into another benchmark.
- `commands/task-create.md` — `/harbor:task-create name=<TaskID> (description="..." | from=<spec.md>) [sections=<list>] [assets=<paths>]` — author a NEW task in the current benchmark repo, or reproduce one from a `/harbor:probe-task` spec. Pre-flight checks the `dependency-generator` → `benchmark-generator` → `rl-integration-generator` chain in sequence and dispatches any missing stage first (rl-integration defaults to `custom_torch` unless the user specifies an algorithm source). Then runs `task-generator` (§1–§5, per-section smoke gates) → the `/harbor:reward-tune` loop (§6 — validated by actual training until success_rate ≥ threshold in ALL modes; reproduce mode seeds iter 0 with the spec's reward pasted verbatim) → `dr-generator` (§7, **opt-in**: skipped unless the user explicitly requests DR).
- `commands/task-list.md` — `/harbor:task-list` — list/inspect tasks in a benchmark; defaults to cwd-local `harbor/benchmark-generator/benchmark-spec.json`, falls back to registry via `list_tasks` MCP tool
- `commands/task-clone.md` — `/harbor:task-clone op=create source=<TaskID> dest=<TaskID> [info_out=<path>] | op=delete dest=<TaskID>` — clone a task into an isolated, independently-editable copy registered under a new suffixed gym id (`-rewarditer<NNN>` before `-vN`); `create` dispatches the `task-cloner` subagent, `delete` removes the clone. The isolation primitive `/harbor:reward-tune` uses to give each parallel reward candidate its own collision-free task

**reward — reward engineering**
- `commands/reward-tune.md` — `/harbor:reward-tune task=<id> [algorithm=<algo>] [pool_size=N] [mode=local|cluster] [on_success=cancel|drain] [success_threshold=0.5] [timesteps_per_iter=N]` — ASYNC fixed-pool reward tuning, same submit/score skeleton as `/harbor:rl-tune`. The **main agent decides** each candidate's full reward spec (B1, in-flight-aware so parallel candidates don't duplicate); `reward-generator` (implement mode) writes it onto an isolated **task clone** (`/harbor:task-clone`); the orchestrator trains+renders compute-side; `reward-analyzer` scores per-term curves + frames → success_rate → returns to the main agent. Keeps `pool_size` candidates in flight (default 1 = serial; >1 = parallel clones), loops until `success_rate ≥ success_threshold` then cancels in-flight. Render is folded into the train job (login-node-safe on cluster). Findings shared via `<task_dir>/memories.jsonl`.
- `commands/reward-add-log.md` — `/harbor:reward-add-log` adds a per-term reward-visibility wrapper to `scripts/_<family>_env.py` (does NOT modify env reward); the sanity-check smoke asserts `composer(info["detailed_reward"].values()) == env_reward` per step, where composer ∈ {"sum","product"} is per-task. Assets at `scripts/reward-add-log/` + `templates/reward-add-log/`.

**rl — train / eval / policy**
- `commands/rl-run.md` — `/harbor:rl-run task=<id> algorithm=<algo> [k=v ...]` — single-trial training; wraps `harbor/scripts/rl/<impl>/train.py` against `<repo>/.venv/bin/python`
- `commands/rl-eval.md` — `/harbor:rl-eval checkpoint=<path> [k=v ...]` — single-checkpoint eval; writes `metrics.json` next to checkpoint
- `commands/rl-render.md` — `/harbor:rl-render checkpoint=<path> [k=v ...]` — render a checkpoint to MP4 with inference-moved + frame-difference sanity checks
- `commands/rl-visualize.md` — `/harbor:rl-visualize checkpoint=<path> [k=v ...]` — open headed GLFW viewer; requires `$DISPLAY`
- `commands/rl-sweep.md` — `/harbor:rl-sweep task=<list> algorithm=<list> [k=v1,v2,...]` — Cartesian-product sweep; one sub-agent per trial; results under `harbor/rl_experiments/sweeps/<sweep_id>/`
- `commands/rl-tune.md` — `/harbor:rl-tune task=<list> algorithm=<list> [mode=local|cluster]` — Cartesian-product grid TUNING (open-ended hyperparameter loop); one rl-tuning-agent subagent per cell; tune-level history.md + final cross-cell summary under `harbor/rl_experiments/tunes/<tune_id>/`. One-time scaffolding lives in the `rl-integration-generator` subagent (dispatched directly).
- `commands/rl-add-trick.md` — `/harbor:rl-add-trick <trick> [algorithm=<algo>]` — apply an RL training trick (e.g. `obs_rms_jax`, `reward_norm_jax`) to a chosen algorithm config in-place (reads the `templates/rl-tricks/` library)
- `commands/rl-list-tricks.md` — `/harbor:rl-list-tricks` — list available RL training tricks with descriptions + applicability (read-only)
- `commands/rl-add-log.md` — `/harbor:rl-add-log` — canonical metric-key contract (PPO/SAC/TD3 + per-reward-term + SB3 remap) for ALL `harbor/scripts/rl/<impl>/` algorithms; the binding reference `rl-integration-generator` follows when authoring/patching algorithm training code

**utilities**
- `commands/plot.md` — `/harbor:plot spec=<yaml>` — multi-panel mean±std W&B learning curves grouped by task × baseline
- `commands/wandb-setup.md` — `/harbor:wandb-setup` — inspect / re-login / switch the host's W&B account
- `commands/update-experience.md` — `/harbor:update-experience target=<name> (experience="..." | file=<path>)` — append a numbered bullet to an agent ledger (`reward-generator`/`task-generator`/`dr-generator`/`rl-tuning-agent`; hand-written bullets capped at 5 lines), OR file a `/harbor:probe-task` spec into the right `experiences/task-library/` embodiment folder (classify single/multi-arm manipulation vs humanoid/quadrupedal locomotion; short `<task>-<repo>.md` name, `-vN` on collision)

### L3 — Subagents (heavy, multi-step; main thread dispatches; no nesting)

- `agents/dependency-generator.md` — entry point for any "set up env for \<repo\>" task; renders `<repo>/harbor/dependency-generator/setup_uv.sh`, creates `<repo>/.venv/`, runs the import smoke
- `agents/benchmark-generator.md` — env-sanity layer: random rollout + render-to-MP4 + 2-tier smoke (L1 random / L2 render). Always treats the repo as RL — no IL detection. Does NOT generate train/eval scripts (rl-integration-generator owns those).
- `agents/rl-integration-generator.md` — RL experiment scaffold: configs, train/eval/render/visualize scripts, algorithm adapter, smoke per algorithm
- `agents/rl-tuning-agent.md` — algorithm-by-algorithm hyperparameter tuning loop (train→eval→render→analyze→suggest)
- `agents/task-generator.md` — authors §1–§5 of a new task (register/scene · actions · reset · goal+termination · observation) with per-section smokes plus an actuator-tracking check (S2.5) and a render-stability + visual check (S6); iterates up to 2× per smoke before escalating. Reads `<repo>/harbor/create-task/task-implementation.md`. Dispatched only by `/harbor:task-create`.
- `agents/task-cloner.md` — clones a task's editable surface (env_cfg + reward-relevant mdp modules) into dest-named copies, rewires imports, registers `<dest>` (suffix before `-vN`), runs the clone smokes (build + rollout + per-term-logging), writes a delete manifest. Dispatched by `/harbor:task-clone op=create`. Never edits source files.
- `agents/reward-generator.md` — §6 (reward) **implementer only — no design**. Sole caller is `/harbor:reward-tune`, whose main agent decides the complete B1-strict spec (terms + concrete weights + gates + composer + budget) and passes it as `reward_spec={kind:"verbatim"|"structured", body}`. The agent translates the spec into IsaacLab code at `reward_path` (the clone, never the source), handling idiom + dt-scaling + numerical safety + mechanical verification, then runs the §6 smoke. Never reweights / re-gates / re-composes; surfaces spec defects instead. Adapt-first / library search / magnitude-budget design all live in the reward-tune main agent now, not here.
- `agents/reward-analyzer.md` — the SCORE phase of `/harbor:reward-tune`. Read-only over one finished trial: parses per-term curves from `metrics.jsonl` → `success_rate`, reads rendered frames → behavior, writes `iter_<NNN>/analysis.md`, returns a distilled result + findings. Makes NO design decision (that is the main agent's B1 job).
- `agents/dr-generator.md` — authors §7 (domain randomization) across 3 groups (robot · object · observation-noise) at the placeholder, once-per-episode-per-env (`mode="reset"`). Discovers available terms per group and wires EVERY available term by default (comprehensive, not minimal — hard constraint; un-wired terms need a logged reason) (modes: multiplicative/additive/direct for groups 1–2 default `(0.9,1.1)`; uniform/gaussian for obs noise default σ=0.01), runs the §7 smoke (exact value read-back at num_envs=16 + after-reset re-check), and writes a handoff at `harbor/create-task/<slug>/handoff-dr-generator.md`. Final agent in the `/create-task` chain; `skipped` is a valid success when no DR is requested and the canonical example has none.

### L4 — Tools (deterministic CLIs and MCP functions)

```
scripts/
  common/                    resolve_suite.py  (canonical rl-suite-spec.json reader: slug / scripts_dir / parallel / config_name — single source so the key path can't drift across callers)
  dependency-generator/      render_uv.py, smoke_uv.py
  benchmark-generator/ capture_spec.py, list_tasks.py, render_task_overview.py
  rl-integration-generator/ render_rl_suite.py, render_data_logger.py, discover_rl_tasks.py,
                      discover_algorithms.py, validate_rl_suite.py
  rl-tuning-agent/    run_rl_trial.py, analyze_rl_trial.py, suggest_hparams.py,
                      render_trial_contact_sheet.py, write_rl_report.py
  rl-run/             check_reward_logger.py
  rl-tricks/          apply_trick.py, list_tricks.py
  reward-add-log/     sanity_check.py, sanity_check_isaaclab.py
  plot/               render_plot.py
  registry/           registry_submit.py, registry_verify.py
  install/            install_prerequisites.sh, install_uv.sh
```

MCP functions (read-only): `list_benchmarks`, `lookup_benchmark`, `get_benchmark_spec`, `list_tasks`.

### L5 — Shared knowledge (read-only)

```
templates/
  dependency-generator/         install.md.template
  benchmark-generator/   benchmark.md, history.md, task_overview.md,
                         task-implementation.md (read by /harbor:task-create),
                         scripts/{run_random, render_random}.py.template
  rl-integration-generator/  per-source subtrees (renderer picks one):
                               stable_baseline3/scripts/{train,eval,render,env_wrapper}.py.template
                               custom_torch/scripts/{train,eval,render,env_wrapper}.py.template
                               custom_torch/{algo,replay,models,utils}/*.py.template (~14 self-contained algo files)
                               custom_jax/scripts/{train,eval,render,env_wrapper,visualize}.py.template +
                                 custom_jax/{algo,replay,models,utils}/*.py.template (JAX mirror of custom_torch)
                               local_implementation/scripts/{train,eval,render,env_wrapper}.py.template (shims)
                             shared (top-level):
                               configs/{ppo,sac,td3}{,.parallel}.yaml.template (unified schema both sources read)
                               configs/suite.yaml.template
                               rl-suite-spec.json.template (carries algorithm_slug + scripts_dir)
                               rl-integration.md.template (Layer 6b user receipt: train / eval / render / override-hparams)
                               tune.py.template (top-level cross-impl tuning entry)
                               data_logger.py.template (rendered to <repo>/harbor/utils/data_logger.py by render_data_logger.py)
  rl-tuning-agent/       tuning-history.md.template (per-cell ledger),
                         (legacy: history.md.template, trial_summary.md.template,
                          video_analysis.md.template, rl_experiment_report.md.template
                          — kept for back-compat, not used by the current agent)
  rl-tune/               history.md.template (tune-level ledger written by /harbor:rl-tune)
  reward-tune/           history.md.template (tune-level ledger written by /harbor:reward-tune)
  task-generator/        smokes/smoke_s{1..5}.py.template (per-section behavioral smokes,
                           num_envs=2 for gpu-sim) + smoke_s2_5.py.template (actuator
                           tracking error → physics-param sanity, runs after S2) +
                           smoke_s6_render.py.template (random-rollout render → scene-stability
                           asserts + keyframe PNGs the agent visually inspects; MP4 to
                           <task_dir>/) + smoke_success{,_visualize}.py.template (success-scenario
                           replication → confirm the success termination fires; the visualize
                           sibling is headed and NOT run in regression) —
                           all rendered to <task_dir>/smokes/ then run in .venv;
                         action_terms/ema_delta_joint_pos{,_cfg}.py.template (custom
                           EMACumulativeRelativeJointPositionAction — rendered into
                           <task>/mdp/ when §2 mode == ema_delta_joint_pos);
                         action_terms/ema_delta_ee_pose{,_cfg}.py.template (custom
                           EMACumulativeDeltaPoseAction — task-space analog;
                           rendered when §2 mode == ema_delta_ee_pose)
  reward-generator/      smokes/smoke_s6.py.template (reward finite + non-constant +
                           composer assertion via info["detailed_reward"])
  task-cloner/           smokes/smoke_clone.py.template (cloned task builds + rolls out
                           with finite reward + reports per-term-logging inheritance;
                           one AppLauncher covering SC1/SC3/SC4)
  dr-generator/          smokes/smoke_s7.py.template (per-term exact value read-back at
                           num_envs=16 — point-interval range → prop == default modified by k,
                           re-checked after reset; obs-noise terms checked vs paired no-noise cfg)
  reward-add-log/        reward_terms_block.py.template (Path A scalar wrapper),
                         isaaclab_env_helper.py.template (Path B IsaacLab helper)
  rl-tricks/             <trick>/{manifest.yaml, patches.yaml, smoke.py, edits/*} — trick library read
                         by /harbor:rl-add-trick (obs_rms_jax, obs_rms_torch, reward_norm_jax,
                         value_clip_torch, value_norm_torch, distributional_critic_torch)
  rl-sweep/              launch.sh{,.isaaclab}.template (SLURM trial launchers for /harbor:rl-sweep)
  plot/                  spec.example.yaml (example /harbor:plot spec)

references/
  task-library-search.md  cross-cutting: search the task-library + experience ledger for a similar prior task BEFORE designing (read by task-generator, /harbor:task-create, /harbor:reward-tune main agent)
  common/agent-conventions.md  cross-cutting: shared conventions (smoke pass-criterion, diagnose-and-retry, process-log discipline, English-only / no-nested-dispatch) for the authoring subagents — each agent's body overrides the generic shape with its own specifics
  dependency-generator/         decision-protocol, install-plan-schema
  benchmark-generator/   smoke-test-contract,
                         receipt-generation, case-studies,
                         task-implementation-contract (rules for the
                           /harbor:task-create guide)
  rl-integration-generator/ rl-suite-spec (schema for harbor/rl-integration-generator/rl-suite-spec.json + benchmark-spec rl extension)
  rl-tuning-agent/       tuning-instruction (procedure + 4 hard constraints)
  task-generator/        isaaclab-code-reference (action / scene / obs / termination /
                           command APIs the agent calls), smoke-contracts (what each S1..S6
                           verifies + substitution slot specs)
  reward-generator/      isaaclab-reward-reference (composer-by-family, RewTerm idiom,
                           common mdp.* building blocks, weight conventions),
                         smoke-contract (what S6 verifies + substitutions)
  task-cloner/           clone-contract (the 5 clone checks SC1..SC5, the registration
                           rule — suffix before -vN, no '#' — and what to copy vs share)
  dr-generator/          isaaclab-dr-reference (3 groups: robot/object/obs-noise; full randomize_*
                           function surface, mode→operation map, discovery recipe, read-back recipes,
                           once-per-episode reset rule),
                         smoke-contract (what S7 verifies + substitutions)

experiences/             cross-run heuristic ledgers (numbered, append-only)
  rl-tuning-agent/       tuning-experience.md
  task-generator/        task-experience.md
  reward-generator/      reward-experience.md
  dr-generator/          dr-experience.md
  task-library/          task-design knowledge indexed by embodiment + family (not by agent);
                         one self-contained <task>-<repo>.md probe-task spec per task (+ README.md):
                           manipulation/{multi-arm-manipulation, single-arm-manipulation}/*.md
                           locomotion/{humanoid, quadrupedal}/*.md

mcp/harbor/data/       benchmarks.yaml  (live registry)
mcp/harbor/specs/      benchmarks/<name>.json
```

### L6a — Process logs (per-run engineering record)

Each agent's per-run process log lives **inside its own subdir** — `<repo>/harbor/rl-integration-generator/history.md`, `<repo>/harbor/benchmark-generator/history.md`, and the per-task `harbor/create-task/<slug>/{task,reward,dr}-history.md`. One short markdown section per run: tool used / agent / command / one-line result. Append-only. (There is no shared `run-log/` folder.)

### L6b — Receipts (end-of-run user summary)

`<repo>/harbor/dependency-generator/install.md`, `<repo>/harbor/benchmark-generator/history.md`, `<repo>/harbor/benchmark-generator/benchmark.md`, `<repo>/harbor/rl-integration-generator/rl-integration.md` — generated by the matching subagent at the end of a run. English only (constraint #1).

### Workspace layout (one root for everything plugin-generated)

```
<repo>/                                user repo root, untouched except for the carve-outs below
├── .venv/                             uv-managed venv (created by dependency-generator's setup_uv.sh)
├── scripts/
│   ├── _<family>_env.py               kept at root — benchmark-generator's smoke-helper convention
│   ├── run_random.py                  kept at root — L1 smoke entry point
│   └── render_random.py               kept at root — L2 smoke entry point
└── harbor/                          single root for plugin-generated artifacts
    ├── dependency-generator/{setup_uv.sh, probe.json, install_plan.json, install.md}   dependency-generator outputs
    ├── benchmark-generator/{benchmark-spec.json, task_overview.md, .task_list.json, history.md, benchmark.md}   benchmark-generator outputs
    ├── rl-integration-generator/{rl-suite-spec.json, rl-integration.md, history.md}   rl-integration-generator outputs (receipts/metadata + L6a process log; the RL training tree stays at harbor/scripts/rl/ etc.)
    ├── rl_experiments/{sweeps,tunes}/<id>/                       sweep + tune workspaces (canonical root)
    ├── create-task/                                            /harbor:task-create workspace
    │   ├── task-implementation.md                                family guide (benchmark-generator output)
    │   └── <slug>/                                               per-task workspace, one folder per /task-create run
    │       ├── spec.json                                         args + per-phase status (orchestrator)
    │       ├── task-history.md                                   verbose log: §1..§5 phases (task-generator)
    │       ├── reward-history.md                                 verbose log: §6 (reward-generator)
    │       ├── dr-history.md                                     verbose log: §7 (dr-generator)
    │       └── handoff-dr-generator.md                           §7 handoff: available+effective DR terms per group, modes, ranges, smoke results
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

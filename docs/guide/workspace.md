# Your workspace

Everything HARBOR generates lands inside the target repository under a single root, `harbor/`. Nothing is hidden in a cache directory or a conversation transcript, and setting up a second benchmark is the same pipeline run again.

```
<your-repo>/                          your repo, untouched except for the carve-outs below
├── .venv/                            uv-managed environment
├── scripts/
│   ├── _<family>_env.py              smoke-helper convention, kept at root
│   ├── run_random.py                 L1 smoke entry point
│   └── render_random.py              L2 smoke entry point
└── harbor/
    ├── dependency-generator/         setup_uv.sh, probe.json, install_plan.json, install.md
    ├── benchmark-generator/          benchmark-spec.json, task_overview.md, benchmark.md, history.md
    ├── rl-integration-generator/     rl-suite-spec.json, rl-integration.md, history.md
    ├── create-task/
    │   ├── task-implementation.md    the family-level authoring guide
    │   └── <task-slug>/              one folder per task-create run
    ├── scripts/rl/<impl>/            train.py, eval.py, render.py, env_wrapper.py
    ├── configs/rl/                   ppo.yaml, sac.yaml, td3.yaml
    ├── outputs/<algo>_<task>_<ts>/   checkpoint, metrics.jsonl, tb/, curves/, render.mp4
    ├── rl_experiments/{sweeps,tunes}/
    └── utils/data_logger.py
```

The folder is `harbor/` with no leading dot, deliberately: it doubles as a valid Python package, so rendered scripts resolve `from utils.data_logger import DataLogger` after adding it to `sys.path`.

## Three kinds of file

**Receipts** are the end-of-run summary written for you — `install.md`, `benchmark.md`, `rl-integration.md`. Read these first.

**Process logs** are the append-only engineering record, one `history.md` inside each agent's own subdirectory. One short section per run: what tool, which agent, what command, one line of result. Read these when something went wrong and you want to know what was tried.

**Working artifacts** are everything else — specs, configs, smokes, verdicts, checkpoints. These are the substrate agents actually communicate through.

## Per-task workspace

Each `task-create` run gets its own folder:

```
harbor/create-task/<task-slug>/
├── spec.json                  arguments and per-phase status
├── task-history.md            §1–§6 design record: analysis + validations
├── task-analysis.md           the rationale half alone, read by reward design
├── test-checklist.md          every check that actually ran
├── smokes/                    rendered smokes + the verdict.json each wrote
├── smoke_s{3,4,6}_frames/     reset layouts · per-predicate states · rollout keyframes
├── reward-history.md          the §6 tuning log
├── dr-history.md              the §7 log
└── handoff-dr-generator.md    available and effective DR terms, modes, ranges, results
```

`test-checklist.md` is task-specific rather than boilerplate: §4 emits one check/validation pair per predicate the design actually implemented, so the checklist describes *this* task's verification, not a generic template.

## Resuming

Because state lives in files rather than context, an interrupted run resumes. Tuning loops checkpoint `tune-state.json` every iteration. Long training jobs launch detached and signal completion with a sentinel file, so a trainer that outlives its agent still counts. Pick the conversation back up and HARBOR reads where it was from disk.

## Removing it

```text
/harbor:reset-workspace repo=<path>
```

Removes all HARBOR output — `harbor/`, `.venv/`, the `scripts/` carve-outs, caches — and by default restores the repository to its cloned HEAD with `git reset --hard` and `git clean -fdx`.

This is the one destructive command, and the only one gated against model invocation: it runs in a subagent behind a dry-run and an explicit confirmation, then verifies with a git-based check that includes hidden and ignored files before reporting success.

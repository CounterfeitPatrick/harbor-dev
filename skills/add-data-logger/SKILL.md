---
name: add-data-logger
description: Drop a parameterized DataLogger.py (TensorBoard / W&B / both, with scalar/image/text/dict logging) into a target Python project. Use when the user types /add-data-logger or asks "add a data logger", "set up wandb logging", "add tensorboard logging", "wire up training logging".
---

# /add-data-logger — Generate a DataLogger Utility

Generates a single-file `data_logger.py` into the user's target project, parameterized by which backend(s) and which log types they need. The output is a self-contained class — no robomimic dependency, no special config schema.

## When to use

- User wants to add training/eval logging to a Python project that doesn't already have it.
- User wants a thin wrapper that hides whether scalars go to TensorBoard, W&B, or both.
- User wants the choice between full-featured (image + text + dict) and minimal (scalar-only).

## When NOT to use

- The project already uses a high-level training framework (PyTorch Lightning, SB3 + WandbCallback, HuggingFace Trainer) — those have their own loggers; adding a DataLogger on top is redundant.
- User wants something that auto-instruments arbitrary code — DataLogger is a manual API, calls must be inserted by the user.

## Workflow

Execute these steps in order:

### Step 1 — Ask the user three questions via AskUserQuestion

```
Q1 (header: "Backend"):
  Which logging backend(s) should the generated DataLogger support?
  - "TensorBoard only" — `tensorboardX.SummaryWriter`, local files only, no creds. (Recommended for local-only runs.)
  - "W&B only" — `wandb.init` + `wandb.log`, requires API key + entity, cloud-first with offline fallback.
  - "Both" — fan-out to both backends in a single `record()` call. (Recommended for production.)

Q2 (header: "Log types", multiSelect: true):
  Which data types does the project need to log?
  - "Scalars (mandatory)" — loss, accuracy, reward, lr, etc. Always included.
  - "Images" — frames, reconstructions, attention maps. Adds `record(..., data_type='image')` + ndarray HxWxC support.
  - "Text" — eval breakdowns, command lines, release notes. Adds `log_text(key, msg, step)`.

Q3 (header: "Output path"):
  Absolute path where the rendered data_logger.py should be written. (Convention: `<project>/utils/data_logger.py` for libraries, `<project>/data_logger.py` for scripts.)
```

Map the answers:

| Q1 answer | --backend |
|---|---|
| TensorBoard only | tb |
| W&B only | wandb |
| Both | both |

For Q2, build the `--features` arg as `scalar` plus any of `image`, `text` selected. (`scalar` is always present.)

### Step 2 — Render the file

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/add-data-logger/scripts/render_data_logger.py" \
    --backend  <backend> \
    --features <features> \
    --output   <abs_path>
```

The render script applies mustache substitution to `skills/add-data-logger/templates/data_logger.py.template`, strips out blocks for unselected features, and writes the result. It also prints the `pip install` line for the dependencies the user needs.

### Step 2.5 — Verify the rendered file (mandatory)

Immediately after Step 2, smoke-test the generated file under mocked backends to catch any template / mustache regression before handing control back to the user:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/add-data-logger/scripts/verify_data_logger.py" --path <abs_path>
```

This script:
- compiles the rendered file
- checks for leftover `{{...}}` mustache markers
- imports the module under mocked `tensorboardX` + `wandb` (no real installs needed)
- instantiates `DataLogger` and exercises every public method that should exist for the chosen feature set (`record`, `record_dict`, `get_stats`, `close`, plus `log_text` / image variants if enabled)
- asserts the underlying mock writers were actually called

If `verify_data_logger.py` exits non-zero, **do not** report success to the user — surface the printed `[FAIL]` line and ask the user whether to retry, file an issue against harbor, or proceed anyway.

If it exits 0, continue to Step 3.

### Step 3 — Report back to the user

Tell them:
1. The absolute path of the generated file.
2. The pip install line printed by the render script.
3. A 3-line example invocation matching their feature choice. For example:

```python
from data_logger import DataLogger

dl = DataLogger(log_dir="./logs", log_tb=True, log_wandb=True,
                project="my-project", run_name="exp1", entity="my-team")
dl.record("loss", 0.42, step=0)
dl.record("loss", 0.30, step=1, log_stats=True)  # also writes loss-mean/std/min/max
dl.record_dict({"acc": 0.9, "lr": 1e-3}, step=1)
# (image-only) dl.record("frame", img_HWC, step=0, data_type="image")
# (text-only)  dl.log_text("note", "epoch 0 done", step=0)
dl.close()
```

4. **Where to call `dl.close()`**: at training-loop teardown, in a `try/finally`, or via `atexit.register(dl.close)`. Skipping it leaves the wandb run "running" in their dashboard.

## Notes

- The generated file has no robomimic dependency; the public API mirrors `robomimic/utils/log_utils.py:DataLogger` so callers familiar with that interface won't need retraining.
- `log_stats=True` semantics: once a key is recorded with stats once, **all** subsequent values for that key are kept in memory and re-aggregated on each call. Memory grows linearly with training length — this is intentional (per-key running stats), but for very long runs the user should use stats only on coarse-grained keys (per-epoch, not per-iteration).
- The wandb init has a 10-attempt retry loop with offline fallback on the last attempt. For CI, pass `wandb_init_retries=1, wandb_init_backoff_seconds=0` to fail fast.
- Tensorboard logs land at `<log_dir>/tb/`. Run `tensorboard --logdir <log_dir>/tb` to view.

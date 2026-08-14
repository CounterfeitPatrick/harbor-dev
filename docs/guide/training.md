# Training and tuning

## Single trial

```text
/harbor:rl-run task=<TaskID> algorithm=ppo
```

Any config key can be overridden inline:

```text
/harbor:rl-run task=<TaskID> algorithm=sac num_envs=4096 learning_rate=3e-4 seed=7
```

Output lands in `harbor/outputs/<algo>_<task>_<timestamp>/` — checkpoint, `metrics.jsonl`, TensorBoard logs, plotted curves, and on success an automatically rendered `render.mp4`.

## Evaluate and watch

```text
/harbor:rl-eval checkpoint=<path>          # unbiased eval, writes metrics.json alongside
/harbor:rl-render checkpoint=<path>        # render to MP4
/harbor:rl-visualize checkpoint=<path>     # headed GLFW viewer, needs $DISPLAY
```

`rl-render` carries two sanity checks that exist because both failures are silent: inference must actually produce actions, and frames at different timesteps must actually differ. A frozen scene and a zeroed policy both render a perfectly valid video of nothing happening.

## Sweeps

A Cartesian product over any keys, one sub-agent per trial:

```text
/harbor:rl-sweep task=TaskA,TaskB algorithm=ppo,sac seed=0,1,2
```

Results collect under `harbor/rl_experiments/sweeps/<sweep_id>/`. Adding `cluster=…` renders a SLURM `launch.sh` for `sbatch` instead of running locally.

## Hyperparameter tuning

Where a sweep enumerates a grid you specified, tuning searches open-endedly:

```text
/harbor:rl-tune task=TaskA,TaskB algorithm=ppo,sac
```

One `rl-tuning-agent` runs per `(task, algorithm)` cell: a default-config baseline, then a tricks pass, then log-driven hyperparameter edits, stopping when the running best is not beaten for N consecutive iterations.

Two constraints keep the results honest. Tuned configurations must train in at most twice the default's wall-clock, so a "win" cannot come from simply spending more compute. And convergence is required — a run that has not converged is not a result.

In the paper's evaluation this matched or beat hand-tuned defaults in 11 of 12 settings across IsaacLab, Bi-DexHands, and Loco-MuJoCo, including two Bi-DexHands tasks where the published SAC baseline fails entirely.

## Training tricks

```text
/harbor:rl-list-tricks
/harbor:rl-add-trick obs_rms_jax algorithm=ppo
```

Each trick is a manifest, a patch set, and its own smoke test, applied to the algorithm config in place. Available tricks include observation RMS normalization, reward normalization, value clipping, value normalization, and a distributional critic.

## Plotting

```text
/harbor:plot spec=my_plot.yaml
```

Mean ± std curves from W&B runs, grouped by task × baseline into a multi-panel figure. Each panel averages the seeds belonging to one `(task, baseline)` pair.

## Metric contract

Every algorithm implementation emits the same metric keys, so tuning, scoring, and plotting can read any of them without special cases. `/harbor:rl-add-log` prints that contract; it is binding on any new algorithm added under `harbor/scripts/rl/`.

## Long runs

Training outlives an agent's attention span, so completion is defined by an **artifact, not an exit code**. Runs launch detached under `setsid` and write a sentinel file when finished; a trainer killed after its checkpoint lands still counts as a success. Waits are backgrounded rather than polled, which is what keeps a multi-hour run from re-reading the agent's entire context every ten minutes.

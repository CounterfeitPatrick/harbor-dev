# §4 — Goal + termination

What the task is asking for, and when an episode ends. Two smokes: S4 proves terminations
**fire when forced**, S-success proves the **success** term specifically fires in the success
configuration — not just that something terminated.

## What §4 authors

- `CommandsCfg`, when the goal is a sampled pose / target the policy observes.
- `TerminationsCfg`: the success term, failure terms (object dropped, robot out of bounds),
  and the time-out.

## Decisions to resolve

| Decision | Notes |
|---|---|
| Success condition | The geometric / state predicate that means "done, correctly". The reward's `success_term` will key on this. |
| Failure conditions | Dropping, tipping, leaving the workspace. Each becomes a `DoneTerm`. |
| Time-out | `episode_length_s` from §1; whether time-out is the *only* termination. |
| Goal representation | A command manager term, a fixed target, or implicit in the scene. Determines whether §5 exposes a goal observation. |

## API surface

`knowledge/references/task-generator/isaaclab-code-reference.md` → **Termination / Command managers**
and **Forcing known reset / goal values**.

## Smoke S4

Proves the goal value appears in the observation at the correct slice, and that a forced
failure state triggers termination.

- `{{GOAL_OVERRIDES_BLOCK}}` — pin `cfg.commands.<name>.ranges.*` to point intervals.
- `{{TERMINATION_FORCE_BLOCK}}` — drive the env into a terminating state. Two common shapes:
  - **Pose-driven failure** (e.g. `object_dropping`): write a below-floor pose with
    `unw.scene[<obj>].write_root_pose_to_sim(...)`, step once with a zero action, assert
    `term.any()`.
  - **Time-out only**: run `max_episode_length + 1` steps with zero actions, assert `trunc.any()`.

`write_root_pose_to_sim` **rejects a `(1, 7)` tensor when `num_envs > 1`** — broadcast:

```python
pose = torch.tensor([px, py, pz, qw, qx, qy, qz], device=unw.device)
unw.scene[<obj>].write_root_pose_to_sim(pose.expand(unw.num_envs, -1).contiguous())
```

Full substitution list: `knowledge/templates/task-generator/smokes/smoke_s4.py.template`.

## Smoke S-success

Proves the **success** termination fires when the env is driven into the success
configuration. Render it for **every task that has a success-style termination**; skip only
when the task is purely time-out terminated. It runs after S4.

- `{{SUCCESS_TERM_NAME}}` — assert *that* term fired, not merely that the episode ended.
- `{{SUCCESS_FORCE_BLOCK}}` — place every entity in the success configuration.

**Visualize sibling.** `smoke_success_visualize.py` is rendered alongside it: headed
(`HEADLESS=0`), `NUM_ENVS=1`, never exits, re-pinning every relevant entity each frame so
gravity and integration drift never accumulate. It does **not** run during Phase B regression
— it is an interactive tool for the user:

```bash
cd <repo>
HEADLESS=0 NUM_ENVS=1 .venv/bin/python -u <task_dir>/smokes/smoke_success_visualize.py
```

Its `{{SUCCESS_HOLD_BLOCK}}` must **also pin the anchor / goal entity** — the one
`SUCCESS_FORCE_BLOCK` can skip because the assert smoke runs a single step — and must zero
linear *and* angular velocities every frame.

## Failure → diagnosis → fix

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| No termination fires | the forced state does not satisfy the predicate | print the predicate's inputs at the forced state before adjusting thresholds |
| Some other term fires first | the forced state trips a failure term too | force a state that is unambiguous for the term under test |
| `write_root_pose_to_sim` shape error | `(1, 7)` at `num_envs > 1` | broadcast as above |
| S-success passes but the scene looks wrong | success predicate is satisfiable in a degenerate pose | run the visualize sibling and look |
| Goal absent from obs | §5 does not expose the command | fix §5, not the termination |

## Known traps

- **"A termination fired" is not "the success termination fired."** S4 accepts any
  termination; only S-success distinguishes them, which is why both exist.
- **A success predicate that is too loose passes S-success and then makes the reward's
  success term fire trivially** during tuning, producing an inflated `success_rate`.

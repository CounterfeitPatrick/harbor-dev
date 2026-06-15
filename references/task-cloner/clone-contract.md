# task-cloner — Clone Contract

What a clone must guarantee, how each guarantee is checked, and the registration rule. Read by `task-cloner` (and `/harbor:task-clone`).

## The five checks

| # | Check | How it's verified | Hard / soft |
|---|---|---|---|
| SC1 | **Build** — `gym.make(<dest>)` succeeds | `smoke_clone.py` instantiates the env | hard |
| SC2 | **Independence** — the clone's reward/cfg files are DISTINCT files from the source, and the cloned cfg imports its reward from the COPIED mdp module | static: the cloned cfg's reward imports resolve to `cloned_files[]`, not the source's mdp path (grep the cloned cfg's import lines) | hard |
| SC3 | **Per-term logging** — `info["detailed_reward"]` present | `smoke_clone.py` reports it after stepping | soft (warn) |
| SC4 | **Rollout** — a few steps run, reward finite every step | `smoke_clone.py` steps 10× and asserts `isfinite` | hard |
| SC5 | **Teardown** — deleting the clone removes its files and the source still builds | `/harbor:task-clone op=delete` removes `cloned_files[]` + the registration anchor, then `gym.make(<source>)` | hard (at delete time) |

SC1 / SC3 / SC4 share one `AppLauncher` in `smoke_clone.py` (sim launch is the expensive part). SC2 is a cheap static check the agent runs with `grep` on the cloned cfg. SC5 runs when the clone is deleted, not at create time.

## Registration rule

- The dest id is `<source>` with a `-rewarditer<NNN>` suffix inserted **before** any `-vN` version token:
  - `Isaac-Lift-Cube-Franka-v0` → `Isaac-Lift-Cube-Franka-rewarditer7-v0`
  - never `Isaac-Lift-Cube-Franka-v0-rewarditer7` (breaks gym version parsing).
- Legal gym id chars only: word chars, `:`, `.`, `-`. **No `#`.**
- Mirror the source's own `gym.register` idiom (same entry-point shape, kwargs), pointing at the cloned cfg class. Do not modify the source's register call.

## Substitution slots (`smoke_clone.py.template`)

| Slot | Value |
|---|---|
| `{{DEST_ID}}` | the cloned gym task id |
| `{{NUM_ENVS}}` | `2` for gpu-sim benchmarks (`benchmark-spec.json:gpu_sim == true`), else `1` |

## What to copy (and what not to)

- **Copy:** the `*_env_cfg.py` (cfg class + `RewardsCfg`) and every mdp module a reward edit could touch (typically `mdp/rewards.py` + any task-local mdp the cfg imports).
- **Do NOT copy:** family-wide shared modules the reward never edits — keep importing those from their originals.
- Independence (SC2) is what justifies parallel candidates: two clones editing `rewards.py` must edit two different files.

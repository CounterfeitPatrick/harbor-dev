# §6 smoke contract

Loaded by `reward-generator`. Template at `${CLAUDE_PLUGIN_ROOT}/templates/reward-generator/smokes/smoke_s6.py.template`.

## What it verifies

Run 30 random-action steps and assert:

1. **Finite** — no `NaN` / `Inf` reward at any step.
2. **Non-constant** — `reward.std() > 0` over the 30 steps. Catches "all weights zero" or "all terms returned constants".
3. **Composer match** — when `info["detailed_reward"]` is present (manager-based, or any env where `_DetailedRewardWrapper` is wired), assert the per-step composer (`sum`) matches the env's scalar reward at `atol=1e-5`. Catches per-term wiring bugs that would silently divorce per-term logging from the optimization signal.
4. **Per-term diagnostics** — print the per-term episodic mean over the 30 steps when decomposition is available, so the iteration log captures which term is contributing what.

## Pass criterion

Script exits 0, no `Traceback` / `AssertionError`, final stdout line reads `S6 OK: ...`.

## Num envs

Smoke runs at **`num_envs=128`**. Reward and per-term tensors are `(128,)`. The contract:
- `reward.std() > 0` is checked on the **mean across envs at each step** (so it's a temporal property, not cross-env variance).
- The composer assertion runs `np.allclose(sum(detailed.values()), reward, atol=1e-5)` element-wise across all 128 envs at every step.

## Substitutions

| Slot | Notes |
|---|---|
| `{{TASK_ID}}` | gym task id |

The composer assertion auto-skips when `info["detailed_reward"]` is absent (Direct envs, etc.). No agent-filled blocks needed — the contract is task-agnostic at this level. **Exception:** inside a `/harbor:reward-tune` iteration the auto-skip is NOT acceptable — per-term logging is wired by the tune's Step 0 gate, so an absent `detailed_reward` there means broken wiring and the smoke verdict must be treated as FAIL (see `agents/reward-generator.md`).

## When the contract fails

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| `NaN` / `Inf` | divide-by-zero, log(0), exp overflow | clamp the offending operand |
| `reward is constant` | weights all zero, or terms returned constants | re-check weights against the §6 reference task; verify the obs the term reads from is updating |
| `composer mismatch` | per-term values don't sum to total | composer override (sum vs product), or a term in the env that isn't surfaced in `detailed_reward` |
| Build error | `mdp.<func>` symbol missing in this version | drop to a known function from the canonical task |

If the canonical task fails the same smoke, `task-implementation.md` is stale — patch it surgically, log in `reward-history.md`, retry.

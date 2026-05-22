# §7 smoke contract

Loaded by `dr-generator`. Template at `${CLAUDE_PLUGIN_ROOT}/templates/dr-generator/smokes/smoke_s7.py.template`.

## What it verifies

Build two envs from the same task:
- **DR ON**: the cfg as authored.
- **DR OFF**: the same cfg with every §7 randomization range collapsed to a point interval (no-op).

Drive both with `seed=0` and identical action sequences for 20 steps. Assert:

1. **Same shape** — DR must not change the obs structure. Catches "DR axis enabled/disabled a sensor".
2. **Diverge** — `max_obs_delta = max(|obs_on - obs_off|) > 1e-3`. Catches "DR is no-op" (event terms targeted entities not in scene, ranges silently collapsed by upstream, etc.).

## Pass criterion

Script exits 0, no `Traceback` / `AssertionError`, final stdout line reads `S7 OK: ...`.

## Num envs

Both rollouts run at **`num_envs=128`**. The action sequence is sampled from the env's `action_space` after `action_space.seed(0)`; for parallel envs the sample shape is `(128, action_dim)` natively, so no manual broadcast is needed. The `np.abs(obs_on - obs_off).max()` reduction runs over the full `(T, 128, dim)` tensor — DR has to push at least one element of one env at one step past the `1e-3` floor.

## Substitutions

| Slot | Notes |
|---|---|
| `{{TASK_ID}}` | gym task id |
| `{{DR_DISABLE_OVERRIDES}}` | Python lines that mutate `cfg_off.events.<term>.params` to point intervals for every §7 term. Reset terms (`reset_*`) are NOT touched here — they're §3 territory. |

The smoke is otherwise task-agnostic. The substitution slot exists because IsaacLab manager-based has no runtime DR toggle, so the agent has to author the disable-block based on the actual EventCfg it wired.

## When the contract fails

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| `DR is no-op (max_delta < 1e-3)` | event params target entities not in scene; or §5 obs doesn't read the affected fields | re-target params to entities present in §1; verify §5 includes the affected fields |
| `shape mismatch` | a DR axis added/removed an obs key (e.g. enabled a sensor with DR off) | constrain DR to axes that don't change the obs space |
| Build error | term name typo, `mdp.randomize_*` symbol absent in the installed version | drop to a known term from the §7 reference task |
| Tracebacks during reset | DR range too aggressive (mass=0, friction<0) | shrink range to ≤ ±20% of nominal |

If the canonical task fails the same smoke, `task-implementation.md` is stale — patch surgically, log in `dr-history.md`, retry.

## When DR is skipped

The agent skips §7 entirely (and never renders this template) if all three conditions hold:

1. User description does not request randomization, robustness, sim-to-real, or noise.
2. §7 reference task in `task-implementation.md` has no DR wired (`<unsupported in this benchmark>` or zero terms).
3. Family default = no-DR (e.g. `dm_control`, `gymnasium-generic`).

`status: skipped` is a valid success outcome.

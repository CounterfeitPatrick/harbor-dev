# §3 — Reset / events

What the world looks like at the start of every episode, expressed as `EventCfg` terms with
`mode="reset"`.

## What §3 authors

- The `EventCfg` reset terms: robot joint state, object poses, and anything else re-randomized
  per episode.
- **Always with their full range parameters present**, even when the ranges are point
  intervals — `dr-generator` widens the numbers later (§7) and needs the terms to exist.

## Decisions to resolve

| Decision | Notes |
|---|---|
| Which entities reset | Every entity whose start state matters to the reward or the success condition. |
| Range params | In **create mode**, point intervals: `(K, K)` / `(1.0, 1.0)` so every episode is deterministic and S3 can assert exact read-back. |
| Reset ordering | If one entity's reset depends on another's (an object placed relative to the table), the term order matters. |

**Create mode is DR-aware but no-op.** Include the terms with full range params, set the
ranges to point intervals. The same applies to observation noise in §5
(`Unoise(n_min=0, n_max=0)`). This is what lets §7 widen ranges later without re-authoring.

## API surface

`knowledge/references/task-generator/isaaclab-code-reference.md` → **Forcing known reset / goal values**
(pinning a term's range to a point interval before `gym.make`) and **Scene state** (reading
the value back out of the simulator).

## Smoke S3

Proves the reset values **land in the simulator**: inject point intervals, reset, then read
the state back and compare.

- `{{INIT_OVERRIDES_BLOCK}}` — lines pinning `cfg.events.<term>.params["pose_range"]` /
  `["position_range"]` to point intervals.
- `{{EXPECTED_STATE_CHECKS}}` — assertions reading `unw.scene[<asset>].data.<field>` and
  comparing against the injected values with `torch.allclose`.

Full substitution list: `knowledge/templates/task-generator/smokes/smoke_s3.py.template`.

## Failure → diagnosis → fix

| Symptom | Likely cause | First-pass fix |
|---|---|---|
| Read-back is the cfg default, not the injected value | the override was applied after the cfg was consumed | pin the range **before** `gym.make`, not after |
| Read-back is close but not equal | reading before the sim settled, or reading a derived field | read immediately after `reset()`, from the raw `data.<field>` |
| `KeyError` on the event term | term name differs from the cfg | read `unw.event_manager.active_terms` off the built env |
| Value correct in env 0, wrong elsewhere | a range that is not actually a point interval | check both ends of every tuple |

## Known traps

- **Dropping the range params because create mode does not randomize** leaves `dr-generator`
  nothing to widen, and §7 then has to re-author §3.
- **Position vs pose ranges** are different parameter names on different event terms; copying
  a block between terms without checking is a silent no-op.

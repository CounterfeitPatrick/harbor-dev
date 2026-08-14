# Tuning rewards

Reward design is a search, and HARBOR runs it as one — with real training runs as the fitness function. A candidate is not scored by asking a model whether the reward looks reasonable; it is scored by training a policy on it and measuring the success rate.

```text
/harbor:reward-tune task=<TaskID> algorithm=ppo pool_size=4 gpus=4
```

The loop runs until `success_rate ≥ success_threshold`, then promotes the winning design onto the source task and re-verifies it there.

## How the search is structured

Two agents, with a boundary between them that exists for a specific reason.

**`reward-tuning-agent` designs and decides.** It reads the §1–§5 analysis first — the failure modes, what the action space can express, the start layout, the subgoal decomposition that *is* the term ladder, and the degenerate states that form the reward-hacking surface. Then it proposes each candidate: a bounded task delta plus a complete reward with concrete weights, gates, and a composer. It never writes reward code.

**`reward-candidate-agent` implements and scores.** One candidate end to end: implement it into its own isolated task, run the smokes for every section it touched, train, render, score the per-term curves and rendered frames, and return a compact verdict.

That split is what keeps the design context clean. Every traceback, log tail, and failed smoke stays on the candidate's side; the agent choosing what to try next sees verdicts, not noise.

## Why candidates change the task, not just the reward

A candidate is a *bounded §1–§5 task delta plus a complete reward*, because a reward can only key on what the observation exposes and can only be achieved by what the action space can express. A search restricted to reweighting terms cannot escape a task whose observation is missing the quantity the reward needs. So the search covers both, and any section a candidate touches must re-pass that section's own smoke.

## Isolation follows the pool

| `pool_size` | Isolation |
|:--:|---|
| 1 | Sequential, editing the source task over a `base/` snapshot |
| > 1 | One slot clone per candidate, each with its own GPU |

In local mode the effective pool is capped by `gpus`. In cluster mode candidates are submitted to SLURM and the pool is bounded by your allocation.

## Scoring

`scripts/reward-tuning-agent/score_iter.py` holds the single success-rate formula, so no two callers can compute it differently. It also refuses to invent a number: a run with no `metrics.jsonl` returns `success_rate: null` with a gate reason like `no_metrics`, rather than a fabricated zero. An ungradable candidate and a failed candidate lead to different next moves, so they must not look alike.

Candidates also report `task_smoke_failed` and `reward_smoke_failed` distinctly — the first means the task delta was wrong, the second means the reward was. Opposite fixes.

## Per-term visibility

Tuning a reward you cannot decompose is guesswork. HARBOR wires per-term logging so every term is visible in the metrics stream, and asserts the decomposition holds every step:

```python
composer(info["detailed_reward"].values()) == env_reward
```

where `composer` is `sum` or `product` per task. If that assertion ever fails, the terms you are reading are not the reward the policy is optimizing — so it is a hard failure, not a warning.

You can add this to any benchmark without changing its native reward:

```text
/harbor:reward-add-log
```

## Experience

After each round, recurring patterns — effective term shapes, unstable ranges, common failure modes — are distilled into an append-only ledger. Later runs retrieve entries filtered by simulator, task, and algorithm before designing. In the paper's measurement this cut a reward redesign on the hardest task from four hours to thirty minutes.

Entries marked `[MUST]` are binding on their reader. For example, magnitude-budget discipline: terms are assigned a share of a fixed total, so no single term can silently dominate the ladder.

## Next

[Train and tune →](/guide/training)

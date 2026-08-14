# Results

All numbers below are from [the paper](https://arxiv.org/abs/2606.08610). Simulation results use five random seeds with 4,096 evaluation rollouts per seed, reported as mean. Real-world results are ten trials per policy.

## End to end, four simulators

The same four task specifications, given to HARBOR against four different simulator codebases with no human in the loop. `Eureka` and `REvolve` are LLM reward-design baselines, given the same model backbone, the same wall-clock budget, and a fixed task implementation — so the comparison isolates reward design.

| Task | HARBOR<br>IsaacLab | Eureka | REvolve | HARBOR<br>ManiSkill | HARBOR<br>Genesis | HARBOR<br>MJLab |
|:--|:--:|:--:|:--:|:--:|:--:|:--:|
| Stack-Cube | **0.885** | 0.000 | 0.000 | **0.936** | **0.935** | 0.221 |
| Insert-Drawer | **0.939** | 0.000 | 0.363 | **0.648** | **0.781** | 0.122 |
| Lift-Box | **1.000** | 0.997 | 0.932 | **1.000** | **0.944** | 1.000 |
| Dex-Grasp | **0.967** | 0.935 | 0.955 | **0.932** | **0.970** | 0.000 |

Two observations worth drawing out.

**The baselines do not fail uniformly — they fail on structure.** On Lift-Box and Dex-Grasp, Eureka and REvolve are competitive. On Stack-Cube and Insert-Drawer they collapse to zero. Those two tasks need a staged reward, where each stage activates only once the previous one is complete. HARBOR builds that ladder from the subgoal decomposition already settled in §4 and from retrieved heuristics; search-from-scratch never finds the staircase.

**Rollout-behavior feedback is what separates the two baselines.** On Insert-Drawer, both HARBOR and REvolve diagnose the real failures — insufficient lifting, collisions with the drawer — from rendered rollouts. Eureka, without that channel, gets stuck.

**MJLab is the honest failure case.** HARBOR could not identify physics parameters yielding stable robot control there, and dexterous control fails outright. Reported rather than dropped.

## Real-world transfer

Policies trained in simulation, transferred through system identification and domain randomization, evaluated over ten trials on hardware.

| Task | from IsaacLab | from ManiSkill | from Genesis | from MJLab |
|:--|:--:|:--:|:--:|:--:|
| Stack-Cube | 0.5 | 0.6 | 0.6 | 0.1 |
| Insert-Drawer | 0.6 | 0.4 | 0.4 | 0.0 |
| Lift-Box | 0.8 | 0.8 | 0.8 | 0.2 |
| Dex-Grasp | 0.9 | 0.7 | 0.7 | 0.0 |

## Reliability, cost, and what each component buys

A clean ManiSkill checkout, building and training a Push-Cube policy as a controlled profiling slice. Five configurations, ten repeats each, five stages per repeat — 50 stage-runs per configuration. Context is cache-read tokens re-read across turns.

| Configuration | Success | Wall-clock | Context | Cost |
|:--|:--:|:--:|:--:|:--:|
| Vanilla agent, no harness | 29/50 | 185.6 min | 82.8M | $182.15 |
| **HARBOR (full)** | **48/50** | **44.1 min** | **28.1M** | **$70.90** |
| without parallel isolation | 46/50 | 83.4 min | 65.3M | $130.68 |
| without gates | 41/50 | 32.9 min | 24.0M | $79.70 |
| without accumulated experience | 32/50 | 53.5 min | 44.4M | $120.27 |

The full harness is simultaneously the most reliable and the cheapest measured configuration — Pareto-optimal on reliability and cost. Each ablation isolates one contribution:

**Isolation buys speed and reliability at once.** Delegating trials to isolated subagents running in parallel cuts the iteration-heavy stages from 49.5 min to 7.9 min (≈6.3×). Without it, serial trials dominate wall-clock and transcript re-reads grow from 28.1M to 65.3M context tokens.

**Gates buy correctness, and cost time.** Removing them is the *fastest* configuration — and it lets a render-path defect pass unnoticed while reward generation and RL tuning both drop to 6/10. Speed achieved by not checking is not speed.

**Experience buys generative reliability.** Without templates, references, and heuristics, reward generation falls to 2/10 and RL tuning to 4/10 — the least reliable configuration on exactly the stages that require producing something new.

## Autonomous hyperparameter tuning

PPO, SAC, and TD3 across twelve tasks in three benchmarks, under a bounded wall-clock budget. Defaults are IsaacLab's for PPO and PQL's for SAC and TD3. Tuned configurations were required to train in at most twice the default's wall-clock, so improvements cannot come from spending more compute.

Tuned configurations match or outperform defaults in **11 of 12** settings. Average area-under-curve improvement is roughly 1,300% on IsaacLab, 238% on Loco-MuJoCo, and 12.3% on Bi-DexHands, with steps-to-threshold improving 18.6%, 60.4%, and 42.2% respectively.

The clearest gains are SAC on Bi-DexHands, where HARBOR-tuned SAC learns `ShadowHandDoorOpenIn` and `ShadowHandDoorCloseIn` — tasks the original SAC baseline fails on in its own paper.

## Experience reuse

Asked to redesign the reward for `stack-cube`, the hardest task, in a separate run with prior experience available, HARBOR completed in 30 minutes against 4 hours from scratch — an 8× speedup.

## Limitations

HARBOR is bounded by the tools exposed to its agents. For genuinely novel tasks with no prior knowledge, it may need many scaffold-and-repair iterations or fail outright.

The sim-to-real boundary remains partly manual: HARBOR automates most of the simulated pipeline, but deployment still requires engineering around robot interfaces and human feedback.

Policy architectures are currently simple. Extending to vision-language-action or world-model policies is additive under this abstraction rather than a redesign, but it has not been done.

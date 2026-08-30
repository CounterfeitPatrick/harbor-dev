# Semantic correctness

A check can confirm that something is structurally valid and still tell you nothing about whether it is the thing you meant.

A rollout can produce finite rewards, correctly shaped observations, and a success predicate that fires at exactly the configured threshold — while the gripper closes on empty air, the mug spawns inside the rack it is supposed to hang on, or the humanoid "jumps" by scooting along the floor. Every number agrees. The task is wrong.

Numbers cannot close this gap, because the gap is between *what you configured* and *what you meant*, and only one of those is written down anywhere a script can read. So HARBOR renders the simulation to images and has the agent look at them.

## Two questions per stage

Wherever a design choice can be misconfigured *and* misconceived, the check is split in two:

| | Question | Form |
|---|---|---|
| Numeric pass | Is the state what you configured? | Assertions on tensors — positions, shapes, finiteness, thresholds |
| Visual pass | Is what you configured what you meant? | Rendered PNGs the agent opens and judges |

The reset section is the clearest case. Its numeric pass verifies that object positions fall inside the configured spawn ranges. Its visual pass renders one frame per reset and asks whether that start layout is a task worth solving — whether the block is reachable, whether the target is visible, whether the arm begins in self-collision. A spawn range can be perfectly implemented and still describe a scene nobody would want.

## Where visuals feed back

Visual judgement is not a final review pass. It is wired into the stages where a wrong answer would otherwise propagate:

| Stage | Artifact | What the agent judges |
|---|---|---|
| Benchmark sanity | `render_random.py` → MP4 | The scene moves at all — a frozen simulation renders a perfectly valid still video |
| §3 Reset | `smoke_s3_frames/` — one PNG per reset | The start distribution is a sane task |
| §4 Termination | `smoke_s4_frames/` — one keyframe per predicate | The predicate fires in the state it was meant to describe |
| §6 Render | `smoke_s6_frames/` — rollout keyframes | Nothing explodes, sinks through the floor, or drifts off-scene |
| Reward candidate | `render.mp4` → extracted `frames/` | What the trained policy *actually does*, written into the verdict as `behavior` |
| Checkpoint render | `/harbor:rl-render` | Inference moved, and consecutive frames differ |

The reward loop is where this matters most. A candidate's scorer owns every number — success rate, per-term curves, peak detection. What it cannot compute is what the robot is doing, so the candidate agent extracts frames from its own rollout and reports behavior in those terms. "Reward went up" is not a behavior. "The arm reaches the cube and hovers, gripper never closes" is — and it tells the designer that the next candidate needs a grasp term, which no curve would have said.

## "Looks correct" is not a validation

A visual pass ends in a written judgement, and the agents are required to record *what they saw* rather than that they looked:

> "handle faces the rack, 18 cm of clear table between them" — a validation
>
> "looks correct" — not one

The distinction is enforceable. A specific claim can be contradicted by the frame it describes; a vague one cannot be wrong, which makes it worthless as evidence. This is the same reason [verdicts are machine truth](/guide/gates) — a check whose result cannot be disputed later is not a check.

## Why the agent is the judge

Frame differencing catches a frozen scene, and a scalar threshold catches a predicate that never fires. Neither can catch a scene that moves incorrectly, or a predicate that fires on the wrong state. That judgement needs a model that can look at a picture of a robot and say whether it is doing the task — which is precisely what a vision-capable agent is for, and is the one check in the pipeline with no deterministic substitute.

Two rules keep it honest. The agent must open the images itself rather than infer from the numeric verdict beside them — a green assertion next to a wrong-looking frame means the assertion is measuring the wrong thing, and that is a finding, not a pass. And when a training run peaked and collapsed, the rendered checkpoint is the best one rather than the last, so the behavior report has to say which policy was actually watched. Conflating them misreports what the reward produced.

## Related

- [Gates](/guide/gates) — the full catalogue of checks, and why frame differencing exists
- [Authoring tasks](/guide/tasks) — where the per-section frames are written
- [Tuning rewards](/guide/rewards) — how `behavior` feeds the next candidate's design

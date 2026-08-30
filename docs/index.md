---
layout: home

hero:
  name: HARBOR
  text: Robot RL, as a request
  tagline: Point it at a simulator. Describe a task. Get a trained policy — with an executable check at every step.
  image:
    src: /logo.svg
    alt: HARBOR
  actions:
    - theme: brand
      text: Get started
      link: /guide/
    - theme: alt
      text: How it works
      link: /guide/harness
    - theme: alt
      text: Read the paper
      link: https://arxiv.org/abs/2606.08610

features:
  - title: Long-horizon automation
    details: Dependency setup, task construction, reward design, algorithm integration, randomization, and tuning run as one workflow. The stages are not separable — each one's choices constrain the next — so automating a single step, as prior work does, leaves the coupling between them to be paid by hand.
  - title: Wall-clock efficiency
    details: The cost is concentrated in the iterative stages, reward engineering and hyperparameter tuning, where every candidate costs a training run. HARBOR fans those out into isolated parallel trials — roughly 6× faster — without any trial's traceback reaching the context deciding what to try next.
  - title: Self-improvement
    details: Human heuristics, previous runs, and a library of existing task specifications are all in-context material. Append-only experience ledgers carry what worked into the next run, and a new task adapts from the closest prior one instead of starting blank — an 8× speedup on a repeated reward design.
  - title: Interpretability and controllability
    details: Every stage writes inspectable code, configs, logs, keyframes, and video into your repository, alongside a design record of why each choice was made. Step in at any gate, correct it, and resume — and when a check stops making progress, the agent stops and asks rather than burning retries.
---

<div style="max-width: 980px; margin: 4rem auto 0; text-align: center;">

## One prompt, End-to-end workflow

It sets up the simulation, writes the task, designs the reward, wires the algorithms, trains the policy — and checks its own work at every step.

<!-- preload=metadata so the file is not pulled down by every visitor who never presses
     play; the poster carries the frame until they do. -->
<video src="/demo.mp4" controls playsinline preload="metadata"
       poster="/walkthrough-poster.webp"
       style="width: 100%; border-radius: 12px;"></video>

## One task, four simulators

The same four descriptions, given to HARBOR against four different simulator codebases.

<img src="/gallery-strip.webp" alt="Stack-Cube, Insert-Drawer, Lift-Box and Dex-Grasp across simulators" style="width: 100%; border-radius: 12px;">

</div>

<div style="max-width: 720px; margin: 3rem auto 0;">

## Why a harness

Reinforcement learning works. The pipeline around it is what costs weeks.

Practitioners build the task, shape the reward, calibrate randomization, tune hyperparameters — and pay that cost again for every new simulator, task, and algorithm. Prior automation targets one stage at a time, so the integration burden between stages is repeatedly re-paid by hand.

HARBOR treats the whole problem as **harness engineering**: shifting human effort from executing each step to designing an agent-readable workflow with verifiable interfaces. Robot RL is unusually well suited to this, because the MDP already exposes stable interfaces — state, action, reward, dynamics, termination — and simulators already produce executable feedback.

HARBOR cannot prove your policy is semantically correct. What it does is turn the common RL engineering failures into **gate failures that surface before they propagate downstream**.

[Read the concepts →](/guide/harness)

</div>

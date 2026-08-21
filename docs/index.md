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
  - title: End to end, not one stage
    details: Dependency setup, task construction, reward design, algorithm integration, domain randomization, and hyperparameter tuning — one continuous workflow rather than six tools you glue together.
  - title: Gated, not hopeful
    details: A stage advances only when an executable check proves it worked. Rollouts, reward curves, and rendered frames are the evidence, so engineering failures surface before a twelve-hour training run, not after.
  - title: Auditable by construction
    details: Every stage writes inspectable code, configs, logs, and video into your repository. Step in at any gate, correct it, and resume — nothing is hidden in a transcript.
  - title: Cheaper the second time
    details: Isolated parallel trials cut iteration-heavy stages by roughly 6×, and an append-only experience ledger carries what worked into the next run — an 8× speedup on a repeated reward design.
---

<div style="max-width: 980px; margin: 4rem auto 0; text-align: center;">

## One prompt, end to end

A single request drives all six stages, from dependency setup to a trained policy. Sound on for the narration.

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

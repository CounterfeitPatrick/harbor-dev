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
    details: A reliable workflow over tightly coupled decisions — related work automates individual steps.
  - title: Wall-clock efficiency
    details: The iterative stages — reward engineering and hyperparameter tuning — are where the clock goes.
  - title: Self-improvement
    details: Human heuristics and existing examples, carried into the next run by in-context learning.
  - title: Interpretability and controllability
    details: Full trace documentation at every stage, and human intervention wherever you want it.
---

<div style="max-width: 980px; margin: 4rem auto 0; text-align: center;">

## One prompt, End-to-end workflow

Set up simulation · Write the task · Design the reward · Wire the algorithms · Train the policy

<!-- preload=metadata so the file is not pulled down by every visitor who never presses
     play; the poster carries the frame until they do. -->
<video src="/demo.mp4" controls playsinline preload="metadata"
       poster="/walkthrough-poster.webp"
       style="width: 100%; border-radius: 12px;"></video>

## One harness, different tasks · robots · simulators

The same task descriptions, given to HARBOR against different simulator codebases. It adapts to each one's APIs, asset formats, and contact model while preserving the task and reward intent — and the harness is embodiment-agnostic, so whole-body locomotion goes through exactly the same pipeline as tabletop manipulation.

<table>
<tr>
  <th align="left" width="118">&nbsp;</th>
  <th align="center">IsaacLab</th>
  <th align="center">ManiSkill</th>
  <th align="center">Genesis</th>
</tr>
<tr>
  <td><b>Stack&#8209;Cube</b><br><sub>long-horizon<br>composition</sub></td>
  <td><img src="/gallery/stack-cube__isaaclab.webp" width="180" alt="Stack-Cube in IsaacLab"></td>
  <td><img src="/gallery/stack-cube__maniskill.webp" width="180" alt="Stack-Cube in ManiSkill"></td>
  <td><img src="/gallery/stack-cube__genesis.webp" width="180" alt="Stack-Cube in Genesis"></td>
</tr>
<tr>
  <td><b>Insert&#8209;Drawer</b><br><sub>articulated<br>interaction</sub></td>
  <td><img src="/gallery/insert-drawer__isaaclab.webp" width="180" alt="Insert-Drawer in IsaacLab"></td>
  <td><img src="/gallery/insert-drawer__maniskill.webp" width="180" alt="Insert-Drawer in ManiSkill"></td>
  <td><img src="/gallery/insert-drawer__genesis.webp" width="180" alt="Insert-Drawer in Genesis"></td>
</tr>
<tr>
  <td><b>Lift&#8209;Box</b><br><sub>bimanual<br>coordination</sub></td>
  <td><img src="/gallery/lift-box__isaaclab.webp" width="180" alt="Lift-Box in IsaacLab"></td>
  <td><img src="/gallery/lift-box__maniskill.webp" width="180" alt="Lift-Box in ManiSkill"></td>
  <td><img src="/gallery/lift-box__genesis.webp" width="180" alt="Lift-Box in Genesis"></td>
</tr>
<tr>
  <td><b>Hang&#8209;Mug</b><br><sub>precise<br>placement</sub></td>
  <td><img src="/gallery/hang-mug__isaaclab.webp" width="180" alt="Hang-Mug in IsaacLab"></td>
  <td><img src="/gallery/hang-mug__maniskill.webp" width="180" alt="Hang-Mug in ManiSkill"></td>
  <td><img src="/gallery/hang-mug__genesis.webp" width="180" alt="Hang-Mug in Genesis"></td>
</tr>
<tr>
  <td><b>Dex&#8209;Grasp</b><br><sub>dexterous<br>control</sub></td>
  <td><img src="/gallery/dex-grasp__isaaclab.webp" width="180" alt="Dex-Grasp in IsaacLab"></td>
  <td><img src="/gallery/dex-grasp__maniskill.webp" width="180" alt="Dex-Grasp in ManiSkill"></td>
  <td><img src="/gallery/dex-grasp__genesis.webp" width="180" alt="Dex-Grasp in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Jump</b><br><sub>whole-body<br>dynamics</sub></td>
  <td><img src="/gallery/g1-jump__isaaclab.webp" width="180" alt="G1 Jump in IsaacLab"></td>
  <td><img src="/gallery/g1-jump__maniskill.webp" width="180" alt="G1 Jump in ManiSkill"></td>
  <td><img src="/gallery/g1-jump__genesis.webp" width="180" alt="G1 Jump in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Footstep</b><br><sub>contact<br>scheduling</sub></td>
  <td><img src="/gallery/g1-footstep__isaaclab.webp" width="180" alt="G1 Footstep in IsaacLab"></td>
  <td><img src="/gallery/g1-footstep__maniskill.webp" width="180" alt="G1 Footstep in ManiSkill"></td>
  <td><img src="/gallery/g1-footstep__genesis.webp" width="180" alt="G1 Footstep in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Bridge&nbsp;Cross</b><br><sub>narrow<br>traverse</sub></td>
  <td><img src="/gallery/g1-bridge-cross__isaaclab.webp" width="180" alt="G1 Bridge Cross in IsaacLab"></td>
  <td><img src="/gallery/g1-bridge-cross__maniskill.webp" width="180" alt="G1 Bridge Cross in ManiSkill"></td>
  <td><img src="/gallery/g1-bridge-cross__genesis.webp" width="180" alt="G1 Bridge Cross in Genesis"></td>
</tr>
<tr>
  <td><b>G1&nbsp;Kick&nbsp;Ball</b><br><sub>dynamic<br>contact</sub></td>
  <td><img src="/gallery/g1-kick-ball__isaaclab.webp" width="180" alt="G1 Kick Ball in IsaacLab"></td>
  <td><img src="/gallery/g1-kick-ball__maniskill.webp" width="180" alt="G1 Kick Ball in ManiSkill"></td>
  <td><img src="/gallery/g1-kick-ball__genesis.webp" width="180" alt="G1 Kick Ball in Genesis"></td>
</tr>
</table>

</div>

<div style="max-width: 720px; margin: 3rem auto 0;">

## Why a harness

Reinforcement learning works. The pipeline around it is what costs weeks.

Practitioners build the task, shape the reward, calibrate randomization, tune hyperparameters — and pay that cost again for every new simulator, task, and algorithm. Prior automation targets one stage at a time, so the integration burden between stages is repeatedly re-paid by hand.

HARBOR treats the whole problem as **harness engineering**: shifting human effort from executing each step to designing an agent-readable workflow with verifiable interfaces. Robot RL is unusually well suited to this, because the MDP already exposes stable interfaces — state, action, reward, dynamics, termination — and simulators already produce executable feedback.

HARBOR cannot prove your policy is semantically correct. What it does is turn the common RL engineering failures into **gate failures that surface before they propagate downstream**.

[Read the concepts →](/guide/harness)

</div>

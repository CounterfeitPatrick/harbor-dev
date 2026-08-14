# Installation

HARBOR needs one host-side tool of its own. Everything else it installs into the target repository's own virtual environment, so it never touches your system Python.

## Prerequisites

| Requirement | Why | Sudo? |
|---|---|:--:|
| [`uv`](https://docs.astral.sh/uv/) | Drives the generated `setup_uv.sh` that builds each repo's `.venv/` | no |
| NVIDIA driver | GPU simulation; `nvidia-smi` must print your device | — |
| CUDA toolkit | Only if your simulator builds CUDA extensions | — |
| Claude Code ≥ 2.1.219 | Nested agent dispatch, which reward tuning depends on | no |

## Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
uv --version && nvidia-smi
```

Both commands must print. If `uv` is not found after `exec $SHELL`, log out and back in so the PATH change takes effect.

::: tip Scripted path
On Ubuntu or Debian you can run the bundled installer instead, which also checks the driver:

```bash
git clone https://github.com/supersglzc/harbor-dev.git ~/harbor
~/harbor/scripts/install/install_prerequisites.sh
```

Pass `--skip-uv` if `uv` is already on PATH, or `--help` for details.
:::

## Install the plugin

Inside Claude Code:

```text
/plugin marketplace add supersglzc/harbor-dev
/plugin install harbor@harbor
```

The marketplace bundles a single plugin named `harbor`. Confirm it loaded:

```text
/harbor:help
```

That prints the full surface — every command, agent, and hook.

## Verify

Run the deterministic test layers, which need no GPU and no simulator:

```text
/harbor:test layers=1,2
```

Layer 1 checks the plugin's own contracts (agent dispatch depth, command invocation rules, script conventions); layer 2 unit-tests the tool scripts. Layer 3 is a full end-to-end pipeline on an isolated worktree and does need a GPU.

## Troubleshooting

**`uv: command not found` after install.** The installer appends to your shell profile; `exec $SHELL` only reloads an interactive shell. Log out and back in.

**Reward tuning reports a version error.** Nested dispatch requires Claude Code 2.1.219 or newer. `/harbor:reward-tune` asserts this in pre-flight and stops rather than silently degrading to a serial loop.

**`nvidia-smi` prints but training cannot see the GPU.** The repo's `.venv/` may have installed a CPU-only torch build. Re-run `/harbor:env-install-uv` — the dependency generator's import smoke checks device availability and will report the mismatch.

## Next

[Set up your first benchmark →](/guide/first-benchmark)

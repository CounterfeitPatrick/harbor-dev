# Installation

HARBOR installs its one host-side tool itself. Everything else goes into the target repository's own virtual environment, so it never touches your system Python.

## Prerequisites

| Requirement | Why | You install it? |
|---|---|:--:|
| Claude Code ≥ 2.1.219 | Nested agent dispatch, which reward tuning depends on | yes |
| NVIDIA driver | GPU simulation; `nvidia-smi` must print your device | yes |
| [`uv`](https://docs.astral.sh/uv/) | Drives the generated `setup_uv.sh` that builds each repo's `.venv/` | no — auto |
| CUDA toolkit | Only if your simulator builds CUDA extensions | no — warned |

Only the first two are yours to arrange. The generated `setup_uv.sh` installs `uv` to
`~/.local/bin` on first use when the host lacks it, and `dependency-generator` warns rather
than failing when a host has the CUDA runtime but no compiler.

## Install `uv` yourself (optional)

The bootstrap covers this, but installing ahead of time is harmless and keeps the first run
offline-free:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
uv --version && nvidia-smi
```

If `uv` is not found after `exec $SHELL`, log out and back in so the PATH change takes effect.

::: tip Scripted path
On Ubuntu or Debian you can run the bundled installer instead:

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

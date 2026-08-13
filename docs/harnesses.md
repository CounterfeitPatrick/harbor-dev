# Native coding-agent harnesses

Harbor keeps one source of truth: `commands/*.md` contains user workflows and
`agents/*.md` contains dispatch-only agents. `tools/generate.py` reads that
Markdown once and delegates native rendering to one adapter per harness.

Supported harnesses are intentionally limited to Claude Code and Codex.

| Harness | Native surface | Storage |
|---|---|---|
| Claude Code | `commands/`, `agents/`, hooks | source of truth; no adapter |
| Codex | `.agents/skills/`, `.codex/agents/` | generated and gitignored |

Run `make generate` to render the Codex tree. `make validate` checks the
original Harbor contracts and adapter behavior.

`make install` performs the complete local setup: it installs the thin
`harbor` launcher to `~/.local/bin`, renders and links Codex, and validates
Claude Code when that CLI is installed. From any working repository,
`harbor claude` loads this checkout through Claude's `--plugin-dir`, while
`harbor codex` refreshes its user-level bundle and hands control to Codex. The
launcher uses process replacement and is not an orchestration runtime.

## Claude Code

The repository root is already a Claude Code plugin. Its `commands/` and
`agents/` Markdown is canonical; generated harnesses never become a second
source that authors must edit.

## Codex

`tools/adapters/codex.py` renders:

- `commands/<name>.md` to
  `.agents/skills/harbor-<name>/SKILL.md`;
- `agents/<name>.md` to `.codex/agents/harbor-<name>.toml` with the required
  `name`, `description`, and `developer_instructions` fields;
- `sandbox_mode = "read-only"` when the source declares an explicit read-only
  tool list, otherwise `workspace-write`; an absent `tools` field inherits
  Claude Code's full toolset and therefore remains writable.
- Claude invocation vocabulary is translated mechanically: `/harbor:<name>`
  and `Skill('<name>')` become Codex `$harbor-<name>` skill references, while
  `AskUserQuestion` becomes `request_user_input`.
- `disable-model-invocation: true` becomes
  `agents/openai.yaml` with `policy.allow_implicit_invocation: false`, so the
  destructive `reset-workspace` skill remains explicit-invocation-only.

[Codex's skill documentation](https://learn.chatgpt.com/docs/build-skills)
budgets the initial skill catalog, not the selected skill body. The adapter
therefore keeps every command body intact in its `SKILL.md`; references remain
an authoring choice rather than a generator-imposed split. Verified
empirically on codex-cli 0.145.0: a 25.6 KB skill body with a canary on its
final line was read completely, so Harbor does not split skill bodies for the
currently tested Codex version.

The in-repository outputs are project-scoped Codex files. The launcher renders
the same files into its user-level bundle so Harbor is available from other
working repositories. Harbor deliberately does not ship a
`.codex-plugin/plugin.json` or Codex marketplace entry: Codex plugins package
skills and integrations, while standalone custom agents use the Codex
configuration surface. A plugin manifest would not install `.codex/agents`.

Harbor claims only the `harbor-*` namespace inside `.agents/skills/` and
`.codex/agents/`: regeneration prunes and rewrites exactly those entries, and
validation ignores everything else, so a project's own skills and agents
coexist untouched.

## Live canary — `make harness-smoke`

`tools/harness_smoke.py` runs a throwaway two-layer plugin (command →
coordinator → worker → `result.json`) on both CLIs from one Markdown source,
judged on the artifact plus a clean CLI exit. It provides end-to-end
evidence static tests cannot: skill discovery, argument passing, `harbor-*`
name resolution, nested dispatch (the reward-tune topology), and
workspace-write — with real model calls, so
it is not part of the deterministic suites. Re-run when the adapter or a
harness CLI version changes. Baseline 2026-08-05: both green (Claude Code
2.1.220 in 37 s; codex-cli 0.145.0 in 78 s).

## Invariants

- No command and agent may share a name.
- Every generated user entrypoint must map to a source command; an agent can
  never be exposed as an entrypoint. Only the `harbor-*` namespace is
  claimed — foreign project entries are preserved and never validated.
- Generated Codex skills retain their complete source command body.
- The declared Claude-only vocabulary set — session tools (`SendMessage`,
  `TaskStop`, `AskUserQuestion`), "the <Tool> tool" prose, and the ad-hoc
  executor dispatch — never survives into the generated Codex tree: the
  shared mapping in `tools/adapters/base.py` rewrites each spelling, and the
  generated-output tests scan the real corpus for that set. Named dispatch
  calls keep their shape but their stems are rewritten to registered
  `harbor-` agent names. Bare backticked tool mentions pass through because
  their surrounding grammar cannot be translated safely.
- Source invocation gates remain gates on harnesses with a native equivalent.
- `${CLAUDE_PLUGIN_ROOT}` is resolved only in generated local artifacts.
- Generated Codex trees are never committed.

No runner, orchestration runtime, provider model, authorization taxonomy, or
worktree manager belongs in this layer.

"""Unit tests for the small, source-only harness generator."""

import importlib.util
import json
import re
import sys

import pytest

from _pluginmeta import ROOT

sys.path.insert(0, str(ROOT / "tools"))
from adapters import ADAPTERS, base, codex  # noqa: E402

_launcher_spec = importlib.util.spec_from_file_location(
    "harbor_launcher", ROOT / "tools" / "harbor.py")
launcher = importlib.util.module_from_spec(_launcher_spec)
_launcher_spec.loader.exec_module(launcher)


@pytest.fixture()
def mini_source(tmp_path):
    src = tmp_path / "src"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "harbor",
        "version": "0.0.1",
        "description": "test plugin",
        "author": {"name": "t"},
        "homepage": "https://example.com",
        "repository": "https://example.com/repo",
        "license": "MIT",
        "keywords": ["test"],
    }))
    (src / "CLAUDE.md").write_text(
        "# test\n\n## Hard constraints\n\n1. Keep this exact.\n\n---\n")
    (src / "commands").mkdir()
    (src / "commands" / "large.md").write_text(
        "---\ndescription: a large command\nargument-hint: x=<v>\n---\n"
        "# large\n\nUses ${CLAUDE_PLUGIN_ROOT}/scripts/x.py\n\n"
        "Run /harbor:small via Skill('small'), then AskUserQuestion.\n\n"
        'Dispatch ONE subagent (`Agent(subagent_type="general-purpose")`), '
        "or spawn a `general-purpose` sub-agent per trial.\n\n"
        "Longer than the Bash tool cap; resume with `SendMessage`; on success "
        "TaskStop each in_flight agent_id. The bash tool is plain English.\n\n"
        "Then Agent(worker, prompt={x}) finishes.\n\n"
        + "word " * 3000)
    (src / "commands" / "small.md").write_text(
        "---\ndescription: a small command\n"
        "disable-model-invocation: true\n---\nbody\n")
    (src / "agents").mkdir()
    (src / "agents" / "worker.md").write_text(
        "---\nname: worker\ndescription: an agent\n"
        "tools: [Read, Write, Edit, Bash, Glob, Grep]\nmodel: opus\n---\nbody\n")
    return base.Source(src)


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_every_adapter_renders_clean(mini_source, tmp_path, name):
    ADAPTERS[name].emit(mini_source, tmp_path)
    assert base.validate(mini_source, tmp_path, ADAPTERS[name]) == []


def test_codex_uses_current_project_scoped_paths(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    skill = tmp_path / ".agents/skills/harbor-large/SKILL.md"
    agent = tmp_path / ".codex/agents/harbor-worker.toml"
    assert skill.is_file()
    assert agent.is_file()
    assert skill.read_text().count("word") == 3000


def test_codex_preserves_the_source_invocation_gate(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    gated = (tmp_path / ".agents/skills/harbor-small/agents/openai.yaml")
    assert gated.read_text() == (
        "policy:\n  allow_implicit_invocation: false\n")
    assert not (tmp_path /
                ".agents/skills/harbor-large/agents/openai.yaml").exists()


def test_plugin_root_token_resolves_to_the_source_root(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    skill = tmp_path / ".agents/skills/harbor-large/SKILL.md"
    text = skill.read_text()
    assert base.PLUGIN_ROOT_TOKEN not in text
    assert f"{mini_source.root}/scripts/x.py" in text


def test_codex_rewrites_claude_invocation_vocabulary(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    text = (tmp_path / ".agents/skills/harbor-large/SKILL.md").read_text()
    assert "$harbor-small" in text
    assert "request_user_input" in text
    assert "/harbor:small" not in text
    assert "Skill('small')" not in text
    # The fixture carries both executor-dispatch spellings (call + prose);
    # neither may survive, and no fallback clause is injected — it would
    # contradict source rules like probe-task's "MUST NOT do this inline".
    assert "general-purpose" not in text
    assert text.count("fresh subagent session") == 2
    assert "inline" not in text
    # Session verbs map to resume-safe equivalents; tool prose is rewritten
    # only in exact-CamelCase form ("the bash tool" is English, not a tool).
    assert "SendMessage" not in text
    assert "a follow-up message to the same subagent session" in text
    assert "TaskStop" not in text
    assert "cancel each in_flight agent_id's subagent" in text
    assert "the shell execution cap" in text
    assert "The bash tool is plain English." in text
    # Named dispatch keeps its shape but must reference the GENERATED name.
    assert "Agent(harbor-worker, prompt={x})" in text
    assert "Agent(worker," not in text


def test_agents_are_never_entrypoints(mini_source, tmp_path):
    checked = 0
    for name, adapter in ADAPTERS.items():
        if adapter.ENTRYPOINTS is None:
            continue
        checked += 1
        out = tmp_path / name
        adapter.emit(mini_source, out)
        base_dir, pattern, _ = adapter.ENTRYPOINTS
        sample = next((out / base_dir).glob(pattern))
        rogue = sample.parent.parent / "harbor-worker" / sample.name
        rogue.parent.mkdir(parents=True)
        rogue.write_text(sample.read_text())
        errors = base.validate(mini_source, out, adapter)
        assert any("agent 'worker'" in error for error in errors)
    assert checked


def test_agent_name_colliding_with_command_is_refused(tmp_path):
    src = tmp_path / "clash"
    (src / ".claude-plugin").mkdir(parents=True)
    (src / ".claude-plugin/plugin.json").write_text(json.dumps({
        "name": "harbor", "version": "0.0.1", "description": "d",
        "author": {"name": "t"}, "homepage": "h", "repository": "r",
        "license": "MIT", "keywords": [],
    }))
    (src / "CLAUDE.md").write_text(
        "# test\n\n## Hard constraints\n\n1. Test.\n\n---\n")
    (src / "commands").mkdir()
    (src / "commands/x.md").write_text("---\ndescription: d\n---\nbody\n")
    (src / "agents").mkdir()
    (src / "agents/x.md").write_text(
        "---\nname: x\ndescription: d\ntools: [Read]\n---\nbody\n")
    with pytest.raises(SystemExit, match="collision"):
        base.Source(src)


def test_generated_agent_toml_parses(mini_source, tmp_path):
    tomllib = pytest.importorskip("tomllib")
    codex.emit(mini_source, tmp_path)
    with open(tmp_path / ".codex/agents/harbor-worker.toml", "rb") as handle:
        parsed = tomllib.load(handle)
    assert {"name", "description", "developer_instructions"} <= parsed.keys()


def test_codex_sandbox_distinguishes_missing_tools_from_empty(tmp_path):
    src = tmp_path / "src"
    (src / "commands").mkdir(parents=True)
    (src / "commands/c.md").write_text("---\ndescription: d\n---\nbody\n")
    (src / "agents").mkdir()
    (src / "agents/default-tools.md").write_text(
        "---\nname: default-tools\ndescription: d\n---\nbody\n")
    (src / "agents/no-tools.md").write_text(
        "---\nname: no-tools\ndescription: d\ntools: []\n---\nbody\n")
    (src / "agents/reader.md").write_text(
        "---\nname: reader\ndescription: d\ntools: [Read, Grep]\n---\nbody\n")
    codex.emit(base.Source(src), tmp_path)

    def sandbox(stem):
        text = (tmp_path / f".codex/agents/harbor-{stem}.toml").read_text()
        return re.search(r'sandbox_mode = "([a-z-]+)"', text).group(1)

    assert sandbox("default-tools") == "workspace-write"
    assert sandbox("no-tools") == "read-only"
    assert sandbox("reader") == "read-only"


def test_codex_argument_hint_nests_under_skill_metadata(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    text = (tmp_path / ".agents/skills/harbor-large/SKILL.md").read_text()
    fm, _ = base.parse_frontmatter(text)
    assert "argument-hint" not in fm
    assert 'metadata:\n  argument-hint: "x=<v>"' in text
    small = (tmp_path / ".agents/skills/harbor-small/SKILL.md").read_text()
    assert "metadata:" not in small


def test_codex_does_not_claim_an_invalid_plugin_registry(mini_source, tmp_path):
    codex.emit(mini_source, tmp_path)
    assert not (tmp_path / ".codex-plugin").exists()
    assert not (tmp_path / ".agents/plugins").exists()


def test_codex_preserves_foreign_project_extensions(mini_source, tmp_path):
    foreign_skill = tmp_path / ".agents/skills/other/SKILL.md"
    foreign_agent = tmp_path / ".codex/agents/other.toml"
    foreign_skill.parent.mkdir(parents=True)
    foreign_agent.parent.mkdir(parents=True)
    foreign_skill.write_text("foreign skill")
    foreign_agent.write_text("foreign agent")
    codex.emit(mini_source, tmp_path)
    assert foreign_skill.read_text() == "foreign skill"
    assert foreign_agent.read_text() == "foreign agent"
    # harbor claims only its namespace: foreign entries are preserved AND
    # ignored by validation — generate must stay green next to them
    assert base.validate(mini_source, tmp_path, codex) == []


def test_launcher_links_only_harbor_namespace(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "harbor-one").mkdir(parents=True)
    (target / "foreign").mkdir(parents=True)

    launcher._replace_links(source, target, "harbor-*")

    assert (target / "harbor-one").is_symlink()
    assert (target / "foreign").is_dir()


def test_launcher_refuses_non_symlink_harbor_collision(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "harbor-one").mkdir(parents=True)
    (target / "harbor-one").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="refusing to replace"):
        launcher._replace_links(source, target, "harbor-*")


def test_launcher_install_is_idempotent(tmp_path):
    installed = launcher.install_launcher(tmp_path)
    assert installed.is_symlink()
    assert launcher.install_launcher(tmp_path) == installed


def test_launcher_replaces_only_the_retired_uv_entrypoint(tmp_path):
    old = tmp_path / ".local/share/uv/tools/harbor-cli/bin/harbor"
    old.parent.mkdir(parents=True)
    old.write_text("old")
    target = tmp_path / ".local/bin/harbor"
    target.parent.mkdir(parents=True)
    target.symlink_to(old)

    assert launcher.install_launcher(tmp_path) == target
    assert target.resolve() == (ROOT / "tools/harbor.py").resolve()


def test_install_command_prepares_both_harnesses(monkeypatch, tmp_path, capsys):
    seen = []
    target = tmp_path / ".local/bin/harbor"
    monkeypatch.setattr(launcher, "install_launcher", lambda: target)
    monkeypatch.setattr(launcher, "sync_codex", lambda: seen.append("codex"))
    monkeypatch.setattr(launcher, "sync_claude", lambda: seen.append("claude"))
    monkeypatch.setattr(
        launcher.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setenv("PATH", str(target.parent))

    assert launcher.main(["install"]) == 0
    assert seen == ["codex", "claude"]
    assert "ready: harbor claude | harbor codex" in capsys.readouterr().out


def test_claude_launcher_loads_live_checkout_and_preserves_args(monkeypatch):
    seen = {}
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/bin/claude")
    monkeypatch.setattr(
        launcher.os, "execv",
        lambda executable, argv: seen.update(executable=executable, argv=argv),
    )

    launcher.launch("claude", ["--resume"])

    assert seen == {
        "executable": "/bin/claude",
        "argv": ["/bin/claude", "--plugin-dir", str(launcher.ROOT), "--resume"],
    }


def test_codex_launcher_syncs_then_preserves_args(monkeypatch):
    seen = {"synced": False}
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/bin/codex")
    monkeypatch.setattr(
        launcher, "sync_codex", lambda: seen.update(synced=True))
    monkeypatch.setattr(
        launcher.os, "execv",
        lambda executable, argv: seen.update(executable=executable, argv=argv),
    )

    launcher.launch("codex", ["resume", "--last"])

    assert seen == {
        "synced": True,
        "executable": "/bin/codex",
        "argv": ["/bin/codex", "resume", "--last"],
    }


def test_codex_sync_populates_user_scoped_links(tmp_path):
    launcher.sync_codex(tmp_path)

    skill_links = list((tmp_path / ".agents/skills").glob("harbor-*"))
    agent_links = list((tmp_path / ".codex/agents").glob("harbor-*.toml"))
    assert skill_links and all(path.is_symlink() for path in skill_links)
    assert agent_links and all(path.is_symlink() for path in agent_links)


@pytest.fixture(scope="module")
def real_source():
    return base.Source(base.ROOT)


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_real_plugin_renders_clean(real_source, tmp_path, name):
    ADAPTERS[name].emit(real_source, tmp_path)
    assert base.validate(real_source, tmp_path, ADAPTERS[name]) == []


# Claude-only vocabulary that must never reach a generated tree: session
# tools Codex lacks, the ad-hoc executor dispatch (either spelling),
# and Claude-idiom phrases with a mapped equivalent. Named dispatch calls are
# NOT in this set — they keep their shape, with stems rewritten to the
# generated `harbor-` names (enforced by the dispatch-name test below).
# Checked against the REAL corpus so a new spelling in any command is either
# mapped or caught here — not silently shipped.
CLAUDE_ONLY = ("AskUserQuestion", "SendMessage", "TaskStop",
               'subagent_type="general-purpose"', "`general-purpose` sub-agent",
               "multiple Agent calls")


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_real_corpus_carries_no_claude_only_vocabulary(real_source, tmp_path, name):
    ADAPTERS[name].emit(real_source, tmp_path)
    leaked = [(str(p.relative_to(tmp_path)), token)
              for p in sorted(tmp_path.rglob("*")) if p.is_file()
              for token in CLAUDE_ONLY
              if token in p.read_text(encoding="utf-8", errors="replace")]
    assert not leaked, (
        f"Claude-only vocabulary leaked into generated output: {leaked}. "
        "Fix: map the spelling in tools/adapters/base.py (VOCAB/TOOL_PROSE) "
        "or rephrase the source.")


@pytest.mark.parametrize("name", sorted(ADAPTERS))
def test_real_corpus_dispatch_names_resolve_to_generated_agents(
        real_source, tmp_path, name):
    """Every Agent(<stem>, ...) surviving into a generated tree must name an
    agent that tree actually registers — i.e. the harbor- prefixed form."""
    ADAPTERS[name].emit(real_source, tmp_path)
    stems = {agent["stem"] for agent in real_source.agents}
    dispatch = re.compile(r"Agent\(([\w-]+)\s*[,)]")
    bad = []
    for path in sorted(tmp_path.rglob("*")):
        if not path.is_file():
            continue
        for match in dispatch.finditer(
                path.read_text(encoding="utf-8", errors="replace")):
            ref = match.group(1)
            if not (ref.startswith("harbor-") and ref[len("harbor-"):] in stems):
                bad.append((str(path.relative_to(tmp_path)), ref))
    assert not bad, (
        f"dispatch calls reference names the tree does not register: {bad}. "
        "Fix: the stem must be a real agent (prefix_agent_dispatch rewrites "
        "known stems to their generated harbor- names).")


def test_real_corpus_executor_dispatch_stays_consistent(real_source, tmp_path):
    """The executor rewrite must not contradict the source rules around it:
    probe-task forbids inline execution and rl-sweep mandates parallel
    dispatch, so no injected fallback clause may say otherwise."""
    codex.emit(real_source, tmp_path)
    for path in (".agents/skills/harbor-probe-task/SKILL.md",
                 ".agents/skills/harbor-reset-workspace/SKILL.md",
                 ".agents/skills/harbor-test/SKILL.md",
                 ".agents/skills/harbor-rl-sweep/SKILL.md"):
        text = (tmp_path / path).read_text(encoding="utf-8")
        assert "fresh subagent session" in text, path
        assert "if unavailable" not in text, path
    sweep = (tmp_path / ".agents/skills/harbor-rl-sweep/SKILL.md").read_text(
        encoding="utf-8")
    assert "multiple subagent dispatches" in sweep
    assert "**Run in parallel**" in sweep

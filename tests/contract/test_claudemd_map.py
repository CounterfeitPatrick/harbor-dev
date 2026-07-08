"""Contract: the CLAUDE.md architecture map stays in sync with disk.

Bidirectional: no CLAUDE.md reference points at a missing file, and every
command/agent on disk is documented.
"""
import re

import pytest

from _pluginmeta import AGENTS, COMMANDS, ROOT

CLAUDEMD = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_claudemd_command_refs_exist():
    missing = sorted(
        r for r in set(re.findall(r"commands/([\w-]+)\.md", CLAUDEMD))
        if not (ROOT / "commands" / f"{r}.md").exists()
    )
    assert not missing, f"CLAUDE.md references missing command files: {missing}"


def test_claudemd_agent_refs_exist():
    missing = sorted(
        r for r in set(re.findall(r"agents/([\w-]+)\.md", CLAUDEMD))
        if not (ROOT / "agents" / f"{r}.md").exists()
    )
    assert not missing, f"CLAUDE.md references missing agent files: {missing}"


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_every_command_documented(path):
    name = path.stem
    assert f"commands/{name}.md" in CLAUDEMD or f"/harbor:{name}" in CLAUDEMD, \
        f"command '{name}' is not documented in CLAUDE.md"


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.name)
def test_every_agent_documented(path):
    name = path.stem
    assert f"agents/{name}.md" in CLAUDEMD or f"`{name}`" in CLAUDEMD, \
        f"agent '{name}' is not documented in CLAUDE.md"

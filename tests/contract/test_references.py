"""Contract: in-repo references resolve (no dangling links).

Catches the class of bug found pre-open-source (deleted decision-matrix still
referenced, a `claude-harbor/` link, a /harbor:<cmd> typo).
"""
import re

import pytest

from _pluginmeta import AGENTS, COMMANDS, REFERENCES, ROOT

DOC_FILES = COMMANDS + AGENTS + REFERENCES

_PATH_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s`)\"'>]+)")
_CMD_RE = re.compile(r"/harbor:([a-z][a-z-]*)")


def _is_placeholder(ref):
    return any(c in ref for c in "<*{")


@pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_references_resolve(path):
    text = path.read_text(encoding="utf-8")
    missing = []

    for ref in _PATH_RE.findall(text):
        if _is_placeholder(ref):
            continue
        clean = ref.rstrip(".,:;")
        if not (ROOT / clean).exists():
            missing.append(f"${{CLAUDE_PLUGIN_ROOT}}/{clean}")

    for cmd in set(_CMD_RE.findall(text)):
        if not (ROOT / "commands" / f"{cmd}.md").exists():
            missing.append(f"/harbor:{cmd}")

    assert not missing, f"{path.relative_to(ROOT)}: dangling reference(s): {missing}"

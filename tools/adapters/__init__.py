"""Harness adapter registry.

Claude Code is the source of truth and has no adapter; Codex is rendered from
it through the interface documented in `base.py`.
"""

from . import codex

ADAPTERS = {codex.NAME: codex}

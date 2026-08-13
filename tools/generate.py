#!/usr/bin/env python3
"""Render harness-native artifacts from the Claude-native plugin source.

The repository root IS the Claude Code plugin (single source of truth):
commands/*.md are the skills, agents/*.md the subagents. Following
wshobson/agents, Codex consumes the same Markdown source through a small
adapter under tools/adapters/:

  codex     .agents/skills/ + .codex/agents/ (generated, gitignored)

This file is only the CLI: it loads the source once, dispatches the selected
adapters, runs the unified validation (base.validate — the entrypoint-
separation and token gates) on each output.
"""

import argparse
import sys
from pathlib import Path

from adapters import ADAPTERS, base


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", choices=(*ADAPTERS, "all"), default="all")
    parser.add_argument("--out", type=Path, default=base.ROOT,
                        help="output root (defaults to the repo root)")
    args = parser.parse_args(argv)

    src = base.Source(base.ROOT)
    names = list(ADAPTERS) if args.harness == "all" else [args.harness]
    failures = []
    for name in names:
        adapter = ADAPTERS[name]
        adapter.emit(src, args.out)
        errors = base.validate(src, args.out, adapter)
        failures += errors
        print(f"  {name:<7} {'FAIL: ' + errors[0] if errors else 'ok'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

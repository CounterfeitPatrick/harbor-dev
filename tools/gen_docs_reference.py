#!/usr/bin/env python3
"""Render the docs site's reference pages from the plugin's own command and agent files.

The reference is the one part of the documentation that must never drift from the code,
and the only reliable way to guarantee that is to not write it by hand. This reads
`commands/*.md` and `agents/*.md` — the definitions Claude Code actually loads — and emits
`docs/guide/{commands,agents}.md`. CI runs it and fails if the result differs from
what is committed, so a command whose description changes cannot ship stale docs.

Usage: tools/gen_docs_reference.py [--check]
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "guide"
REPO_URL = "https://github.com/supersglzc/harbor-dev"

# Commands are grouped by filename prefix, which is the only grouping mechanism Claude Code
# offers — there is no real subdirectory namespace for commands.
GROUPS = [
    ("env", "Environment", "Set up a Python GPU robotics repository and its virtual environment."),
    ("probe", "Probing", "Inspect an existing benchmark or task and emit a portable specification."),
    ("task", "Task authoring", "Create, list, and clone tasks inside a benchmark."),
    ("reward", "Reward engineering", "Design and tune the reward, validated by actual training."),
    ("rl", "Training and tuning", "Train, evaluate, render, sweep, and tune RL policies."),
    ("", "Utilities", "Plotting, account setup, experience ledgers, workspace reset, and tests."),
]


def parse_frontmatter(text):
    """Return (fields, body). Handles both `key: value` and YAML block scalars (`key: |`)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end], text[end + 4:]
    fields, key = {}, None
    for line in raw.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            fields[key] = "" if val == "|" else val
        elif key:
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields, body


def first_sentence(desc):
    """The description doubles as Claude's dispatch trigger, so it ends with a long
    'Use when the user types ...' clause that is noise in a reference table."""
    desc = re.split(r"\s*Use when\b", desc)[0]
    desc = re.split(r"\s*PREREQUISITE:", desc)[0]
    return " ".join(desc.split()).strip()


def prose(text):
    """VitePress compiles rendered markdown as a Vue template, so the `<repo>` and
    `<path>` placeholders these descriptions are full of parse as unclosed HTML tags and
    fail the build. Escape them wherever the text lands outside a code span."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def cell(text):
    """As above, plus pipes — an unescaped `|` inside a table cell ends the column, and
    argument hints like `algorithm=<ppo|sac|td3>` are full of them."""
    return prose(text).replace("|", "\\|")


def render_commands():
    files = sorted((ROOT / "commands").glob("*.md"))
    claimed, lines = set(), []
    lines += ["# Commands", "",
              "Every HARBOR command, generated from the plugin source. "
              "Invoke any of them as `/harbor:<name>`.", ""]
    for prefix, title, blurb in GROUPS:
        if prefix:
            group = [p for p in files if p.stem.startswith(prefix + "-")]
        else:
            group = [p for p in files if p not in claimed]
        group = [p for p in group if p not in claimed]
        if not group:
            continue
        claimed.update(group)
        lines += [f"## {title}", "", blurb, "",
                  "| Command | Arguments | Purpose |", "|---|---|---|"]
        for p in sorted(group):
            fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
            hint = fm.get("argument-hint", "").strip().strip('"')
            lines.append(
                f"| [`{p.stem}`]({REPO_URL}/blob/main/commands/{p.name}) "
                f"| {'`' + cell(hint) + '`' if hint else '—'} "
                f"| {cell(first_sentence(fm.get('description', '')))} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_agents():
    files = sorted((ROOT / "agents").glob("*.md"))
    lines = ["# Agents", "",
             "Each agent owns one bounded stage of the workflow and runs in its own isolated "
             "context. Only `reward-tuning-agent` dispatches workers of its own; every other "
             "agent is a leaf, which is what keeps dispatch depth at two.", ""]
    for p in files:
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        name = fm.get("name", p.stem)
        tools = fm.get("tools", "").strip("[]")
        lines += [f"## `{name}`", "",
                  prose(first_sentence(fm.get("description", ""))), "",
                  f"**Tools** · {tools or '—'}  ",
                  f"**Source** · [`agents/{p.name}`]({REPO_URL}/blob/main/agents/{p.name})", ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated pages differ from what is on disk")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, text in (("commands.md", render_commands()), ("agents.md", render_agents())):
        path = OUT / name
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if args.check:
            if current != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")

    if stale:
        print("stale reference docs (run tools/gen_docs_reference.py): " + ", ".join(stale),
              file=sys.stderr)
        return 1
    if args.check:
        print("reference docs are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())

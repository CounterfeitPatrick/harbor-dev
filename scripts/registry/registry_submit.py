#!/usr/bin/env python3
"""
Append an unverified entry to mcp/harbor/data/benchmarks.yaml.

Used by the /benchmark submit skill flow. Pure text append: no YAML round-trip
is performed, so the existing file's formatting is preserved exactly. The new
block is written with the project's flush-left sequence style (`- name:`
aligned with `benchmarks:`, two-space sub-keys).

Usage:
    python3 registry_submit.py \
        --name <name> --user-id <gh-user> --github <url> --image <docker-tag> \
        --category {il|rl|mixed} --notes <text>

Exit codes: 0 ok, 1 bad args, 2 duplicate name.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
DATA_DIR = PLUGIN_ROOT / "mcp" / "harbor" / "data"


def _yaml_quote(s: str) -> str:
    """Return YAML single-quoted scalar; doubles any internal single quote."""
    return "'" + s.replace("'", "''") + "'"


def _entry_block(args: argparse.Namespace) -> str:
    return (
        f"- name: {args.name}\n"
        f"  image: {args.image}\n"
        f"  image_id: ''\n"
        f"  size: ''\n"
        f"  github: {args.github}\n"
        f"  user_id: {args.user_id}\n"
        f"  category: {args.category}\n"
        f"  status: unverified\n"
        f"  submitted_at: {args.submitted_at}\n"
        f"  verified_at: ''\n"
        f"  notes: {_yaml_quote(args.notes)}\n"
    )


def _name_exists(text: str, name: str) -> bool:
    pattern = re.compile(rf"^- name: {re.escape(name)}\s*$", re.MULTILINE)
    return bool(pattern.search(text))


def _ensure_top_list_present(text: str, top_key: str) -> str:
    """Replace `<top_key>: []` with `<top_key>:` so the new entry can be appended."""
    empty_pattern = re.compile(rf"^{re.escape(top_key)}:\s*\[\s*\]\s*$", re.MULTILINE)
    return empty_pattern.sub(f"{top_key}:", text, count=1)


def _next_steps_message(name: str) -> str:
    branch = f"registry/submit-benchmark-{name}"
    return (
        "\n[next steps] open a PR (run from the plugin repo root):\n"
        f"  git checkout -b {branch}\n"
        f"  git add mcp/harbor/data/benchmarks.yaml\n"
        f"  git commit -m 'submit(benchmark): {name}'\n"
        f"  git push -u origin {branch}\n"
        "  gh pr create --fill   # or open the URL git push prints\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--user-id", dest="user_id", required=True)
    p.add_argument("--github", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--category", required=True, choices=["il", "rl", "mixed"])
    p.add_argument("--submitted-at", dest="submitted_at",
                   default=_dt.date.today().isoformat())
    p.add_argument("--dry-run", action="store_true",
                   help="Print the would-be entry block and exit; do not write.")
    args = p.parse_args(argv)

    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.name):
        p.error(f"--name {args.name!r} must be lowercase letters/digits/hyphens, "
                "starting with a letter.")

    yaml_path = DATA_DIR / "benchmarks.yaml"
    top_key = "benchmarks"
    if not yaml_path.exists():
        print(f"[error] registry file not found: {yaml_path}", file=sys.stderr)
        return 1

    text = yaml_path.read_text(encoding="utf-8")

    if _name_exists(text, args.name):
        print(f"[error] entry '{args.name}' already exists in {yaml_path.name}.\n"
              f"        run /benchmark verify {args.name} to graduate it, or pick"
              f" a different --name.", file=sys.stderr)
        return 2

    block = _entry_block(args)

    if args.dry_run:
        print(block, end="")
        return 0

    text = _ensure_top_list_present(text, top_key)
    if not text.endswith("\n"):
        text += "\n"
    text += block

    yaml_path.write_text(text, encoding="utf-8")

    print(f"[ok] appended '{args.name}' to mcp/harbor/data/benchmarks.yaml "
          f"as status=unverified")
    print(_next_steps_message(args.name), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Promote a benchmark registry entry from status=unverified to status=verified,
and fill image_id + size from `docker image inspect`.

Used by the /benchmark verify <name> skill flow. Pure line-replacement within
the targeted entry's range — no YAML round-trip, so the rest of the file is
untouched byte-for-byte.

Usage:
    python3 registry_verify.py --name <name>
        [--no-docker --image-id <id> --size <human-size>]
        [--verified-at <YYYY-MM-DD>]
        [--dry-run]

Exit codes: 0 ok, 1 bad args, 2 entry not found / docker failure.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
DATA_DIR = PLUGIN_ROOT / "mcp" / "harbor" / "data"


def _humanize_bytes(n: int) -> str:
    """Match `docker images` SIZE column: base-1000, 1 decimal where useful, GB for >= 1e9.

    Examples (verified against `docker images`):
        14_842_341_888 -> "14.8GB"
        20_001_000_000 -> "20GB"
         8_362_000_000 -> "8.36GB"
    """
    units = [("GB", 1e9), ("MB", 1e6), ("kB", 1e3)]
    for suffix, scale in units:
        if n >= scale:
            v = n / scale
            if v >= 100:
                return f"{v:.0f}{suffix}"
            if v >= 10:
                return f"{v:.1f}{suffix}".rstrip("0").rstrip(".") + (
                    "" if "." in f"{v:.1f}" else suffix
                )
            return f"{v:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{n}B"


def _docker_inspect(image: str) -> tuple[str, str]:
    """Return (image_id_12, human_size). Raises subprocess.CalledProcessError on failure."""
    out = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}} {{.Size}}", image],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    full_id, size_bytes = out.split()
    image_id_12 = full_id.removeprefix("sha256:")[:12]
    size = _humanize_bytes(int(size_bytes))
    return image_id_12, size


def _find_entry_range(text: str, name: str) -> tuple[int, int] | None:
    """Return (start_line_idx, end_line_idx_exclusive) for the entry's lines, or None."""
    lines = text.splitlines(keepends=True)
    name_re = re.compile(rf"^- name: {re.escape(name)}\s*$")
    start = None
    for i, ln in enumerate(lines):
        if name_re.match(ln):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- "):
            end = j
            break
    return start, end


def _replace_in_range(lines: list[str], start: int, end: int,
                      key: str, new_value: str) -> bool:
    """In lines[start:end], replace the first `  <key>: ...` line's value with new_value."""
    pat = re.compile(rf"^(  {re.escape(key)}: ).*$")
    for i in range(start, end):
        m = pat.match(lines[i].rstrip("\n"))
        if m:
            lines[i] = f"{m.group(1)}{new_value}\n"
            return True
    return False


def _read_image_field(lines: list[str], start: int, end: int) -> str | None:
    pat = re.compile(r"^  image: (.+)$")
    for i in range(start, end):
        m = pat.match(lines[i].rstrip("\n"))
        if m:
            return m.group(1).strip()
    return None


def _read_status(lines: list[str], start: int, end: int) -> str | None:
    pat = re.compile(r"^  status: (.+)$")
    for i in range(start, end):
        m = pat.match(lines[i].rstrip("\n"))
        if m:
            return m.group(1).strip()
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--image-id", dest="image_id",
                   help="Override image_id (12-char). Required with --no-docker.")
    p.add_argument("--size", help="Override size string (e.g. 14.8GB). Required with --no-docker.")
    p.add_argument("--no-docker", dest="no_docker", action="store_true",
                   help="Skip `docker image inspect`; use --image-id/--size as-is.")
    p.add_argument("--verified-at", dest="verified_at",
                   default=_dt.date.today().isoformat())
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    if args.no_docker and not (args.image_id and args.size):
        p.error("--no-docker requires both --image-id and --size")

    yaml_path = DATA_DIR / "benchmarks.yaml"
    if not yaml_path.exists():
        print(f"[error] registry file not found: {yaml_path}", file=sys.stderr)
        return 1

    text = yaml_path.read_text(encoding="utf-8")
    rng = _find_entry_range(text, args.name)
    if rng is None:
        print(f"[error] no entry named '{args.name}' in {yaml_path.name}.\n"
              f"        try /benchmark list all to see candidates.", file=sys.stderr)
        return 2
    start, end = rng

    lines = text.splitlines(keepends=True)
    current_status = _read_status(lines, start, end)
    if current_status == "verified":
        print(f"[warn] '{args.name}' is already verified. Refreshing image_id, "
              f"size, and verified_at.", file=sys.stderr)

    image_tag = _read_image_field(lines, start, end)
    if image_tag is None:
        print(f"[error] entry '{args.name}' has no `image:` field.", file=sys.stderr)
        return 2

    if args.no_docker:
        image_id = args.image_id
        size = args.size
    else:
        try:
            image_id, size = _docker_inspect(image_tag)
        except FileNotFoundError:
            print("[error] `docker` CLI not found on PATH. re-run with --no-docker "
                  "and pass --image-id/--size manually.", file=sys.stderr)
            return 2
        except subprocess.CalledProcessError as e:
            print(f"[error] `docker image inspect {image_tag}` failed:\n"
                  f"{e.stderr.strip() if e.stderr else ''}\n"
                  f"        run `docker pull {image_tag}` first, or pass --no-docker "
                  f"with --image-id/--size.", file=sys.stderr)
            return 2
        if args.image_id:
            image_id = args.image_id
        if args.size:
            size = args.size

    changed_status = _replace_in_range(lines, start, end, "status", "verified")
    changed_image_id = _replace_in_range(lines, start, end, "image_id", image_id)
    changed_size = _replace_in_range(lines, start, end, "size", size)
    changed_verified_at = _replace_in_range(lines, start, end, "verified_at",
                                            args.verified_at)

    if not (changed_status and changed_image_id and changed_size and changed_verified_at):
        missing = [k for k, v in [
            ("status", changed_status), ("image_id", changed_image_id),
            ("size", changed_size), ("verified_at", changed_verified_at),
        ] if not v]
        print(f"[error] entry '{args.name}' is missing required field(s): "
              f"{', '.join(missing)}. registry schema may have drifted.",
              file=sys.stderr)
        return 2

    new_text = "".join(lines)

    if args.dry_run:
        sys.stdout.write(new_text)
        return 0

    yaml_path.write_text(new_text, encoding="utf-8")

    print(f"[ok] {args.name} -> status=verified, image_id={image_id}, size={size}, "
          f"verified_at={args.verified_at}")
    print("\n[next steps] stage and commit:")
    print(f"  git add mcp/harbor/data/benchmarks.yaml")
    print(f"  git commit -m 'verify(benchmark): {args.name}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Launch Claude Code or Codex with the current Harbor checkout attached.

This is deliberately a thin native-session launcher. It prepares Harbor's
harness files, then replaces itself with the vendor CLI; it does not proxy the
session, orchestrate providers, create worktrees, or interpret vendor flags.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("claude", "codex")


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False)


def _replace_links(source_dir: Path, target_dir: Path, pattern: str) -> None:
    """Mirror Harbor-owned entries as symlinks without touching foreign data."""
    sources = {path.name: path.resolve() for path in source_dir.glob(pattern)}
    target_dir.mkdir(parents=True, exist_ok=True)

    conflicts = [
        path for path in target_dir.glob(pattern)
        if not path.is_symlink()
    ]
    if conflicts:
        names = ", ".join(str(path) for path in conflicts)
        raise RuntimeError(f"refusing to replace non-symlink Harbor entries: {names}")

    for path in target_dir.glob(pattern):
        if path.name not in sources:
            path.unlink()

    for name, source in sources.items():
        target = target_dir / name
        if target.is_symlink():
            if target.resolve(strict=False) == source:
                continue
            target.unlink()
        target.symlink_to(source, target_is_directory=source.is_dir())


def sync_codex(home: Path | None = None) -> None:
    """Render Codex files and expose them through Codex's user-level roots."""
    home = home or Path.home()
    bundle = home / ".local" / "share" / "harbor" / "codex"
    result = _run([
        sys.executable, str(ROOT / "tools" / "generate.py"),
        "--harness", "codex", "--out", str(bundle),
    ])
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Codex generation failed")

    _replace_links(
        bundle / ".agents" / "skills", home / ".agents" / "skills",
        "harbor-*",
    )
    _replace_links(
        bundle / ".codex" / "agents", home / ".codex" / "agents",
        "harbor-*.toml",
    )


def sync_claude() -> None:
    """Validate the live Claude source used by ``harbor claude``."""
    executable = shutil.which("claude")
    if executable is None:
        raise RuntimeError("'claude' is not installed or not on PATH")
    result = _run([executable, "plugin", "validate", str(ROOT)])
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(detail or "Claude plugin validation failed")


def install_launcher(home: Path | None = None) -> Path:
    """Install a safe symlink in the user's conventional local bin directory."""
    home = home or Path.home()
    target = home / ".local" / "bin" / "harbor"
    source = Path(__file__).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.is_symlink():
        current = target.resolve(strict=False)
        old_uv_launcher = "/uv/tools/harbor-cli/bin/harbor" in str(current)
        if current != source and not old_uv_launcher:
            raise RuntimeError(
                f"refusing to replace unrelated launcher symlink: {target} -> {current}")
        if current == source:
            return target
        target.unlink()
    elif target.exists():
        raise RuntimeError(f"refusing to replace existing launcher: {target}")

    target.symlink_to(source)
    return target


def launch(provider: str, args: list[str]) -> None:
    """Prepare Harbor, then hand the terminal to the unwrapped vendor CLI."""
    executable = shutil.which(provider)
    if executable is None:
        raise SystemExit(f"harbor: '{provider}' is not installed or not on PATH")

    if provider == "codex":
        try:
            sync_codex()
        except (OSError, RuntimeError) as exc:
            print(f"harbor: Codex sync failed ({exc}); launching anyway",
                  file=sys.stderr)
        command = [executable, *args]
    else:
        # Claude reads the checkout directly, so it is always current. The
        # local source also takes precedence over an installed Harbor plugin.
        command = [executable, "--plugin-dir", str(ROOT), *args]

    os.execv(executable, command)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Keep provider argv opaque: no argparse layer may consume vendor flags.
    if argv and argv[0] in PROVIDERS:
        launch(argv[0], argv[1:])
        return 0

    parser = argparse.ArgumentParser(
        prog="harbor",
        description="Prepare Harbor and launch a native Claude Code or Codex session.",
        epilog=("native sessions:\n"
                "  harbor claude [args...]  load the live Claude plugin\n"
                "  harbor codex [args...]   sync, then launch Codex"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="prepare native harness files")
    sync_parser.add_argument("provider", nargs="?", choices=PROVIDERS)
    subparsers.add_parser("install", help="install the harbor launcher symlink")
    args = parser.parse_args(argv)

    try:
        if args.command == "install":
            target = install_launcher()
            print(f"  launcher ok ({target})")
            failed = False
            try:
                sync_codex()
                suffix = "" if shutil.which("codex") else " (Codex CLI not found)"
                print(f"  codex   ok (generated and linked){suffix}")
            except (OSError, RuntimeError) as exc:
                failed = True
                print(f"  codex   FAIL ({exc})", file=sys.stderr)
            if shutil.which("claude"):
                try:
                    sync_claude()
                    print("  claude  ok (live plugin source validated)")
                except (OSError, RuntimeError) as exc:
                    failed = True
                    print(f"  claude  FAIL ({exc})", file=sys.stderr)
            else:
                print("  claude  skip (Claude Code CLI not found)")
            if str(target.parent) not in os.environ.get("PATH", "").split(os.pathsep):
                print(f"add {target.parent} to PATH before running 'harbor'")
            if not failed:
                print("ready: harbor claude | harbor codex")
            return 1 if failed else 0

        providers = (args.provider,) if args.provider else PROVIDERS
        failed = False
        for provider in providers:
            try:
                if provider == "claude":
                    sync_claude()
                    print("  claude  ok (live plugin source validated)")
                else:
                    sync_codex()
                    print("  codex   ok (generated and linked)")
            except (OSError, RuntimeError) as exc:
                failed = True
                print(f"  {provider:<7} FAIL ({exc})", file=sys.stderr)
        return 1 if failed else 0
    except (OSError, RuntimeError) as exc:
        print(f"harbor: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

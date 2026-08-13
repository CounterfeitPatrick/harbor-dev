#!/usr/bin/env python3
"""Two-layer harness canary: command → coordinator → worker → result.json.

One throwaway plugin source (embedded below, NOT part of harbor's real
commands/ or agents/) is executed by both harnesses and compared solely on
the result.json it produces — natural-language replies are ignored. A single
run verifies, end to end:

  - the harness discovers the generated skill;
  - arguments pass through the command into the dispatch chain;
  - `harbor-*` agent names resolve to the generated agents (Codex);
  - TWO-LAYER nested dispatch works — the reward-tune topology
    (main → coordinator → worker), which a command-to-leaf test cannot show;
  - workspace-write sandboxing permits the leaf's file write;
  - the result is recovered from the artifact, not from chat text.

Costs real model calls on both CLIs — run via `make harness-smoke` when the
adapter or a harness CLI version changes, never in the deterministic suites.

Exit 0: every requested harness produced a valid result.json. Exit 1: at
least one did not (the verdict JSON on stdout says which layer broke).
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import base, codex  # noqa: E402

COMMAND = """---
description: Harness canary — dispatch the coordinator, then report result.json's status.
argument-hint: "input=<token> out=<absolute path>"
---

# Canary

1. Resolve `input` and `out` from the arguments; both are required.
2. Dispatch ONE subagent: Agent(canary-coordinator, prompt={input: "<input>", out: "<out>"}).
3. When it returns, read `<out>` and reply with one line: `CANARY <status>`
   using the file's `status` field. Never write `<out>` yourself.
"""

COORDINATOR = """---
name: canary-coordinator
description: Canary middle layer — dispatches canary-worker, then verifies and finalizes result.json.
tools: [Read, Write, Agent]
---

# Canary Coordinator

You receive an `input` token and an `out` path.

1. Dispatch ONE subagent: Agent(canary-worker, prompt={input: "<input>", out: "<out>"}).
2. When it returns, read `<out>`. It must be JSON whose `input` equals your
   token and whose `worker_ran` is true.
3. Rewrite `<out>` keeping its fields and adding `"coordinator_ran": true`
   plus `"status": "ok"` if step 2 held, else `"status": "mismatch"`.

Never write the worker's initial file yourself — step 2 must observe the
worker's own write. Final message: the status, one word.
"""

WORKER = """---
name: canary-worker
description: Canary leaf — writes the initial result.json.
tools: [Write]
---

# Canary Worker

You receive an `input` token and an `out` path. Write `<out>` containing
exactly `{"input": "<input>", "worker_ran": true}` and reply `wrote`.
"""


def write_fixture(root: Path) -> Path:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps(
        {"name": "canary", "version": "0.0.1",
         "description": "harness smoke canary"}))
    (root / "commands").mkdir()
    (root / "commands" / "canary.md").write_text(COMMAND)
    (root / "agents").mkdir()
    (root / "agents" / "canary-coordinator.md").write_text(COORDINATOR)
    (root / "agents" / "canary-worker.md").write_text(WORKER)
    return root


def verify(out: Path, token: str):
    """(ok, detail) judged from the artifact alone."""
    if not out.is_file():
        return False, ("result.json was never written — failed before the "
                       "worker's write (command, coordinator, or worker)")
    try:
        result = json.loads(out.read_text())
    except json.JSONDecodeError as exc:
        return False, f"result.json is not valid JSON: {exc}"
    if not isinstance(result, dict):
        return False, f"result.json must be a JSON object, got {result!r}"
    checks = {"input": result.get("input") == token,
              "worker_ran": result.get("worker_ran") is True,
              "coordinator_ran": result.get("coordinator_ran") is True,
              "status": result.get("status") == "ok"}
    failed = sorted(key for key, ok in checks.items() if not ok)
    return not failed, (f"failed fields: {failed}, got {result}" if failed
                       else "ok")


def run_claude(fixture: Path, proj: Path, token: str, timeout: int):
    out = proj / "result.json"
    prompt = f"/canary:canary input={token} out={out}"
    proc = subprocess.run(
        ["claude", "-p", prompt, "--plugin-dir", str(fixture),
         "--permission-mode", "bypassPermissions"],
        cwd=proj, capture_output=True, text=True, timeout=timeout)
    return proc, out


def run_codex(fixture: Path, proj: Path, token: str, timeout: int):
    codex.emit(base.Source(fixture), proj)
    out = proj / "result.json"
    prompt = (f"Run the $harbor-canary skill with arguments: "
              f"input={token} out={out}")
    proc = subprocess.run(
        ["codex", "exec", "--cd", str(proj), "--sandbox", "workspace-write",
         "--skip-git-repo-check", prompt],
        capture_output=True, text=True, timeout=timeout)
    return proc, out


RUNNERS = {"claude": run_claude, "codex": run_codex}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Two-layer canary across Claude Code and Codex.")
    parser.add_argument("--harness", choices=["both", "claude", "codex"],
                        default="both")
    parser.add_argument("--timeout", type=int, default=480,
                        help="seconds per harness run")
    parser.add_argument("--keep", action="store_true",
                        help="keep the temp directory for inspection")
    args = parser.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="harbor-canary-"))
    fixture = write_fixture(tmp / "source")
    names = ["claude", "codex"] if args.harness == "both" else [args.harness]
    verdict = {}
    for name in names:
        if shutil.which(name) is None:
            verdict[name] = {"ok": False, "detail": f"{name} CLI not on PATH"}
            continue
        proj = tmp / f"proj-{name}"
        proj.mkdir()
        token = f"canary-{uuid.uuid4().hex[:8]}"
        started = time.monotonic()
        try:
            proc, out = RUNNERS[name](fixture, proj, token, args.timeout)
            ok, detail = verify(out, token)
            # A smoke is about confidence: a valid artifact from a CLI that
            # exited non-zero still fails.
            if ok and proc.returncode != 0:
                ok = False
                detail = f"artifact valid but the CLI exited {proc.returncode}"
            verdict[name] = {"ok": ok, "detail": detail,
                             "exit_code": proc.returncode,
                             "elapsed_s": round(time.monotonic() - started, 1)}
            if not ok:
                verdict[name]["stdout_tail"] = proc.stdout[-800:]
                verdict[name]["stderr_tail"] = proc.stderr[-400:]
        except subprocess.TimeoutExpired:
            verdict[name] = {"ok": False,
                             "detail": f"timed out after {args.timeout}s"}
    if args.keep:
        verdict["tmp"] = str(tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(verdict, indent=2))
    return 0 if all(v["ok"] for k, v in verdict.items() if k != "tmp") else 1


if __name__ == "__main__":
    sys.exit(main())

"""Shared adapter machinery: the parsed plugin source, render helpers, and
the unified validation every generated tree must pass.

Each adapter module (one per generated harness) exposes:

  NAME         the harness name (the `--harness` value)
  OUTPUTS      glob patterns for files the adapter owns and validates
  ENTRYPOINTS  (base dir, glob, stem_fn) locating the shipped user
               entrypoints, or None when the harness reads the source
               commands/ directly
  emit(src, out)     render the harness artifacts under `out`

Claude Code has no adapter: the repository root IS the plugin.
"""

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"

# --------------------------------------------------------------- source model

def parse_frontmatter(text):
    """Tolerant line parser matching how Claude Code reads frontmatter."""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return None, text
    lines = m.group(1).split("\n")
    fm, i = {}, 0
    while i < len(lines):
        km = re.match(r"^([A-Za-z][\w-]*):\s?(.*)$", lines[i])
        if not km:
            i += 1
            continue
        key, val = km.group(1), km.group(2)
        if re.fullmatch(r"[|>][-+]?\d?", val.strip()):
            i += 1
            block = []
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                block.append(lines[i].removeprefix("  "))
                i += 1
            fm[key] = "\n".join(block).strip()
            continue
        fm[key] = val.strip()
        i += 1
    tools = fm.get("tools")
    if isinstance(tools, str) and tools.startswith("[") and tools.endswith("]"):
        fm["tools"] = [t.strip() for t in tools[1:-1].split(",") if t.strip()]
    return fm, text[m.end():]


class Source:
    """The parsed plugin: commands (the only entrypoints) + agents."""

    def __init__(self, root: Path):
        self.root = root
        self.commands = [self._load(p) for p in sorted((root / "commands").glob("*.md"))]
        self.agents = [self._load(p) for p in sorted((root / "agents").glob("*.md"))]
        overlap = {c["stem"] for c in self.commands} & {a["stem"] for a in self.agents}
        if overlap:
            raise SystemExit(f"command/agent name collision: {sorted(overlap)}")

    def _load(self, path: Path):
        fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm is None:
            raise SystemExit(f"{path}: missing frontmatter")
        # Generated artifacts are local files; the plugin root is this repo.
        body = body.replace(PLUGIN_ROOT_TOKEN, str(self.root)).strip() + "\n"
        return {
            "stem": path.stem,
            "description": str(fm.get("description", "")).strip(),
            "argument_hint": str(fm.get("argument-hint", "")).strip(),
            "disable_model_invocation": (
                str(fm.get("disable-model-invocation", "false")).lower()
                == "true"),
            # None ≠ []: an absent `tools` field means Claude's full default
            # toolset, while an explicit list (even empty) narrows it.
            "tools": list(fm["tools"] or []) if "tools" in fm else None,
            "body": body,
        }


# ------------------------------------------------------------- render helpers

def yaml_str(value: str) -> str:
    """A safe single-line YAML scalar (JSON strings are valid YAML)."""
    return json.dumps(value, ensure_ascii=False)


def toml_str(value: str) -> str:
    """A TOML multiline basic string."""
    escaped = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""\n{escaped}"""'


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def reset_owned(path: Path, pattern: str):
    """Remove only this adapter's prior outputs from a shared native root."""
    path.mkdir(parents=True, exist_ok=True)
    for target in path.glob(pattern):
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


# --------------------------------------------------------- vocabulary rewrite

# Claude-only vocabulary mapped to Codex. Keep it centralized so the adapter
# and generated-output tests cannot drift.
#
# TOOL_PROSE rewrites the grammatically-safe "the <Tool> tool" prose form —
# the article matches case-insensitively but the tool name must be exact
# CamelCase, so English like "the bash tool" (meaning the shell) survives.
# Bare backticked mentions (e.g. "read with `Read`") are left alone: no
# mechanical replacement survives their grammar. VOCAB literal pairs then
# catch the remaining Claude-only spellings; insertion order matters, so a
# longer spelling precedes any spelling it contains.
TOOL_PROSE = {  # Codex has no formal tool-name vocabulary.
    "Read": "the file reading", "Edit": "the file editing",
    "Write": "the file writing", "Bash": "the shell execution",
    "Grep": "the content search", "Glob": "the file matching",
    "Agent": "the subagent dispatch", "Task": "the subagent dispatch",
}
_TOOL_PROSE_RE = re.compile(
    r"(?i:\bthe)\s+`?("
    + "|".join(sorted(TOOL_PROSE))
    + r")`?\s+tool\b")

VOCAB = {
    "an AskUserQuestion": "a request_user_input prompt",
    "AskUserQuestion": "request_user_input",
    "Agent tool": "subagent tool",
    "Bash tool": "shell execution",
    # The tune loop is resume-safe by files; these mappings preserve that
    # behavior without depending on Claude's session-tool names.
    "`SendMessage`": "a follow-up message to the same subagent session",
    "TaskStop each in_flight agent_id":
        "cancel each in_flight agent_id's subagent",
    # Codex has native subagents, so no speculative inline fallback is needed.
    # Named calls keep their shape; prefix_agent_dispatch fixes their names.
    'Agent(subagent_type="general-purpose")': "fresh subagent session",
    "a `general-purpose` sub-agent": "a fresh subagent session",
    "multiple Agent calls": "multiple subagent dispatches",
}


def rewrite_vocabulary(text: str) -> str:
    """Rewrite Claude-only vocabulary into Codex-native phrasing."""
    text = _TOOL_PROSE_RE.sub(lambda m: TOOL_PROSE[m.group(1)], text)
    for spelling, native in VOCAB.items():
        text = text.replace(spelling, native)
    return text


def prefix_agent_dispatch(text: str, agents) -> str:
    """Point named dispatch calls at the generated `harbor-` agent names.

    `Agent(reward-tuning-agent, ...)` must reference the name the target
    harness actually registers (`harbor-reward-tuning-agent`). Only exact,
    known agent stems are rewritten, so the ad-hoc executor call (handled by
    VOCAB) and any non-dispatch parenthetical are untouched.
    """
    if not agents:
        return text
    pattern = re.compile(
        r"Agent\((" + "|".join(map(re.escape, sorted(agents)))
        + r")(?=\s*[,)])")
    return pattern.sub(lambda m: f"Agent(harbor-{m.group(1)}", text)


# --------------------------------------------------------- unified validation

def validate(src: Source, out: Path, adapter) -> list:
    """Every shipped entrypoint maps to a command, never an agent."""
    errors = []
    skills = {c["stem"] for c in src.commands}
    agent_defs = {a["stem"] for a in src.agents}
    if adapter.ENTRYPOINTS is not None:
        base_dir, pattern, stem_of = adapter.ENTRYPOINTS
        for p in sorted((out / base_dir).glob(pattern)):
            stem = re.sub(r"^harbor-", "", stem_of(p))
            if stem in agent_defs:
                errors.append(
                    f"{adapter.NAME}: agent '{stem}' shipped as an entrypoint")
            elif stem not in skills:
                errors.append(
                    f"{adapter.NAME}: entrypoint '{stem}' maps to no skill")
    for pattern in adapter.OUTPUTS:
        for p in sorted(out.glob(pattern)):
            if p.is_file() and PLUGIN_ROOT_TOKEN in p.read_text(
                    encoding="utf-8", errors="replace"):
                errors.append(
                    f"{adapter.NAME}: unresolved plugin-root token in {p}")
    return errors

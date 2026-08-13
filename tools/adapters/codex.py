"""Codex CLI adapter.

Commands become project skills under `.agents/skills/`; agents become TOML
definitions under `.codex/agents/`. Both are native project-scoped Codex
surfaces, generated locally and gitignored. Harbor claims only the
`harbor-*` namespace in those trees — foreign project skills and agents are
preserved and never validated.
"""

import re
from pathlib import Path

from .base import (prefix_agent_dispatch, reset_owned, rewrite_vocabulary,
                   toml_str, write, yaml_str)

NAME = "codex"
OUTPUTS = (".agents/skills/harbor-*/SKILL.md",
           ".agents/skills/harbor-*/agents/openai.yaml",
           ".codex/agents/harbor-*.toml")
ENTRYPOINTS = (".agents/skills", "harbor-*/SKILL.md", lambda p: p.parent.name)

READ_ONLY_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch"}


def native_text(text: str, src) -> str:
    """Translate only harness vocabulary; preserve workflow semantics."""
    commands = {item["stem"] for item in src.commands}
    agents = {item["stem"] for item in src.agents}

    def skill_call(match):
        name = match.group(1)
        if name in commands:
            return f"$harbor-{name}"
        if name in agents:
            return f"custom agent `harbor-{name}`"
        return match.group(0)

    text = re.sub(r"Skill\(['\"]([a-z][a-z-]*)['\"]\)", skill_call, text)
    text = re.sub(r"/harbor:([a-z][a-z-]*)", r"$harbor-\1", text)
    text = prefix_agent_dispatch(text, agents)
    return rewrite_vocabulary(text)


def emit(src, out: Path):
    skills = out / ".agents" / "skills"
    agents = out / ".codex" / "agents"
    reset_owned(skills, "harbor-*")
    reset_owned(agents, "harbor-*.toml")
    for cmd in src.commands:
        name = f"harbor-{cmd['stem']}"
        fm = [f"name: {name}",
              f"description: {yaml_str(native_text(cmd['description'], src))}"]
        if cmd["argument_hint"]:
            # Codex skill extensions belong under `metadata`.
            fm.append("metadata:")
            fm.append(f"  argument-hint: {yaml_str(cmd['argument_hint'])}")
        preamble = "---\n" + "\n".join(fm) + "\n---\n\n"
        write(skills / name / "SKILL.md",
              preamble + native_text(cmd["body"], src))
        if cmd["disable_model_invocation"]:
            write(skills / name / "agents" / "openai.yaml",
                  "policy:\n  allow_implicit_invocation: false\n")
    for agent in src.agents:
        # An absent tools field inherits Claude's full default toolset. Only
        # an explicit read-only list may narrow the Codex sandbox.
        sandbox = ("read-only" if agent["tools"] is not None
                   and set(agent["tools"]) <= READ_ONLY_TOOLS
                   else "workspace-write")
        write(agents / f"harbor-{agent['stem']}.toml", "\n".join([
            f'name = "harbor-{agent["stem"]}"',
            f"description = {toml_str(native_text(agent['description'], src))}",
            f'sandbox_mode = "{sandbox}"',
            f"developer_instructions = {toml_str(native_text(agent['body'], src))}",
        ]) + "\n")

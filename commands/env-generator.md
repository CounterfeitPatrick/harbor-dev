---
description: Generate an isolated Python environment for a GPU repo using uv on the host (creates a `.venv/`). Use when the user types /harbor:env-generator [path], or asks "set up env for X", "make a venv".
argument-hint: "[path]"
---

# /harbor:env-generator — Environment Generator (uv only)

The user has invoked `/harbor:env-generator` with an optional `[path]` argument. Resolve it and dispatch the env-generator agent.

## Dispatch table

| User input | Route to |
|---|---|
| `/harbor:env-generator` | dispatch env-generator agent with `repo_path=$(pwd)` |
| `/harbor:env-generator <path>` | dispatch with `repo_path=<absolute_path>` |

---

## Action: dispatch

1. Resolve `repo_path`:
   - If an argument is present, treat it as a path (resolve to absolute via `realpath` / `Path.resolve()`).
   - Otherwise use `$(pwd)`.
   - If the resolved path is missing or not a directory, print the error and stop.

2. Verify the repo:
   ```bash
   ls "<repo_path>/.git" >/dev/null 2>&1 && echo "is git repo" || echo "warning: not a git repo"
   ls "<repo_path>"/{pyproject.toml,setup.py,requirements.txt,uv.lock} 2>/dev/null
   ```
   If none of these exist, ask the user to confirm `<repo_path>` is the right repo (Python project missing).

3. Dispatch the env-generator agent with the resolved inputs:
   ```
   Skill('env-generator')
     repo_path = <absolute>
     force?    = false
   ```

4. **Print the agent's structured JSON output verbatim** (its `classification`, `smoke`, etc.), then route based on `classification` per the agent's dispatch table:

   | classification | next |
   |---|---|
   | `benchmark` | dispatch `benchmark-generator` |
   | `plain` | stop |

## Constraints

- **Pass the resolved absolute path** to the agent — never relative.
- **Do not call `benchmark-generator` yourself unless the agent's classification justifies it.** The agent owns the decision.
- The agent produces these artifacts in `<repo>/`:
  - `<repo>/.venv/` — the actual venv (created by `uv venv` + `uv pip install`).
  - `<repo>/harbor/{setup_uv.sh, install_plan.json, install.md, history.md}` — re-runnable setup script and receipts.

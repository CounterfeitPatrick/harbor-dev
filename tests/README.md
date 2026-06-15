# harbor plugin tests

Three layers, because the plugin is two kinds of thing — deterministic code
(`scripts/`, `mcp/`, rendered templates) and LLM instruction files
(`commands/`, `agents/`).

| Layer | Dir | Tests | Needs |
|---|---|---|---|
| **1. Contract** | `tests/contract/` | frontmatter valid · in-repo references resolve · CLAUDE.md map ↔ disk · open-source hygiene | nothing (any machine, < 1s) |
| **2. Unit** | `tests/unit/` | each `scripts/*.py` + MCP fn against fixtures · every `*.py.template` compiles | nothing / light deps |
| **3. E2E pipeline** | (via `/harbor:test-pipeline`) | the full create→train→reset chain on one task | GPU box + a benchmark + the Claude runtime |

Layers 1–2 are plain pytest and run in CI on any machine. Layer 3 is agentic +
GPU-gated and runs through the `/harbor:test-pipeline` command (or a headless
`claude -p` driver) on the benchmark host — not part of `pytest`.

## Run (Layers 1–2)

```bash
pip install -r tests/requirements-test.txt
pytest tests/ -q
```

Run just the fast contract layer:

```bash
pytest tests/contract -q
```

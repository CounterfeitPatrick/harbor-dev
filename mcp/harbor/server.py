#!/usr/bin/env python3
"""harbor — read-only MCP server for the benchmark registry.

Single source of truth:
  - data/benchmarks.yaml: verified benchmark sources (maintainer-curated)
  - specs/benchmarks/<name>.json: obs/action layout per benchmark

The registry is **read-only** at runtime. Adding a new verified entry is a
maintainer-only flow: hand-edit the YAML and drop a spec JSON in this plugin
repo, then `git commit` + plugin release. Agents (env-generator /
benchmark-generator) only produce repo-local artifacts; they cannot mutate
this registry. See README.md "How to graduate to verified" for the curation
flow.

Tools (all return JSON, never multi-page text; the only long-text field allowed
is `formatted_table`, used by the /harbor:help registry listing).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SPECS_DIR = ROOT / "specs"
BENCH_YAML = DATA_DIR / "benchmarks.yaml"

mcp = FastMCP("harbor-registry")


# ---------- yaml shim (PyYAML if present, otherwise minimal parser) ----------

try:
    import yaml as _yaml

    def yaml_load(text: str) -> dict:
        return _yaml.safe_load(text) or {}
except ImportError:  # fallback for environments without PyYAML
    def yaml_load(text: str) -> dict:
        result: dict = {"schema_version": 1}
        items: list[dict] = []
        list_key: str | None = None
        current: dict | None = None
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent == 0 and stripped.endswith(":"):
                key = stripped[:-1].strip()
                if key == "benchmarks":
                    list_key = key
                    items = []
                    result[key] = items
                continue
            if indent == 0 and ":" in stripped:
                k, _, v = stripped.partition(":")
                result[k.strip()] = _coerce(v.strip())
                continue
            if list_key and stripped.startswith("- "):
                current = {}
                items.append(current)
                stripped = stripped[2:]
                if ":" in stripped:
                    k, _, v = stripped.partition(":")
                    current[k.strip()] = _coerce(v.strip())
            elif current is not None and ":" in stripped:
                k, _, v = stripped.partition(":")
                current[k.strip()] = _coerce(v.strip())
        return result

    def _coerce(v: str) -> Any:
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            return v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [_coerce(x.strip()) for x in inner.split(",")]
        if v in ("true", "True"):
            return True
        if v in ("false", "False"):
            return False
        return v


# ---------- registry I/O (read-only) ----------

def _load(path: Path, list_key: str) -> tuple[dict, list[dict]]:
    if not path.exists():
        return {"schema_version": 1, list_key: []}, []
    data = yaml_load(path.read_text())
    items = data.get(list_key) or []
    return data, items


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "(empty)"
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [fmt.format(*headers), fmt.format(*("-" * w for w in widths))]
    for row in rows:
        out.append(fmt.format(*[str(c) for c in row]))
    return "\n".join(out)


# ---------- fuzzy match helpers ----------

def _url_basename(s: str) -> str:
    """Extract repo basename from a github URL.

    'https://github.com/foo/bar.git'  → 'bar'
    'git@github.com:foo/bar.git'      → 'bar'
    'github.com/foo/bar'              → 'bar'
    'bar' (no slashes)                → 'bar'
    """
    s = s.strip().rstrip("/")
    last = re.split(r"[/:]", s)[-1]
    if last.endswith(".git"):
        last = last[:-4]
    return last


def _normalize(s: str) -> str:
    """Aggressive normalization for fuzzy match.

    - lowercase
    - strip trailing digits ('ManiSkill3' → 'maniskill')
    - drop non-alphanumeric ('mani-skill' → 'maniskill')
    """
    s = s.lower()
    s = re.sub(r"\d+$", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _match_entry(entry: dict, query: str) -> str | None:
    """Try to match a registry entry against a query string.

    Returns one of: 'exact_name' | 'exact_url' | 'fuzzy_basename' | 'fuzzy_normalized' | None.
    Match types are listed in priority order (highest first).
    """
    name = entry.get("name", "") or ""
    github = entry.get("github", "") or ""

    if name and name == query:
        return "exact_name"
    if github and github == query:
        return "exact_url"

    basename = _url_basename(query)

    if basename and name and basename.lower() == name.lower():
        return "fuzzy_basename"

    nq = _normalize(query)
    nb = _normalize(basename) if basename else ""
    nn = _normalize(name)
    if nn and (nq == nn or nb == nn):
        return "fuzzy_normalized"

    return None


# ---------- benchmark tools (read-only) ----------

@mcp.tool()
def list_benchmarks(status: str | None = "verified", category: str | None = None) -> dict:
    """List benchmarks. Defaults to status=verified. Pass status=null to list all."""
    _, items = _load(BENCH_YAML, "benchmarks")
    filtered = [
        b for b in items
        if (status is None or b.get("status") == status)
        and (category is None or b.get("category") == category)
    ]
    headers = ["name", "user_id", "image", "category", "status", "verified_at", "github"]
    rows = [[b.get(h, "") for h in headers] for b in filtered]
    return {
        "count": len(filtered),
        "benchmarks": filtered,
        "formatted_table": _format_table(headers, rows),
    }


@mcp.tool()
def lookup_benchmark(name_or_url: str) -> dict:
    """Look up one benchmark by name OR github URL (fork-tolerant, case-insensitive).

    Match priority (returns first hit):
      1. exact name           — `name_or_url == entry.name`
      2. exact github URL     — `name_or_url == entry.github`
      3. fuzzy URL basename   — `<repo>` from URL ≈ entry.name (case-insensitive)
      4. fuzzy normalized     — lowercased + trailing-digits-stripped + alnum-only

    Use case for fuzzy: a fork like `https://github.com/zhuoqun-chen/ManiSkill3`
    matches verified `maniskill` via 'ManiSkill3' → 'maniskill' normalization.

    Returns `{found, benchmark?, match_type?}` where `match_type` is one of
    `exact_name | exact_url | fuzzy_basename | fuzzy_normalized`.
    """
    _, items = _load(BENCH_YAML, "benchmarks")
    for b in items:
        mt = _match_entry(b, name_or_url)
        if mt:
            return {"found": True, "benchmark": b, "match_type": mt}
    return {"found": False}


@mcp.tool()
def get_benchmark_spec(name: str) -> dict:
    """Read benchmark obs/action spec. Returns {found, spec?}."""
    path = SPECS_DIR / "benchmarks" / f"{name}.json"
    if not path.exists():
        return {"found": False}
    return {"found": True, "spec": json.loads(path.read_text())}


@mcp.tool()
def list_tasks(benchmark_name: str | None = None) -> dict:
    """List per-task metadata across registry benchmark specs.

    A task entry is read from `specs/benchmarks/<bench>.json` field `tasks[]`,
    populated by `benchmark-generator` for RL benchmarks (each entry typically
    has `id`, `max_episode_steps`, `success_metric`, `reward_implemented`,
    `reward_metric`). IL benchmarks usually have an empty `tasks[]` because
    their notion of "task" is a single obs/action contract (covered by
    `get_benchmark_spec`), not an enumerated list.

    Args:
        benchmark_name: if given, list tasks from only that benchmark's spec.
            If None, aggregate across every spec under `specs/benchmarks/`.

    Returns: `{count, tasks: [...], formatted_table}`. Each task gets an
    extra `benchmark` field so the table can be sorted/filtered downstream.
    """
    bench_dir = SPECS_DIR / "benchmarks"
    if benchmark_name:
        candidates = [bench_dir / f"{benchmark_name}.json"]
    else:
        candidates = sorted(p for p in bench_dir.glob("*.json") if p.name != "_schema.json")

    tasks: list[dict] = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            spec = json.loads(path.read_text())
        except Exception:
            continue
        bench = spec.get("benchmark_name") or path.stem
        for t in spec.get("tasks") or []:
            entry = {"benchmark": bench}
            entry.update(t if isinstance(t, dict) else {"id": str(t)})
            tasks.append(entry)

    headers = ["benchmark", "id", "max_episode_steps", "success_metric",
               "reward_implemented", "reward_metric"]
    rows = [[t.get(h, "") for h in headers] for t in tasks]
    return {
        "count": len(tasks),
        "tasks": tasks,
        "formatted_table": _format_table(headers, rows),
    }


if __name__ == "__main__":
    mcp.run()

---
description: List or inspect tasks within a Harbor benchmark. Use when the user types /harbor:task-list or asks "list tasks", "show task spec", "what tasks does this benchmark have", "show me task <id>". Defaults to the cwd-local `harbor/benchmark-generator/benchmark-spec.json` (rich, populated by benchmark-generator for RL benchmarks); falls back to the registry-side spec when given a benchmark name.
argument-hint: [list] | list <benchmark-name> | list all | <task-id>
---

# /harbor:task-list — Task Browser

The user has invoked `/harbor:task-list` with optional sub-command arguments. **Parse the arguments and route to one of the actions below.** Do not execute multiple actions in one invocation.

## Dispatch table

| User input | Route to |
|---|---|
| `/harbor:task-list` (no args) | **list local** |
| `/harbor:task-list list` | **list local** |
| `/harbor:task-list list <benchmark-name>` | **list registry** (one benchmark) |
| `/harbor:task-list list all` | **list registry** (all benchmarks) |
| `/harbor:task-list <task-id>` (arg contains `/`, e.g. `cartpole/swingup`) | **show one** |

Anything else: print the dispatch table above and stop.

---

## Action: list local

Tasks captured by `benchmark-generator` into the **current repo's** `harbor/benchmark-generator/benchmark-spec.json`. This is the rich path: each task carries `id`, `max_episode_steps`, `success_metric`, `reward_implemented`, `reward_metric`, plus any benchmark-specific fields.

1. Locate the spec:
   ```bash
   ls "$(pwd)/harbor/benchmark-generator/benchmark-spec.json"
   ```
   If missing, print:
   > `harbor/benchmark-generator/benchmark-spec.json` not found in `<cwd>`. Either `cd` into a benchmark repo (one that has been processed by `benchmark-generator`) and retry, or pass a registered benchmark name: `/harbor:task-list list <name>` (see MCP `list_benchmarks` for valid names).

2. Tabulate via inline Bash:
   ```bash
   python3 - <<'PY'
   import json, sys
   from pathlib import Path
   spec = json.loads(Path("harbor/benchmark-generator/benchmark-spec.json").read_text())
   tasks = spec.get("tasks") or []
   bench = spec.get("benchmark_name") or "(unknown)"
   if not tasks:
       print(f"benchmark '{bench}' has no enumerated tasks (likely an IL benchmark — its task is the obs/action contract; use get_benchmark_spec).")
       sys.exit(0)
   headers = ["id", "max_episode_steps", "success_metric", "reward_implemented", "reward_metric"]
   widths = [len(h) for h in headers]
   rows = [[str(t.get(h, "")) for h in headers] for t in tasks]
   for row in rows:
       for i, c in enumerate(row):
           widths[i] = max(widths[i], len(c))
   fmt = "  ".join(f"{{:<{w}}}" for w in widths)
   print(f"benchmark: {bench}  ({len(tasks)} tasks)")
   print(fmt.format(*headers))
   print(fmt.format(*("-"*w for w in widths)))
   for r in rows:
       print(fmt.format(*r))
   PY
   ```

3. Print the script's stdout verbatim. Do not paraphrase.

---

## Action: list registry

Aggregates `tasks[]` from registry-side specs at `mcp/harbor/specs/benchmarks/<name>.json`.

1. Call `mcp__plugin_harbor_harbor__list_tasks`:
   - `list <benchmark-name>`: pass `{benchmark_name: "<name>"}`.
   - `list all`: no args (aggregates across all specs).

2. Print the returned `formatted_table` field **verbatim**. If `count == 0`, also print this hint:
   > Registry specs currently capture obs/action layout but not enumerated `tasks[]` for most verified benchmarks (IL benchmarks have a single obs/action contract; RL benchmarks populate `tasks[]` only at scaffold time in the local `harbor/benchmark-generator/benchmark-spec.json`). To see live tasks, `cd` into a benchmark repo and run `/harbor:task-list` with no args.

---

## Action: show one

Show the full task entry for `<task-id>` from the cwd-local benchmark-spec.

1. Verify `harbor/benchmark-generator/benchmark-spec.json` exists in cwd; if not, follow the same fallback as **list local**.

2. Inline:
   ```bash
   python3 - "<task-id>" <<'PY'
   import json, sys
   from pathlib import Path
   tid = sys.argv[1]
   spec = json.loads(Path("harbor/benchmark-generator/benchmark-spec.json").read_text())
   for t in spec.get("tasks") or []:
       if t.get("id") == tid:
           print(json.dumps(t, indent=2))
           sys.exit(0)
   print(f"task '{tid}' not found in benchmark '{spec.get('benchmark_name')}'. "
         f"Run /harbor:task-list to see the full list.", file=sys.stderr)
   sys.exit(2)
   PY
   ```

3. Print stdout verbatim. If exit code is non-zero, surface stderr and stop.

---

## Constraints

- Local mode is the default because it carries the rich per-task metadata; the registry mode is informational and currently sparse.
- Do NOT modify `harbor/benchmark-generator/benchmark-spec.json` — this command is read-only.
- Do NOT mix the two sources in a single output. If the user wants one specific benchmark, prefer the registry path so it works without `cd`-ing.

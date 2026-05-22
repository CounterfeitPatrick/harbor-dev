---
description: Browse, contribute to, or reproduce from the benchmark registry. Use when the user types /harbor:benchmark or asks "list benchmarks", "show verified benchmarks", "submit a benchmark", "verify benchmark <name>", "reproduce <name>", or passes a GitHub URL to reproduce a benchmark from source. Dispatches list / submit / verify / reproduce sub-actions; calls MCP tools, shared CLI scripts, or env-generator + benchmark-generator depending on the verb.
argument-hint: [list verified|unverified|all] | [submit] | [verify <name>] | <name> | <url>
---

# /harbor:benchmark — Benchmark Registry

## TBD — uv-only registry artifact convention pending

The plugin is migrating off docker images. The registry currently stores a docker image tag (`yufengjin/<name>:latest`); going forward we plan to store the source URL + commit hash and let users reproduce via `/harbor:env-generator` + `/harbor:benchmark` from the source repo. The submit/verify flows below still reference image tags — treat those as legacy until the registry schema is updated.

---

The user has invoked `/harbor:benchmark` with optional sub-command arguments. **Parse the arguments and route to one of the actions below.** Do not execute multiple actions in one invocation.

## Dispatch table

| User input | Route to |
|---|---|
| `/harbor:benchmark` (no args) | **list verified** |
| `/harbor:benchmark list` | **list verified** |
| `/harbor:benchmark list verified` | **list verified** |
| `/harbor:benchmark list unverified` | **list unverified** |
| `/harbor:benchmark list all` | **list all** |
| `/harbor:benchmark submit` | **submit** |
| `/harbor:benchmark verify` (no name) | **verify** (prompt for which entry) |
| `/harbor:benchmark verify <name>` | **verify** with that name |
| `/harbor:benchmark <url>` (arg starts with `http://`, `https://`, `git@`, or `github.com/`) | **reproduce** (URL form) |
| `/harbor:benchmark <name>` (arg is a single bare token, not a URL, not a recognized verb) | **reproduce** (name shortcut — resolves to the registered URL via `lookup_benchmark`) |

Anything else: tell the user the six sub-commands and stop.

---

## Action: list

1. Call `mcp__plugin_harbor_harbor__list_benchmarks` with the appropriate `status` argument:
   - `list` / `list verified`: no args (defaults to `status="verified"`).
   - `list unverified`: `{status: "unverified"}`.
   - `list all`: `{status: null}`.
2. Print the returned `formatted_table` field **verbatim**. Do not paraphrase.

For a single benchmark by name or github URL (fork-tolerant fuzzy match): call `mcp__plugin_harbor_harbor__lookup_benchmark` with `{name_or_url}`.
For obs/action layout of a verified benchmark: call `mcp__plugin_harbor_harbor__get_benchmark_spec` with `{name}`.

---

## Action: submit

Collect the required fields via two `AskUserQuestion` calls (the tool caps at 4 questions per call), then invoke the shared CLI script.

### Questions, call 1 (4 free-text fields)

For each field, present 1–2 example options plus the auto-included "Other" choice (where the user types a custom value). Headers max 12 chars.

1. **Name** (header `Name`) — short canonical name (lowercase, hyphens or letters only). Becomes the registry key.
2. **GitHub user** (header `GitHub user`) — the submitter's GitHub username. Stored as `user_id` so reviewers can ping the author.
3. **GitHub URL** (header `GitHub URL`) — full URL of the benchmark source repo.
4. **Commit** (header `Commit`) — git commit hash for the verified state of the benchmark source.

### Questions, call 2 (category + notes)

5. **Category** (header `Category`, single-select) — three options:
   - `il` — Imitation learning
   - `rl` — Reinforcement learning
   - `mixed` — Both pipelines supported
6. **Notes** (header `Notes`) — short free-text note (e.g. "IsaacGym Python 3.8, sibling mount"). Empty allowed; offer "(none)" as one option.

### After collecting answers

Run via Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/registry/registry_submit.py" \
  --kind benchmark \
  --name "<a1>" \
  --user-id "<a2>" \
  --github "<a3>" \
  --commit "<a4>" \
  --category "<a5>" \
  --notes "<a6>"
```

(Legacy `--image` flag may still exist on `registry_submit.py`; pass `--commit` once the script is updated, or fall back to `--image` with a placeholder until the registry schema migrates.)

Print the script's stdout verbatim — it includes the `git checkout -b ... / git add / git commit / git push / gh pr create` block the user must run themselves. **Do NOT run any git commands yourself.**

---

## Action: verify

If the user did not supply a `<name>`, first call `mcp__plugin_harbor_harbor__list_benchmarks` with `{status: "unverified"}` and use `AskUserQuestion` to let the user pick one of the unverified entries. If there are zero unverified entries, tell the user and stop.

Then run via Bash:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/registry/registry_verify.py" \
  --kind benchmark \
  --name "<name>"
```

Verification fills the verified state from the source repo (commit hash). The script's legacy docker-image inspection step is best-effort; if it fails, re-run with `--no-docker --image-id ... --size ...` or pass the source-only equivalents — see the script's `--help`.

Print the script's stdout verbatim. **Do NOT run `git add`/`git commit` yourself** — print the suggested commands and let the user execute them.

---

## Action: reproduce

Triggered when the argument is either a **URL** (starts with `http://`, `https://`, `git@`, or `github.com/`) or a **bare name** that is not a recognized verb. Runs the full reproduce pipeline by dispatching `env-generator` (which short-circuits on a verified-registry hit) and routes to `benchmark-generator` only when the repo is a fresh, benchmark-classified rebuild.

### Step 0 — Resolve name to URL + confirm with user (name-shortcut form only)

If the argument does NOT start with `http://`, `https://`, `git@`, or `github.com/`, treat it as a registry name:

1. Call `mcp__plugin_harbor_harbor__lookup_benchmark({name_or_url: <arg>})`.
2. If `found=false`, print: "No benchmark named `<arg>` in the registry. Run `/harbor:benchmark list` to see available entries, or pass a full GitHub URL to reproduce a new benchmark from source." Stop. Do not dispatch any subagent.
3. If `found=true`, **confirm with the user via `AskUserQuestion`** before doing anything else. Use a single multi-choice question:
   - Header: `Confirm benchmark` (≤12 chars)
   - Question text must include the matched entry's `name` and `github` so the user can sanity-check this is the entry they meant.
   - Options:
     - `Yes, reproduce` — description: "Clone repo, set up venv via env-generator, run benchmark-generator"
     - `Cancel` — description: "Stop without doing anything"
4. If the user picks `Yes, reproduce`, set `url = response.benchmark.github` and proceed to Step 1.
5. If the user picks `Cancel` or `AskUserQuestion` returns null, print `Cancelled. No changes made.` and stop.

If the argument IS a URL, skip Step 0 entirely.

### Step 1 — Resolve the repo path

1. Derive the repo name: take the URL basename, strip a trailing `.git`. Example: `https://github.com/Lifelong-Robot-Learning/LIBERO.git` → `LIBERO`.
2. If `./<name>/.git/` already exists locally, treat as already-cloned and use the absolute path of `./<name>/` as `repo_path`. Do NOT re-clone.
3. Otherwise run `git clone <url> <name>` from the current working directory.
4. If `git clone` exits non-zero (network, auth, 404, etc.), surface stderr verbatim and stop. Do not dispatch any subagent.

### Step 2 — Dispatch env-generator

Dispatch the `env-generator` subagent with `repo_path=<absolute path from Step 1>`.

`env-generator` runs the full pipeline against this exact repo state and returns one of `{benchmark, plain}`. There is no verified-image short-circuit in uv mode — every reproduction starts from a fresh `<repo>/.venv/`.

### Step 3 — Route on env-generator's output

User intent for this slash command is **benchmark**. Match against env-generator's classification:

| `classification` | Action |
|---|---|
| `benchmark` | Dispatch `benchmark-generator` with `repo_path=<abs>`, `base_classification="benchmark"`, plus `quirks_resolved` and `is_isaacgym` lifted from env-generator's output JSON (so the subagent doesn't re-probe the env layer). Print its returned JSON report. Then suggest `/harbor:benchmark submit` if the user wants to publish the entry. |
| `plain` | Print: "env-generator could not classify this repo as a benchmark. The venv at `<repo>/.venv/` has been generated; see `<repo>/harbor/install.md` and `<repo>/harbor/history.md` for what works." Stop. |

If env-generator returned a non-empty `errors[]`, surface it verbatim before the routing decision and let the user decide whether to retry.

### Constraints

- **Do NOT dispatch `benchmark-generator` on a `plain` classification.** The downstream subagent would fail its own Step 0 prerequisite checks anyway, but the slash command should produce a clean human-readable message before that happens.
- **Do NOT re-clone if `./<name>/.git/` already exists.** Reuse the existing checkout — the user may have local changes.

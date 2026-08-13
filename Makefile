# Harbor management verbs, wshobson/agents-style.
#
# The repo root is the Claude Code source of truth. Codex consumes native
# artifacts rendered from the same commands/ and agents/ Markdown.

.PHONY: generate harness-smoke install validate garden test release-check help

help:
	@echo "make generate         render Codex-native artifacts"
	@echo "make install          install the harbor native-session launcher"
	@echo "make validate         source contracts + generator tests"
	@echo "make harness-smoke    live two-layer canary on Claude Code + Codex (real model calls)"
	@echo "make garden           focused source drift and hygiene checks"
	@echo "make test             the full deterministic suite (contract + unit)"
	@echo "make release-check    all gates + Claude manifest/tag dry-run"

generate:
	python3 tools/generate.py --harness codex

# Live model calls on both CLIs — deliberately NOT part of validate/test.
# Re-run when the adapter or a harness CLI version changes.
harness-smoke:
	python3 tools/harness_smoke.py

install:
	python3 tools/harbor.py install

validate:
	python3 -m pytest tests/contract -q
	python3 -m pytest tests/unit/test_generate.py tests/unit/test_harness_smoke.py -q

# The drift-focused subset already present on main. Keep this list small.
garden:
	python3 -m pytest tests/contract/test_frontmatter.py \
	                  tests/contract/test_references.py \
	                  tests/contract/test_claudemd_map.py \
	                  tests/contract/test_invocation.py -q

test:
	python3 -m pytest tests/contract tests/unit -q

release-check: validate garden test
	git diff --check
	claude plugin validate .
	claude plugin tag --dry-run .

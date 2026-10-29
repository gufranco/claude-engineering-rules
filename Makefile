VENV       := $(CURDIR)/.venv
tool = $(if $(wildcard $(VENV)/bin/$(1)),$(VENV)/bin/$(1),$(1))

PYTHON     := $(call tool,python3)
PYTEST     := $(call tool,pytest)
COVERAGE   := $(call tool,coverage)
RUFF       := $(call tool,ruff)
MYPY       := $(call tool,mypy)

# Must match the paths the CI Lint job passes to ruff. When the two drift,
# a lint failure only ever surfaces after a push.
LINT_PATHS := hooks scripts tools skills .github/scripts tests analyzers

# The modules held to mypy --strict. The rest of the tree does not pass yet, so
# widening this list is a deliberate change that comes with the fixes. CI calls
# `make typecheck` rather than repeating the list, so the two cannot drift.
TYPECHECK_PATHS := hooks/mutation-method-blocker.py \
                   hooks/markdown-link-discipline.py \
                   hooks/frontend-render-gate.py \
                   hooks/coverage-exclusion-guard.py \
                   hooks/_lib/coverage_exclusion.py \
                   hooks/_lib/change_marker.py \
                   hooks/_lib/image_dimensions.py \
                   hooks/_lib/publish_commands.py \
                   hooks/_lib/ui_evidence.py \
                   hooks/_lib/ui_surface.py \
                   $(sort $(wildcard hooks/_lib/mutation_*.py)) \
                   $(sort $(wildcard hooks/_lib/polyglot_mutation_*.py)) \
                   hooks/_lib/guard_runner.py \
                   hooks/_lib/python_mutation_detectors.py \
                   hooks/_lib/dedup_detectors.py \
                   hooks/_lib/idempotency_detectors.py \
                   hooks/_lib/analyzer_runs.py \
                   hooks/_lib/analyzer_parsers.py \
                   hooks/_lib/analyzer_batch.py \
                   hooks/_lib/changed_lines.py \
                   hooks/_lib/source_scope.py \
                   hooks/immutability-analyzers.py \
                   hooks/python-mutation-guard.py \
                   hooks/polyglot-immutability-guard.py \
                   hooks/idempotency-guard.py \
                   hooks/dedup-store-guard.py \
                   hooks/_lib/suppression.py \
                   hooks/_lib/audit_log.py \
                   hooks/_lib/project_workspace.py \
                   hooks/_lib/git_invocation.py \
                   hooks/project-workspace.py \
                   hooks/_lib/aaa_structure.py \
                   hooks/_lib/comment_families.py \
                   hooks/_lib/comment_family_index.py \
                   hooks/_lib/comment_regions.py \
                   hooks/_lib/comment_resolution.py \
                   hooks/_lib/comment_syntax.py \
                   hooks/_lib/edit_resolution.py \
                   hooks/_lib/staged_blobs.py \
                   hooks/_lib/tool_directive.py \
                   hooks/_lib/yaml_shell.py \
                   hooks/test-aaa-markers.py \
                   hooks/comment-blocker.py \
                   hooks/_lib/cli_invocations.py \
                   hooks/_lib/shell_segments.py \
                   hooks/_lib/published_text.py \
                   hooks/_lib/hook_input.py

YAMLLINT   := $(call tool,yamllint)
ZIZMOR     := $(call tool,zizmor)

ACTIONLINT := $(shell command -v actionlint 2>/dev/null)

# Must match the config the CI workflow-lint job passes to yamllint.
YAMLLINT_RULES := {extends: default, rules: {line-length: disable, document-start: disable, truthy: {check-keys: false}}}

# Test selectors. Override on the CLI:
#   make test PYTEST_K="some_keyword"
PYTEST_K   ?=
PYTEST_M   ?=
PYTEST_N   ?= auto

PYTEST_OPTS = $(if $(PYTEST_K),-k '$(PYTEST_K)',) $(if $(PYTEST_M),-m '$(PYTEST_M)',)

.PHONY: help install test test-fast test-cov test-js test-analyzers test-smoke benchmark mutation-scan test-all \
        lint lint-py lint-yaml lint-actions lint-workflows lint-md lint-skills \
        format format-check typecheck validate validate-structure \
        clean clean-pyc clean-cov

help:
	@echo "Targets:"
	@echo "  install      Sync .venv from uv.lock and node_modules from pnpm-lock.yaml"
	@echo "  test         Run pytest (parallel, no coverage gate)"
	@echo "  test-fast    Run pytest serial, no coverage, fail fast"
	@echo "  test-cov     Run pytest with branch coverage, enforce 100%"
	@echo "  test-js      Run the Node script tests, enforce 100% coverage"
	@echo "  test-analyzers  Prove every analyzer catalog rule against the real tools, local only"
	@echo "  test-smoke   Run every hook against its smoke fixtures, as CI does"
	@echo "  benchmark    Hold every hook under 500 ms, as CI does"
	@echo "  mutation-scan  Scan tracked JS and TS files for in-place mutation, as CI does"
	@echo "  test-all     test-cov + test-js + test-smoke + benchmark + mutation-scan + lint + typecheck + validate"
	@echo "  lint         All linters: ruff + actionlint + yamllint + zizmor + lint-skills"
	@echo "  lint-skills  tools/lint-skills.py --strict over every skill"
	@echo "  format       ruff format (writes)"
	@echo "  format-check ruff format --check (read-only)"
	@echo "  typecheck    mypy --strict over TYPECHECK_PATHS"
	@echo "  validate     validate-structure plus every .github/scripts/validate-* check"
	@echo "  validate-structure  Parse tracked JSON and rules/index.yml, check index paths and code fences"
	@echo "  clean        Remove caches, coverage data, build artifacts"

install:
	uv sync --locked
	corepack pnpm install --frozen-lockfile --ignore-scripts

test:
	$(PYTEST) -n $(PYTEST_N) --no-cov $(PYTEST_OPTS)

test-fast:
	$(PYTEST) --no-cov -x $(PYTEST_OPTS)

test-cov:
	find . -maxdepth 1 -type f \( -name '.coverage' -o -name '.coverage.*' \) -delete
	$(PYTEST) -n $(PYTEST_N) $(PYTEST_OPTS)
	if find . -maxdepth 1 -name '.coverage.*' -print -quit | grep -q .; then $(COVERAGE) combine; fi
	$(COVERAGE) report

test-analyzers:
	$(PYTEST) --no-cov -p no:randomly analyzers/tests

NODE_COVERAGE := --experimental-test-coverage --test-coverage-include='scripts/*.mjs' \
                 --test-coverage-lines=100 --test-coverage-branches=100 \
                 --test-coverage-functions=100

test-js:
	node --test $(NODE_COVERAGE) 'tests/js/*.test.mjs'

test-smoke:
	$(PYTHON) .github/scripts/hook-smoke.py

benchmark:
	$(PYTHON) .github/scripts/hook-benchmark.py --threshold 500

MUTATION_SCAN_GLOBS := '*.ts' '*.tsx' '*.js' '*.jsx' '*.mjs' '*.cjs' '*.mts' '*.cts'

mutation-scan:
	git ls-files -- $(MUTATION_SCAN_GLOBS) ':!:tests/corpus/' \
		| MUTATION_METHOD_BATCH_MODE=1 $(PYTHON) hooks/mutation-method-blocker.py

test-all: test-cov test-js test-smoke benchmark mutation-scan lint typecheck validate

lint: lint-py lint-yaml lint-actions lint-workflows lint-md lint-skills

lint-skills:
	$(PYTHON) tools/lint-skills.py --strict

lint-md:
	pnpm exec markdownlint-cli2 "rules/*.md" "rules/lang/*.md" "standards/*.md" \
	  "skills/*/SKILL.md" "checklists/*.md" "CLAUDE.md" "README*.md" \
	  "CONTRIBUTING.md" "SECURITY.md" "CODE_OF_CONDUCT.md"

validate-structure:
	$(PYTHON) -c "import json, subprocess; files = subprocess.run(['git', 'ls-files', '*.json'], capture_output=True, text=True, check=True).stdout.split(); [json.load(open(f)) for f in files]; print(f'{len(files)} JSON files parse')"
	$(PYTHON) -c "import os, sys, yaml; idx = yaml.safe_load(open('rules/index.yml')); paths = [e.get('path', f'rules/{n}.md') for s in ('always_loaded', 'on_demand') for n, e in (idx.get(s) or {}).items()]; missing = [p for p in paths if not os.path.exists(p)]; [print(f'ERROR: {p} referenced in index.yml does not exist') for p in missing]; print(f'{len(paths)} index.yml paths checked'); sys.exit(1 if missing else 0)"
	@errors=0; \
	for f in rules/*.md skills/*/SKILL.md checklists/*.md; do \
	  count=$$(grep -c '^[[:space:]]*```' "$$f" || true); \
	  if [ $$(( $${count:-0} % 2 )) -ne 0 ]; then \
	    echo "ERROR: $$f has unclosed code block ($$count triple-backtick lines)"; \
	    errors=$$((errors + 1)); \
	  fi; \
	done; \
	if [ "$$errors" -gt 0 ]; then echo "$$errors file(s) with markdown issues"; exit 1; fi; \
	echo "All markdown files valid"

validate: validate-structure
	@fail=0; \
	for script in validate-counts validate-markdown-links validate-skills \
	              validate-agents validate-settings validate-patterns \
	              validate-cross-refs validate-registry-drift \
	              validate-normative-keywords validate-checklist-counts \
	              validate-instruction-budget validate-public-content; do \
	  printf '%-34s ' "$$script"; \
	  if python3 .github/scripts/$$script.py >/tmp/validate-$$script.log 2>&1; then \
	    echo PASS; \
	  else \
	    echo FAIL; cat /tmp/validate-$$script.log; fail=1; \
	  fi; \
	done; \
	exit $$fail


lint-py:
	$(RUFF) check $(LINT_PATHS)

lint-yaml:
	$(YAMLLINT) -d "$(YAMLLINT_RULES)" .github/

lint-workflows:
	$(ZIZMOR) $(if $(GH_TOKEN),,--offline) --persona=regular --min-severity=low .github/workflows/

lint-actions:
ifndef ACTIONLINT
	@echo "actionlint not installed; skipping"
else
	@if [ -d .github/workflows ]; then \
		$(ACTIONLINT); \
	else \
		echo "no .github/workflows; skipping"; \
	fi
endif

format:
	$(RUFF) format $(LINT_PATHS)
	$(RUFF) check --fix $(LINT_PATHS)

format-check:
	$(RUFF) format --check $(LINT_PATHS)
	$(RUFF) check $(LINT_PATHS)

typecheck:
	$(MYPY) --strict $(TYPECHECK_PATHS)

clean: clean-pyc clean-cov
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov coverage.xml

clean-pyc:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

clean-cov:
	find . -maxdepth 1 -type f \( -name '.coverage' -o -name '.coverage.*' \) -delete
	rm -f coverage.xml

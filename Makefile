# Top-level Makefile.
#
# Python tooling, including yamllint and zizmor, resolves from the in-repo
# .venv when it exists and from PATH otherwise. bats, shellcheck, and
# actionlint are system packages and their targets skip when absent.
#
# The tool versions come from requirements-dev.txt, which CI installs from too.

# Prefer the in-repo .venv when it exists, otherwise fall back to whatever is
# on PATH. CI installs the toolchain with plain pip and still calls these
# targets, so the two must agree without a venv present.
VENV       := $(CURDIR)/.venv
tool = $(if $(wildcard $(VENV)/bin/$(1)),$(VENV)/bin/$(1),$(1))

PYTHON     := $(call tool,python3)
PYTEST     := $(call tool,pytest)
COVERAGE   := $(call tool,coverage)
RUFF       := $(call tool,ruff)
MYPY       := $(call tool,mypy)

# Must match the paths the CI Lint job passes to ruff. When the two drift,
# a lint failure only ever surfaces after a push.
LINT_PATHS := hooks scripts .github/scripts tests

# The modules held to mypy --strict. The rest of the tree does not pass yet, so
# widening this list is a deliberate change that comes with the fixes. CI calls
# `make typecheck` rather than repeating the list, so the two cannot drift.
TYPECHECK_PATHS := hooks/mutation-method-blocker.py \
                   hooks/_lib/mutation_detectors_core.py \
                   hooks/_lib/mutation_detectors_methods.py \
                   hooks/_lib/mutation_detectors_assignments.py \
                   hooks/_lib/suppression.py \
                   hooks/_lib/audit_log.py

# yamllint and zizmor ship in requirements-dev.txt, so they resolve through
# the venv like the rest of the python toolchain. bats, shellcheck, and
# actionlint are system packages and stay optional.
YAMLLINT   := $(call tool,yamllint)
ZIZMOR     := $(call tool,zizmor)

BATS       := $(shell command -v bats 2>/dev/null)
SHELLCHECK := $(shell command -v shellcheck 2>/dev/null)
ACTIONLINT := $(shell command -v actionlint 2>/dev/null)

# Must match the config the CI workflow-lint job passes to yamllint.
YAMLLINT_RULES := {extends: default, rules: {line-length: disable, document-start: disable, truthy: {check-keys: false}}}

# Test selectors. Override on the CLI:
#   make test PYTEST_K="some_keyword"
PYTEST_K   ?=
PYTEST_M   ?=
PYTEST_N   ?= auto

PYTEST_OPTS = $(if $(PYTEST_K),-k '$(PYTEST_K)',) $(if $(PYTEST_M),-m '$(PYTEST_M)',)

.PHONY: help install test test-fast test-cov test-bats test-all \
        lint lint-py lint-sh lint-yaml lint-actions lint-workflows \
        format format-check typecheck \
        clean clean-pyc clean-cov

help:
	@echo "Targets:"
	@echo "  install      Install python deps into .venv from requirements-dev.txt"
	@echo "  test         Run pytest (parallel, no coverage gate)"
	@echo "  test-fast    Run pytest serial, no coverage, fail fast"
	@echo "  test-cov     Run pytest with branch coverage, enforce 95%"
	@echo "  test-bats    Run bats-core suites for shell hooks"
	@echo "  test-all     test-cov + test-bats + lint + typecheck"
	@echo "  lint         All linters: ruff + shellcheck + actionlint + yamllint + zizmor"
	@echo "  format       ruff format (writes)"
	@echo "  format-check ruff format --check (read-only)"
	@echo "  typecheck    mypy --strict over TYPECHECK_PATHS"
	@echo "  clean        Remove caches, coverage data, build artifacts"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTEST) -n $(PYTEST_N) --no-cov $(PYTEST_OPTS)

test-fast:
	$(PYTEST) --no-cov -x $(PYTEST_OPTS)

test-cov:
	rm -f .coverage .coverage.*
	$(PYTEST) -n $(PYTEST_N) $(PYTEST_OPTS)
	$(COVERAGE) combine 2>/dev/null || true
	$(COVERAGE) report

test-bats:
ifndef BATS
	@echo "bats not installed. brew install bats-core"
	@exit 1
else
	@if [ -n "$$(find tests/bats -name '*.bats' 2>/dev/null)" ]; then \
		$(BATS) -r tests/bats; \
	else \
		echo "no .bats files under tests/bats/; skipping"; \
	fi
endif

test-all: test-cov test-bats lint typecheck

lint: lint-py lint-sh lint-yaml lint-actions lint-workflows

lint-py:
	$(RUFF) check $(LINT_PATHS)

lint-sh:
ifndef SHELLCHECK
	@echo "shellcheck not installed; skipping"
else
	@if compgen -G "hooks/*.sh" > /dev/null; then \
		$(SHELLCHECK) hooks/*.sh; \
	else \
		echo "no shell hooks; skipping"; \
	fi
endif

lint-yaml:
	$(YAMLLINT) -d "$(YAMLLINT_RULES)" .github/

lint-workflows:
	$(ZIZMOR) --persona=regular --min-severity=medium .github/workflows/

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
	rm -f .coverage .coverage.* coverage.xml

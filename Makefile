# Top-level Makefile for ~/.claude.
# Spec: specs/2026-05-09-claude-config-state-of-art/plan.md 1.2.3.
#
# Detects the in-repo `.venv/` for python tooling. Falls back to PATH lookups
# for shell tools (bats, shellcheck, actionlint, yamllint).

VENV       := $(CURDIR)/.venv
PYTHON     := $(VENV)/bin/python
PYTEST     := $(VENV)/bin/pytest
COVERAGE   := $(VENV)/bin/coverage
RUFF       := $(VENV)/bin/ruff
MYPY       := $(VENV)/bin/mypy

BATS       := $(shell command -v bats 2>/dev/null)
SHELLCHECK := $(shell command -v shellcheck 2>/dev/null)
ACTIONLINT := $(shell command -v actionlint 2>/dev/null)
YAMLLINT   := $(shell command -v yamllint 2>/dev/null)

# Test selectors. Override on the CLI:
#   make test PYTEST_K="some_keyword"
PYTEST_K   ?=
PYTEST_M   ?=
PYTEST_N   ?= auto

PYTEST_OPTS = $(if $(PYTEST_K),-k '$(PYTEST_K)',) $(if $(PYTEST_M),-m '$(PYTEST_M)',)

.PHONY: help install test test-fast test-cov test-bats test-all \
        lint lint-py lint-sh lint-yaml lint-actions \
        format format-check typecheck \
        clean clean-pyc clean-cov

help:
	@echo "Targets:"
	@echo "  install      Install python deps into .venv"
	@echo "  test         Run pytest (parallel, no coverage gate)"
	@echo "  test-fast    Run pytest serial, no coverage, fail fast"
	@echo "  test-cov     Run pytest with branch coverage, enforce 95%"
	@echo "  test-bats    Run bats-core suites for shell hooks"
	@echo "  test-all     test-cov + test-bats + lint + typecheck"
	@echo "  lint         All linters: ruff + shellcheck + actionlint + yamllint"
	@echo "  format       ruff format (writes)"
	@echo "  format-check ruff format --check (read-only)"
	@echo "  typecheck    mypy --strict"
	@echo "  clean        Remove caches, coverage data, build artifacts"

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install pytest pytest-cov pytest-xdist pytest-randomly \
	                        coverage ruff mypy

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
	@if [ -d tests/bats ]; then \
		$(BATS) -r tests/bats; \
	else \
		echo "tests/bats/ not present; skipping"; \
	fi
endif

test-all: test-cov test-bats lint typecheck

lint: lint-py lint-sh lint-yaml lint-actions

lint-py:
	$(RUFF) check hooks scripts tests

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
ifndef YAMLLINT
	@echo "yamllint not installed; skipping"
else
	$(YAMLLINT) -d "{extends: default, rules: {line-length: disable}}" .
endif

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
	$(RUFF) format hooks scripts tests
	$(RUFF) check --fix hooks scripts tests

format-check:
	$(RUFF) format --check hooks scripts tests
	$(RUFF) check hooks scripts tests

typecheck:
	$(MYPY) --strict scripts hooks

clean: clean-pyc clean-cov
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov coverage.xml

clean-pyc:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

clean-cov:
	rm -f .coverage .coverage.* coverage.xml

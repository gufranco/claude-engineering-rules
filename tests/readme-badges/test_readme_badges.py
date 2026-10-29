from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from faker import Faker

from _helpers.cov_env import apply_coverage_env

TOOL = Path(__file__).resolve().parents[2] / "tools" / "readme-badges.py"

fake = Faker()
Faker.seed(5521)

CI_WORKFLOW = (
    "name: CI\non:\n  push:\n    branches: [main]\n  pull_request:\njobs: {}\n"
)
LINT_WORKFLOW = "name: Lint\non: [push, pull_request]\njobs: {}\n"
RELEASE_WORKFLOW = (
    "name: Release\non:\n  workflow_run:\n    workflows: [CI]\njobs: {}\n"
)
SCORECARD_WORKFLOW = (
    "name: Scorecard\non:\n  push:\n    branches: [main]\njobs:\n  a:\n"
    "    steps:\n      - uses: ossf/scorecard-action@abc\n"
)
MIT = "MIT License\n\nCopyright (c) 2026 Someone\n"
HEADER = (
    '<div align="center">\n\n<strong>Does one thing well.</strong>\n\n'
    "English | [日本語](README.ja.md)\n\n"
)


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("readme_badges", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["readme_badges"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool() -> ModuleType:
    return load_tool()


def make_repo(root: Path, files: dict[str, str], branch: str = "main") -> Path:
    repo = root / "repo"
    repo.mkdir()
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(repo)], check=True, timeout=30
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "add",
            "origin",
            "git@github.com:acme/widget.git",
        ],
        check=True,
        timeout=30,
    )
    return repo


def facts(tool: ModuleType, repo: Path, *, private: bool = False, release: bool = True):
    return tool.collect(repo, private=private, has_release=release)


def test_gating_workflows_become_ci_badges_in_file_order(tool, tmp_path):
    # Arrange
    repo = make_repo(
        tmp_path,
        {
            ".github/workflows/ci.yml": CI_WORKFLOW,
            ".github/workflows/lint.yml": LINT_WORKFLOW,
            ".github/workflows/release.yml": RELEASE_WORKFLOW,
        },
    )

    # Act
    result = facts(tool, repo).workflows

    # Assert
    assert result == (tool.Workflow("ci.yml", "ci"), tool.Workflow("lint.yml", "lint"))


def test_a_public_repo_gets_the_full_block_in_the_standard_order(tool, tmp_path):
    # Arrange
    repo = make_repo(
        tmp_path,
        {
            ".github/workflows/ci.yml": CI_WORKFLOW,
            ".github/workflows/scorecard.yml": SCORECARD_WORKFLOW,
            "pyproject.toml": "[tool.coverage.report]\nfail_under = 100\n",
            "LICENSE": MIT,
        },
    )

    # Act
    result = tool.block(facts(tool, repo))

    # Assert
    assert result == [
        "[![ci](https://img.shields.io/github/actions/workflow/status/acme/widget/ci.yml?branch=main&style=flat-square&label=ci)](https://github.com/acme/widget/actions/workflows/ci.yml)",
        "[![release](https://img.shields.io/github/v/release/acme/widget?style=flat-square&label=release)](https://github.com/acme/widget/releases/latest)",
        "[![coverage](https://img.shields.io/badge/coverage-100%25-brightgreen?style=flat-square)](https://github.com/acme/widget/actions/workflows/ci.yml)",
        "[![openssf scorecard](https://img.shields.io/ossf-scorecard/github.com/acme/widget?style=flat-square&label=openssf%20scorecard)](https://scorecard.dev/viewer/?uri=github.com/acme/widget)",
        "[![license](https://img.shields.io/github/license/acme/widget?style=flat-square&label=license)](LICENSE)",
    ]


def test_a_private_repo_uses_native_ci_and_a_static_license(tool, tmp_path):
    # Arrange
    repo = make_repo(
        tmp_path,
        {
            ".github/workflows/tests.yml": "on: push\njobs: {}\n",
            "LICENSE.md": "Apache License\nVersion 2.0, January 2004\n",
        },
        branch="master",
    )

    # Act
    result = tool.block(facts(tool, repo, private=True))

    # Assert
    assert result == [
        "[![tests](https://github.com/acme/widget/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/acme/widget/actions/workflows/tests.yml)",
        "[![license](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](LICENSE.md)",
    ]


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({".coveragerc": "[report]\nfail_under = 95\n"}, 95),
        ({"Makefile": "test:\n\tpytest --cov-fail-under=100\n"}, 100),
        ({"scripts/coverage.sh": "MINIMUM_COVERAGE=100\n"}, 100),
        ({"package.json": '{"c8": {"lines": 100, "branches": 90}}'}, 90),
        ({"README.md": "fail_under = 100\n"}, None),
        ({"Makefile": "pytest --cov-fail-under=0\n"}, None),
    ],
)
def test_the_enforced_coverage_floor_is_the_lowest_one_found(
    tool, tmp_path, files, expected
):
    # Arrange
    repo = make_repo(tmp_path, files)

    # Act
    result = facts(tool, repo).coverage

    # Assert
    assert result == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (MIT, ("MIT", "LICENSE")),
        ("Apache License\n Version 2.0\n", ("Apache-2.0", "LICENSE")),
        (
            "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n",
            ("GPL-3.0", "LICENSE"),
        ),
        ("GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n", ("GPL-2.0", "LICENSE")),
        ("Some bespoke terms\n", None),
    ],
)
def test_the_license_file_names_its_spdx_id(tool, tmp_path, text, expected):
    # Arrange
    repo = make_repo(tmp_path, {"LICENSE": text})

    # Act
    result = facts(tool, repo).license

    # Assert
    assert result == expected


def test_a_repo_without_release_license_or_ci_gets_an_empty_block(tool, tmp_path):
    # Arrange
    repo = make_repo(tmp_path, {"main.c": "int main(void) { return 0; }\n"})

    # Act
    result = tool.block(facts(tool, repo, release=False))

    # Assert
    assert result == []


def test_apply_replaces_every_old_badge_line_with_the_block(tool):
    # Arrange
    text = (
        HEADER
        + "[![CI](https://x/badge.svg)](https://x)\n"
        + "[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](x)\n\n"
        + "[![Shell](https://img.shields.io/badge/shell-sh-lightgrey)](x)\n\n"
        + "</div>\n\n## Usage\n\n[![not header](https://y)](z)\n"
    )

    # Act
    result = tool.apply(text, ["[![ci](A)](B)", "[![license](C)](D)"])

    # Assert
    assert result == (
        HEADER
        + "[![ci](A)](B)\n[![license](C)](D)\n\n</div>\n\n## Usage\n\n"
        + "[![not header](https://y)](z)\n"
    )


def test_apply_inserts_after_the_language_line_when_there_were_none(tool):
    # Arrange
    text = HEADER + "</div>\n\n## Usage\n"

    # Act
    result = tool.apply(text, ["[![ci](A)](B)"])

    # Assert
    assert result == HEADER + "[![ci](A)](B)\n\n</div>\n\n## Usage\n"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "# widget\n\nDoes one thing.\n\n## Usage\n",
            "# widget\n\nDoes one thing.\n\n[![ci](A)](B)\n\n## Usage\n",
        ),
        ("# widget\n", "# widget\n\n[![ci](A)](B)\n"),
    ],
)
def test_apply_without_a_language_line_goes_after_the_tagline(tool, text, expected):
    # Arrange
    block = ["[![ci](A)](B)"]

    # Act
    result = tool.apply(text, block)

    # Assert
    assert result == expected


def test_an_empty_block_removes_the_old_badges(tool):
    # Arrange
    text = "# widget\n\n[![Version](x)](y)\n\nBody.\n"

    # Act
    result = tool.apply(text, [])

    # Assert
    assert result == "# widget\n\nBody.\n"


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), str(repo), *args],
        capture_output=True,
        text=True,
        env=apply_coverage_env(dict(os.environ)),
        timeout=60,
        check=False,
    )


def test_the_cli_writes_every_readme_then_check_passes(tmp_path):
    # Arrange
    repo = make_repo(
        tmp_path,
        {
            ".github/workflows/ci.yml": CI_WORKFLOW,
            "LICENSE": MIT,
            "README.md": HEADER + "[![Old](x)](y)\n\n</div>\n",
            "README.ja.md": HEADER + "</div>\n",
        },
    )
    _run(repo, "--visibility", "public", "--release", "no", "--write")

    # Act
    result = _run(repo, "--visibility", "public", "--release", "no", "--check")

    # Assert
    assert (result.returncode, result.stdout) == (0, "")
    assert "[![ci](" in (repo / "README.ja.md").read_text(encoding="utf-8")


def test_the_cli_check_names_each_stale_readme(tmp_path):
    # Arrange
    repo = make_repo(tmp_path, {"LICENSE": MIT, "README.md": "# widget\n"})

    # Act
    result = _run(repo, "--visibility", "private", "--release", "no", "--check")

    # Assert
    assert result.returncode == 1
    assert "README.md: badges differ from the standard block" in result.stdout


def test_the_cli_prints_the_block_by_default(tmp_path):
    # Arrange
    repo = make_repo(tmp_path, {"LICENSE": MIT})

    # Act
    result = _run(repo, "--visibility", "private", "--release", "no")

    # Assert
    assert result.stdout == (
        "[![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)\n"
    )


def test_a_repo_without_a_github_origin_is_refused(tmp_path):
    # Arrange
    repo = tmp_path / "plain"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=30)

    # Act
    result = _run(repo, "--visibility", "public", "--release", "no")

    # Assert
    assert result.returncode == 2
    assert "no GitHub origin remote" in result.stderr


def test_the_owner_comes_from_an_https_remote_too(tool, tmp_path):
    # Arrange
    repo = make_repo(tmp_path, {})
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "remote",
            "set-url",
            "origin",
            "https://github.com/acme/gadget",
        ],
        check=True,
        timeout=30,
    )

    # Act
    result = facts(tool, repo).slug

    # Assert
    assert result == "acme/gadget"


def test_the_default_branch_comes_from_the_clone_origin_head(tool, tmp_path):
    # Arrange
    repo = make_repo(tmp_path, {"a.txt": "x\n"})
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            "refs/remotes/origin/develop",
        ],
        check=True,
        timeout=30,
    )

    # Act
    result = facts(tool, repo).branch

    # Assert
    assert result == "develop"


def test_apply_with_no_title_puts_the_badges_first(tool):
    # Arrange
    text = "Plain notes.\n"

    # Act
    result = tool.apply(text, ["[![ci](A)](B)"])

    # Assert
    assert result == "\n[![ci](A)](B)\n\nPlain notes.\n"


def test_the_cli_leaves_topic_readmes_alone(tmp_path):
    # Arrange
    topic = "# Music\n\nHow the music driver works.\n"
    repo = make_repo(
        tmp_path,
        {
            "LICENSE": MIT,
            "README.md": "# widget\n",
            "README.Music.md": topic,
            "README.zh-HK.md": "# widget\n",
        },
    )

    # Act
    _run(repo, "--visibility", "private", "--release", "no", "--write")

    # Assert
    assert (repo / "README.Music.md").read_text(encoding="utf-8") == topic
    assert "[![license](" in (repo / "README.zh-HK.md").read_text(encoding="utf-8")

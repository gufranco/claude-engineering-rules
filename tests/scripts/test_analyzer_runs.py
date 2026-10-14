from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from _lib.analyzer_runs import ANALYZERS, analyzers_for, config, run  # noqa: E402


def _stub_tool(directory: Path, name: str, body: str) -> None:
    tool = directory / name
    tool.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    tool.chmod(0o755)


def test_analyzers_for_maps_suffixes_to_tools():
    # Arrange
    paths = (Path("a.cpp"), Path("a.py"), Path("a.kt"), Path("a.ts"))

    # Act
    names = tuple(tuple(a.name for a in analyzers_for(p)) for p in paths)

    # Assert
    assert names == (("clang-tidy",), ("ruff", "pyright"), ("detekt",), ())


def test_every_analyzer_config_file_exists():
    # Arrange
    names = (
        "clang-tidy.yaml",
        "golangci.yml",
        "ruff.toml",
        "pyrightconfig.json",
        "rubocop.yml",
        "luacheckrc",
        "detekt.yml",
        "pmd.xml",
        "swiftlint.yml",
        "analysis_options.yaml",
    )

    # Act
    missing = [name for name in names if not config(name).is_file()]

    # Assert
    assert missing == []


def test_missing_tool_is_a_failure(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("PATH", str(tmp_path))
    source = tmp_path / "a.rb"
    source.write_text("X = [1]\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["ruby"], source)

    # Assert
    assert result.failure == "rubocop is not installed; run `brew install rubocop`"


def test_unexpected_exit_code_is_a_failure(tmp_path, monkeypatch):
    # Arrange
    _stub_tool(tmp_path, "luacheck", "echo boom >&2; exit 9")
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    source = tmp_path / "a.lua"
    source.write_text("x = 1\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["lua"], source)

    # Assert
    assert result.failure == "luacheck exited 9: boom"


def test_unparsable_output_is_a_failure(tmp_path, monkeypatch):
    # Arrange
    _stub_tool(tmp_path, "rubocop", "echo not-json")
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    source = tmp_path / "a.rb"
    source.write_text("X = [1]\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["ruby"], source)

    # Assert
    assert result.failure == "rubocop produced output that could not be parsed"


def test_timeout_is_a_failure(tmp_path, monkeypatch):
    # Arrange
    _stub_tool(tmp_path, "luacheck", "sleep 5")
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    monkeypatch.setattr("_lib.analyzer_runs.TOOL_TIMEOUT_S", 1)
    source = tmp_path / "a.lua"
    source.write_text("x = 1\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["lua"], source)

    # Assert
    assert result.failure == "luacheck did not finish within 1 seconds"


def test_ruff_reports_a_mutable_default(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}:/usr/bin:/bin")
    source = tmp_path / "a.py"
    source.write_text("def f(items=[]):\n    return items\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["python-ruff"], source)

    # Assert
    assert [(f.line, f.rule) for f in result.findings] == [(1, "B006")]


def _build(key: str, path: Path, scratch: Path):
    return ANALYZERS[key].build("tool-bin", path, scratch)


def test_every_builder_names_the_binary_and_its_config(tmp_path):
    # Arrange
    sources = {key: tmp_path / f"src-{key}.txt" for key in ANALYZERS}
    for source in sources.values():
        source.write_text("x\n", encoding="utf-8")

    # Act
    invocations = {key: _build(key, sources[key], tmp_path / key) for key in ANALYZERS}

    # Assert
    assert [key for key, inv in invocations.items() if inv.argv[0] != "tool-bin"] == []


def test_clang_tidy_uses_a_compile_database_when_present(tmp_path):
    # Arrange
    (tmp_path / "compile_commands.json").write_text("[]", encoding="utf-8")
    nested = tmp_path / "src"
    nested.mkdir()
    source = nested / "a.c"
    source.write_text("int a;\n", encoding="utf-8")

    # Act
    invocation = _build("c", source, tmp_path)

    # Assert
    assert invocation.argv[-2:] == ("-p", str(tmp_path))


def test_golangci_runs_the_package_from_the_module_root(tmp_path):
    # Arrange
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    package = tmp_path / "internal" / "store"
    package.mkdir(parents=True)
    source = package / "a.go"
    source.write_text("package store\n", encoding="utf-8")

    # Act
    invocation = _build("go", source, tmp_path)

    # Assert
    assert (invocation.cwd, invocation.argv[-1], invocation.path_map) == (
        tmp_path,
        "./internal/store",
        {"internal/store/a.go": str(source)},
    )


def test_dart_analyzes_a_copy_under_the_directive_options(tmp_path):
    # Arrange
    source = tmp_path / "card.dart"
    source.write_text("class Card {}\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    # Act
    invocation = _build("dart", source, scratch)

    # Assert
    assert (
        (scratch / "analysis_options.yaml").read_text(encoding="utf-8"),
        invocation.path_map,
    ) == (
        config("analysis_options.yaml").read_text(encoding="utf-8"),
        {str(scratch / "lib" / "card.dart"): str(source)},
    )


def test_report_file_output_is_read_back(tmp_path, monkeypatch):
    # Arrange
    _stub_tool(
        tmp_path,
        "detekt",
        'for a; do case "$a" in xml:*) out="${a#xml:}";; esac; done\n'
        'printf \'<checkstyle><file name="%s"><error line="1" message="m" '
        'source="detekt.DataClassShouldBeImmutable"/></file></checkstyle>\' "$2" > "$out"',
    )
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    source = tmp_path / "A.kt"
    source.write_text("data class A(var x: Int)\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["kotlin"], source)

    # Assert
    assert [(f.line, f.rule) for f in result.findings] == [
        (1, "DataClassShouldBeImmutable")
    ]


def test_a_tool_that_cannot_start_is_a_failure(tmp_path, monkeypatch):
    # Arrange
    tool = tmp_path / "luacheck"
    tool.write_text("#!/nonexistent/interpreter\n", encoding="utf-8")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    source = tmp_path / "a.lua"
    source.write_text("x = 1\n", encoding="utf-8")

    # Act
    result = run(ANALYZERS["lua"], source)

    # Assert
    assert result.failure.startswith("luacheck could not start:")

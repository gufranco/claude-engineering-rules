from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .analyzer_parsers import (
    Parsed,
    RawFinding,
    parse_checkstyle,
    parse_clang_tidy,
    parse_dart,
    parse_golangci,
    parse_luacheck,
    parse_pmd,
    parse_pyright,
    parse_rubocop,
    parse_ruff,
    parse_swiftlint,
)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "analyzers"
TOOL_TIMEOUT_S = 240
CLANG_TIDY_FALLBACKS = (
    "/opt/homebrew/opt/llvm/bin/clang-tidy",
    "/usr/local/opt/llvm/bin/clang-tidy",
)
DART_PUBSPEC = 'name: probe\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n'


@dataclass(frozen=True, slots=True)
class Invocation:
    argv: tuple[str, ...]
    cwd: Path
    report: Path | None = None
    path_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Analyzer:
    name: str
    binary: str
    install_hint: str
    accepted_exits: frozenset[int]
    blocking: frozenset[str]
    advisory: frozenset[str]
    build: Callable[[str, Path, Path], Invocation]
    parse: Callable[[str], Parsed]


@dataclass(frozen=True, slots=True)
class RunResult:
    findings: tuple[RawFinding, ...] = ()
    failure: str = ""


def config(name: str) -> Path:
    return CONFIG_DIR / name


def resolve_binary(binary: str) -> str | None:
    found = shutil.which(binary)
    if found or binary != "clang-tidy":
        return found
    return next(
        (candidate for candidate in CLANG_TIDY_FALLBACKS if Path(candidate).is_file()),
        None,
    )


def _nearest(start: Path, marker: str) -> Path | None:
    for directory in (start, *start.parents):
        if (directory / marker).exists():
            return directory
    return None


def _clang_tidy(binary: str, path: Path, _scratch: Path) -> Invocation:
    database = _nearest(path.parent, "compile_commands.json")
    tail = ("-p", str(database)) if database else ("--",)
    argv = (
        binary,
        f"--config-file={config('clang-tidy.yaml')}",
        "--quiet",
        str(path),
        *tail,
    )
    return Invocation(argv=argv, cwd=path.parent)


def _golangci(binary: str, path: Path, _scratch: Path) -> Invocation:
    module = _nearest(path.parent, "go.mod") or path.parent
    relative = path.parent.relative_to(module)
    package = "." if str(relative) == "." else f"./{relative}"
    argv = (
        binary,
        "run",
        f"--config={config('golangci.yml')}",
        "--output.json.path=stdout",
        "--output.text.path=stderr",
        package,
    )
    return Invocation(
        argv=argv, cwd=module, path_map={str(path.relative_to(module)): str(path)}
    )


def _ruff(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "check",
        "--no-cache",
        f"--config={config('ruff.toml')}",
        "--output-format=json",
        str(path),
    )
    return Invocation(argv=argv, cwd=path.parent)


def _pyright(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "--project",
        str(config("pyrightconfig.json")),
        "--outputjson",
        str(path),
    )
    return Invocation(argv=argv, cwd=path.parent)


def _rubocop(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "--config",
        str(config("rubocop.yml")),
        "--format",
        "json",
        "--cache",
        "false",
        str(path),
    )
    return Invocation(argv=argv, cwd=path.parent)


def _luacheck(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "--config",
        str(config("luacheckrc")),
        "--formatter",
        "plain",
        "--codes",
        "--no-color",
        str(path),
    )
    return Invocation(argv=argv, cwd=path.parent)


def _detekt(binary: str, path: Path, scratch: Path) -> Invocation:
    report = scratch / "detekt.xml"
    argv = (
        binary,
        "--input",
        str(path),
        "--config",
        str(config("detekt.yml")),
        "--report",
        f"xml:{report}",
    )
    return Invocation(argv=argv, cwd=path.parent, report=report)


def _pmd(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "check",
        "-d",
        str(path),
        "-R",
        str(config("pmd.xml")),
        "-f",
        "json",
        "--no-cache",
        "--no-progress",
    )
    return Invocation(argv=argv, cwd=path.parent)


def _swiftlint(binary: str, path: Path, _scratch: Path) -> Invocation:
    argv = (
        binary,
        "lint",
        "--config",
        str(config("swiftlint.yml")),
        "--reporter",
        "json",
        "--quiet",
        str(path),
    )
    return Invocation(argv=argv, cwd=path.parent)


def _dart(binary: str, path: Path, scratch: Path) -> Invocation:
    library = scratch / "lib"
    library.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config("analysis_options.yaml"), scratch / "analysis_options.yaml")
    (scratch / "pubspec.yaml").write_text(DART_PUBSPEC, encoding="utf-8")
    copy = library / path.name
    shutil.copyfile(path, copy)
    argv = (binary, "analyze", "--format=machine", str(copy))
    return Invocation(argv=argv, cwd=scratch, path_map={str(copy): str(path)})


def _rules(*names: str) -> frozenset[str]:
    return frozenset(names)


ANALYZERS: dict[str, Analyzer] = {
    "c": Analyzer(
        "clang-tidy",
        "clang-tidy",
        "brew install llvm",
        frozenset({0, 1}),
        _rules(
            "readability-non-const-parameter",
            "misc-const-correctness",
            "cppcoreguidelines-pro-type-const-cast",
            "readability-make-member-function-const",
        ),
        _rules("cppcoreguidelines-avoid-non-const-global-variables"),
        _clang_tidy,
        parse_clang_tidy,
    ),
    "go": Analyzer(
        "golangci-lint",
        "golangci-lint",
        "brew install golangci-lint",
        frozenset({0, 1}),
        _rules("reassign", "gocritic", "revive"),
        _rules("gochecknoglobals"),
        _golangci,
        parse_golangci,
    ),
    "python-ruff": Analyzer(
        "ruff",
        "ruff",
        "uv tool install ruff",
        frozenset({0, 1}),
        _rules(
            "B006",
            "B008",
            "B020",
            "B909",
            "RUF008",
            "RUF009",
            "RUF012",
            "PLW0602",
            "PLW0603",
            "PLW0642",
            "PLW2901",
        ),
        _rules(),
        _ruff,
        parse_ruff,
    ),
    "python-pyright": Analyzer(
        "pyright",
        "pyright",
        "brew install pyright",
        frozenset({0, 1}),
        _rules("reportConstantRedefinition"),
        _rules(),
        _pyright,
        parse_pyright,
    ),
    "ruby": Analyzer(
        "rubocop",
        "rubocop",
        "brew install rubocop",
        frozenset({0, 1}),
        _rules(
            "Style/FrozenStringLiteralComment",
            "Style/MutableConstant",
            "Style/GlobalVars",
            "Style/ClassVars",
        ),
        _rules(),
        _rubocop,
        parse_rubocop,
    ),
    "lua": Analyzer(
        "luacheck",
        "luacheck",
        "brew install luacheck",
        frozenset({0, 1, 2}),
        _rules("W121", "W122", "W142"),
        _rules("W111", "W112"),
        _luacheck,
        parse_luacheck,
    ),
    "kotlin": Analyzer(
        "detekt",
        "detekt",
        "brew install detekt",
        frozenset({0, 2}),
        _rules("DataClassShouldBeImmutable"),
        _rules(),
        _detekt,
        parse_checkstyle,
    ),
    "java": Analyzer(
        "pmd",
        "pmd",
        "brew install pmd",
        frozenset({0, 4}),
        _rules(
            "ImmutableField",
            "MutableStaticState",
            "MethodReturnsInternalArray",
            "ArrayIsStoredDirectly",
            "AvoidReassigningParameters",
            "AssignmentToNonFinalStatic",
        ),
        _rules(),
        _pmd,
        parse_pmd,
    ),
    "swift": Analyzer(
        "swiftlint",
        "swiftlint",
        "brew install swiftlint",
        frozenset({0, 2}),
        _rules(),
        _rules("shared_static_var", "top_level_var"),
        _swiftlint,
        parse_swiftlint,
    ),
    "dart": Analyzer(
        "dart",
        "dart",
        "brew install dart-sdk",
        frozenset({0, 1, 2, 3}),
        _rules(
            "PREFER_FINAL_FIELDS", "PREFER_FINAL_LOCALS", "PREFER_FINAL_IN_FOR_EACH"
        ),
        _rules(),
        _dart,
        parse_dart,
    ),
}

LANGUAGE_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    **dict.fromkeys((".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp"), ("c",)),
    ".go": ("go",),
    ".py": ("python-ruff", "python-pyright"),
    ".rb": ("ruby",),
    ".lua": ("lua",),
    ".kt": ("kotlin",),
    ".kts": ("kotlin",),
    ".java": ("java",),
    ".swift": ("swift",),
    ".dart": ("dart",),
}


def analyzers_for(path: Path) -> tuple[Analyzer, ...]:
    return tuple(
        ANALYZERS[key] for key in LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), ())
    )


def _execute(invocation: Invocation) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        invocation.argv,
        cwd=invocation.cwd,
        capture_output=True,
        text=True,
        timeout=TOOL_TIMEOUT_S,
        check=False,
    )


def _output_of(
    invocation: Invocation, completed: subprocess.CompletedProcess[str]
) -> str:
    if invocation.report is None:
        return completed.stdout
    return (
        invocation.report.read_text(encoding="utf-8")
        if invocation.report.is_file()
        else ""
    )


def _remap(
    findings: tuple[RawFinding, ...], invocation: Invocation
) -> tuple[RawFinding, ...]:
    return tuple(
        RawFinding(invocation.path_map.get(f.path, f.path), f.line, f.rule, f.message)
        for f in findings
    )


def _last_line(completed: subprocess.CompletedProcess[str]) -> str:
    lines = (completed.stderr or completed.stdout).strip().splitlines()
    return lines[-1][:200] if lines else "no output"


def _run_in(analyzer: Analyzer, binary: str, path: Path, scratch: Path) -> RunResult:
    invocation = analyzer.build(binary, path, scratch)
    completed = _execute(invocation)
    if completed.returncode not in analyzer.accepted_exits:
        return RunResult(
            failure=f"{analyzer.name} exited {completed.returncode}: {_last_line(completed)}"
        )
    parsed = analyzer.parse(_output_of(invocation, completed))
    if parsed is None:
        return RunResult(
            failure=f"{analyzer.name} produced output that could not be parsed"
        )
    return RunResult(findings=_remap(parsed, invocation))


def run(analyzer: Analyzer, path: Path) -> RunResult:
    binary = resolve_binary(analyzer.binary)
    if binary is None:
        return RunResult(
            failure=f"{analyzer.name} is not installed; run `{analyzer.install_hint}`"
        )
    try:
        with tempfile.TemporaryDirectory(prefix="analyzer-") as scratch:
            return _run_in(analyzer, binary, path, Path(scratch))
    except subprocess.TimeoutExpired:
        return RunResult(
            failure=f"{analyzer.name} did not finish within {TOOL_TIMEOUT_S} seconds"
        )
    except OSError as error:
        return RunResult(failure=f"{analyzer.name} could not start: {error}")

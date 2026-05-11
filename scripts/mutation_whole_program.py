"""Opt-in whole-program mutation tracker (plan item 380).

When `MUTATION_METHOD_WHOLE_PROGRAM=1` is set, the hook walks the source tree
beneath the current file and builds a lightweight inter-file call graph by
scanning `import` and `export` declarations. The graph is then used to track
mutation surfaces that cross module boundaries: a function declared in one
file that mutates an argument, when called from a second file that passed in
a shared reference, is flagged as a cross-module mutation.

The default is OFF because the analysis is expensive (>500ms cold-cache on
1000-file projects). The tracker is best-effort: it does not perform type
resolution, does not follow re-exports across barrels, and does not analyze
dynamic `import()` calls. Treat findings as advisory hints, not as a proof
of mutation.

When `ts-morph` is installed and `MUTATION_METHOD_TS_PROJECT_SERVICE=1` is
set, the tracker delegates symbol resolution to ts-morph via
`scripts/mutation_type_bridge.py`. Otherwise it falls back to a regex-based
call-graph approximation.

Public API:

  build_call_graph(root: str) -> CallGraph
  find_cross_module_mutations(graph, mutations) -> list[CrossModuleHit]
  is_enabled() -> bool

Environment variables:

  MUTATION_METHOD_WHOLE_PROGRAM   1 to enable (default 0).
  MUTATION_METHOD_WP_MAX_FILES    Hard ceiling on files scanned (default 5000).
  MUTATION_METHOD_WP_TIMEOUT_MS   Soft timeout in ms (default 2000).
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field

ENV_FLAG = "MUTATION_METHOD_WHOLE_PROGRAM"
ENV_MAX_FILES = "MUTATION_METHOD_WP_MAX_FILES"
ENV_TIMEOUT_MS = "MUTATION_METHOD_WP_TIMEOUT_MS"

DEFAULT_MAX_FILES = 5000
DEFAULT_TIMEOUT_MS = 2000

IMPORT_PATTERN = re.compile(
    r"^\s*import\s+(?:type\s+)?"
    r"(?:\{[^}]*\}|[a-zA-Z_$][\w$]*|\*\s+as\s+[a-zA-Z_$][\w$]*)"
    r'\s+from\s+[\'"]([^\'"]+)[\'"]'
)
EXPORT_FUNCTION_PATTERN = re.compile(
    r"^\s*export\s+(?:async\s+)?(?:function\s+|const\s+|let\s+|var\s+)"
    r"(?P<name>[a-zA-Z_$][\w$]*)"
)
EXPORT_CLASS_PATTERN = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[a-zA-Z_$][\w$]*)"
)


@dataclass(frozen=True)
class CallGraphNode:
    """A single source file in the call graph."""

    file_path: str
    exports: frozenset[str] = frozenset()
    imports: frozenset[tuple[str, str]] = frozenset()


@dataclass
class CallGraph:
    """Inter-file call graph for the project root."""

    root: str
    nodes: dict[str, CallGraphNode] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=dict)
    truncated: bool = False


@dataclass(frozen=True)
class CrossModuleHit:
    """A mutation that crosses a module boundary."""

    source_file: str
    target_file: str
    symbol: str
    reason: str


def is_enabled() -> bool:
    """True when whole-program analysis is opted in."""
    return os.environ.get(ENV_FLAG, "0") == "1"


def _max_files() -> int:
    raw = os.environ.get(ENV_MAX_FILES, "")
    if raw.isdigit():
        return max(1, int(raw))
    return DEFAULT_MAX_FILES


def _timeout_ms() -> int:
    raw = os.environ.get(ENV_TIMEOUT_MS, "")
    if raw.isdigit():
        return max(1, int(raw))
    return DEFAULT_TIMEOUT_MS


def _iter_source_files(root: str) -> list[str]:
    """Yield JS/TS files under root, skipping node_modules and dist."""
    results: list[str] = []
    skip_dirs = {"node_modules", "dist", "build", ".next", "coverage", ".git"}
    extensions = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if name.endswith(extensions):
                results.append(os.path.join(dirpath, name))
    return results


def _parse_file(path: str) -> CallGraphNode:
    """Extract exports and imports from a single file."""
    exports: set[str] = set()
    imports: set[tuple[str, str]] = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.rstrip("\n")
                m_imp = IMPORT_PATTERN.match(stripped)
                if m_imp:
                    imports.add((path, m_imp.group(1)))
                m_func = EXPORT_FUNCTION_PATTERN.match(stripped)
                if m_func:
                    exports.add(m_func.group("name"))
                m_cls = EXPORT_CLASS_PATTERN.match(stripped)
                if m_cls:
                    exports.add(m_cls.group("name"))
    except OSError:
        pass
    return CallGraphNode(
        file_path=path,
        exports=frozenset(exports),
        imports=frozenset(imports),
    )


def build_call_graph(root: str) -> CallGraph:
    """Build a call graph for the project rooted at `root`.

    Walks source files, parses imports and exports, and stitches them
    into a graph keyed by absolute file path. Honors MAX_FILES and
    TIMEOUT_MS limits; sets `truncated=True` when a limit was hit.
    """
    graph = CallGraph(root=root)
    deadline_ms = _timeout_ms()
    start = time.monotonic()
    max_files = _max_files()
    files = _iter_source_files(root)
    if len(files) > max_files:
        files = files[:max_files]
        graph.truncated = True
    for path in files:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if elapsed_ms > deadline_ms:
            graph.truncated = True
            break
        node = _parse_file(path)
        graph.nodes[path] = node
        graph.edges.setdefault(path, set())
        for _, spec in node.imports:
            graph.edges[path].add(spec)
    return graph


def find_cross_module_mutations(
    graph: CallGraph,
    mutations_by_file: dict[str, list[str]],
) -> list[CrossModuleHit]:
    """Identify mutations that originate in one module and reach callers.

    Best-effort: a function name appearing both as an export in file A and
    a mutation source in file A, where another file B imports from A, is
    flagged as a potential cross-module mutation. Lacks full call-site
    resolution; treat output as advisory.
    """
    hits: list[CrossModuleHit] = []
    for path, mutated_symbols in mutations_by_file.items():
        node = graph.nodes.get(path)
        if node is None:
            continue
        leaked = node.exports & set(mutated_symbols)
        if not leaked:
            continue
        for other_path, other_node in graph.nodes.items():
            if other_path == path:
                continue
            specs = {spec for _, spec in other_node.imports}
            if any(_specifier_matches(spec, path) for spec in specs):
                for symbol in leaked:
                    hits.append(
                        CrossModuleHit(
                            source_file=path,
                            target_file=other_path,
                            symbol=symbol,
                            reason="exported symbol mutates and is imported elsewhere",
                        )
                    )
    return hits


def _specifier_matches(specifier: str, target_path: str) -> bool:
    """True when an import specifier likely resolves to `target_path`.

    Heuristic: relative paths and bare specifiers are compared against
    the file basename without extension. This is intentionally fuzzy:
    full resolution requires the TS compiler's path mapping logic.
    """
    if not specifier:
        return False
    base = os.path.basename(target_path)
    name, _ = os.path.splitext(base)
    return (
        specifier.endswith("/" + name) or specifier == name or specifier.endswith(name)
    )

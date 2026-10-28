from __future__ import annotations

import ast
import re
import textwrap
from collections.abc import Iterator
from typing import TypeGuard

from .guard_runner import Finding
from .suppression import line_or_prev_has_suppression

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef

MUTATING_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "sort",
        "reverse",
        "update",
        "add",
        "discard",
        "setdefault",
        "popitem",
        "appendleft",
        "extendleft",
        "difference_update",
        "intersection_update",
        "symmetric_difference_update",
        "rotate",
    }
)
READ_ONLY_ANNOTATIONS = frozenset(
    {
        "Sequence",
        "Mapping",
        "AbstractSet",
        "Collection",
        "Iterable",
        "FrozenSet",
        "frozenset",
        "tuple",
        "Tuple",
        "MappingProxyType",
    }
)
COLLECTION_ANNOTATIONS = (
    frozenset(
        {
            "list",
            "List",
            "dict",
            "Dict",
            "set",
            "Set",
            "bytearray",
            "deque",
            "Counter",
            "defaultdict",
            "OrderedDict",
            "MutableSequence",
            "MutableMapping",
            "MutableSet",
        }
    )
    | READ_ONLY_ANNOTATIONS
)
MUTABLE_FACTORIES = frozenset(
    {
        "list",
        "dict",
        "set",
        "bytearray",
        "defaultdict",
        "deque",
        "Counter",
        "OrderedDict",
    }
)
INIT_HOOKS = frozenset(
    {
        "__init__",
        "__post_init__",
        "__new__",
        "__setstate__",
        "__attrs_post_init__",
        "__init_subclass__",
        "__set_name__",
    }
)
VALIDATED_MODEL_BASES = frozenset(
    {"BaseModel", "BaseSettings", "SQLModel", "TypedDict"}
)
DATACLASS_DECORATORS = frozenset({"dataclass", "define", "s", "attrs", "mutable"})
EXEMPT_PARAMS = frozenset({"self", "cls"})
CONFIGURATION_CLASSES = frozenset({"Meta", "Config"})
SKIP_SUFFIXES = (".pyi", "_test.py", "_tests.py", ".test.py", "/conftest.py")
SKIP_SEGMENTS = (
    "/tests/",
    "/test/",
    "/__tests__/",
    "/migrations/",
    "/migration/",
    "/fixtures/",
    "/.claude/hooks/",
    "/site-packages/",
)
MUTABLE_DEFAULT_REGEX = re.compile(
    r"def\s+\w+\s*\([^)]*?=\s*(?:\[\s*\]|\{\s*\}|set\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\))",
    re.DOTALL,
)
SHARED_DEFAULT = "mutable default argument. One instance is shared by every call"


def is_python_source(path: str) -> bool:
    lowered = path.lower()
    if not lowered.endswith(".py") or lowered.endswith(SKIP_SUFFIXES):
        return False
    if any(segment in lowered for segment in SKIP_SEGMENTS):
        return False
    return not lowered.rsplit("/", 1)[-1].startswith("test_")


def annotation_name(node: ast.expr | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return annotation_name(node.value)
    if isinstance(node, ast.BinOp):
        return annotation_name(node.left) or annotation_name(node.right)
    return ""


def line_of(node: ast.AST) -> int:
    return int(getattr(node, "lineno", 0))


def root_name(node: ast.expr) -> str:
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def is_mutable_value(node: ast.expr | None) -> bool:
    if isinstance(
        node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    ):
        return True
    return (
        isinstance(node, ast.Call) and annotation_name(node.func) in MUTABLE_FACTORIES
    )


Mutation = tuple[str, bool]
NO_MUTATION: Mutation = ("", False)


def _call_mutation(node: ast.Call) -> Mutation:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in MUTATING_METHODS:
        return root_name(func.value), True
    if isinstance(func, ast.Name) and func.id in {"setattr", "delattr"} and node.args:
        return root_name(node.args[0]), False
    return NO_MUTATION


def _target_mutation(targets: list[ast.expr]) -> Mutation:
    written = [t for t in targets if isinstance(t, (ast.Subscript, ast.Attribute))]
    if not written:
        return NO_MUTATION
    target = written[-1]
    return root_name(target.value), isinstance(target, ast.Subscript)


def mutation_of(node: ast.AST) -> Mutation:
    if isinstance(node, ast.Call):
        return _call_mutation(node)
    if isinstance(node, (ast.Assign, ast.Delete)):
        return _target_mutation(node.targets)
    if isinstance(node, (ast.AugAssign, ast.AnnAssign)) and node.value is not None:
        return _target_mutation([node.target])
    return NO_MUTATION


def mutated_root(node: ast.AST) -> str:
    return mutation_of(node)[0]


def parameters_of(func: FunctionNode) -> dict[str, str]:
    args = func.args
    every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    every.extend(arg for arg in (args.vararg, args.kwarg) if arg is not None)
    return {
        arg.arg: annotation_name(arg.annotation)
        for arg in every
        if arg.arg not in EXEMPT_PARAMS
    }


def rebound_names(func: FunctionNode) -> frozenset[str]:
    names = (
        target.id
        for node in ast.walk(func)
        if isinstance(node, BindingNode)
        for target in _binding_targets(node)
        if isinstance(target, ast.Name)
    )
    return frozenset(names)


BindingNode = ast.Assign | ast.AnnAssign | ast.For | ast.With | ast.NamedExpr


def _binding_targets(node: BindingNode) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.With):
        return [
            item.optional_vars for item in node.items if item.optional_vars is not None
        ]
    return [node.target]


def _in_place_plus(node: ast.AST, params: dict[str, str]) -> str:
    if not isinstance(node, ast.AugAssign) or not isinstance(node.target, ast.Name):
        return ""
    name = node.target.id
    return name if params.get(name, "") in COLLECTION_ANNOTATIONS else ""


def _param_message(func: FunctionNode, name: str, params: dict[str, str]) -> str:
    annotated = params[name]
    note = f", annotated `{annotated}`" if annotated in READ_ONLY_ANNOTATIONS else ""
    return f"parameter `{name}` is mutated inside `{func.name}`{note}"


def _parameter_mutation(
    node: ast.AST, params: dict[str, str], rebound: frozenset[str]
) -> Mutation:
    in_place = _in_place_plus(node, params)
    name, blocking = (in_place, True) if in_place else mutation_of(node)
    if name in params and name not in rebound:
        return name, blocking
    return NO_MUTATION


def parameter_findings(func: FunctionNode) -> Iterator[Finding]:
    params = parameters_of(func)
    rebound = rebound_names(func)
    for node in ast.walk(func):
        name, blocking = _parameter_mutation(node, params, rebound)
        if name:
            yield Finding(
                line=line_of(node),
                message=_param_message(func, name, params),
                blocking=blocking,
            )


def default_findings(func: FunctionNode) -> Iterator[Finding]:
    defaults = [
        *func.args.defaults,
        *(d for d in func.args.kw_defaults if d is not None),
    ]
    for default in defaults:
        if is_mutable_value(default):
            yield Finding(
                line=default.lineno, message=f"{SHARED_DEFAULT} of `{func.name}`"
            )


def _is_frozen_escape(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    func = node.func
    return (
        func.attr == "__setattr__"
        and isinstance(func.value, ast.Name)
        and func.value.id == "object"
    )


def escape_findings(func: FunctionNode) -> Iterator[Finding]:
    if func.name in INIT_HOOKS:
        return
    for node in ast.walk(func):
        if _is_frozen_escape(node):
            yield Finding(
                line=line_of(node),
                message=f"`object.__setattr__` bypasses a frozen instance inside `{func.name}`",
            )


def global_findings(func: FunctionNode) -> Iterator[Finding]:
    for node in ast.walk(func):
        if isinstance(node, ast.Global):
            for name in node.names:
                yield Finding(
                    line=line_of(node),
                    message=f"global `{name}` is rebound inside `{func.name}`",
                )


def module_mutables(tree: ast.Module) -> frozenset[str]:
    names = (
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and is_mutable_value(node.value)
        for target in _binding_targets(node)
        if isinstance(target, ast.Name) and target.id != "__all__"
    )
    return frozenset(names)


def module_state_findings(
    func: FunctionNode, shared: frozenset[str]
) -> Iterator[Finding]:
    local = rebound_names(func) | frozenset(parameters_of(func))
    for node in ast.walk(func):
        name = mutated_root(node)
        if name in shared and name not in local:
            yield Finding(
                line=line_of(node),
                message=f"module-level `{name}` is mutated inside `{func.name}`",
            )


def _class_is_validated_model(node: ast.ClassDef) -> bool:
    return any(annotation_name(base) in VALIDATED_MODEL_BASES for base in node.bases)


def _is_shared_name(target: ast.expr) -> TypeGuard[ast.Name]:
    return isinstance(target, ast.Name) and not (
        target.id.startswith("__") and target.id.endswith("__")
    )


def class_attribute_findings(node: ast.ClassDef) -> Iterator[Finding]:
    if _class_is_validated_model(node) or node.name in CONFIGURATION_CLASSES:
        return
    for item in node.body:
        if not isinstance(item, (ast.Assign, ast.AnnAssign)) or not is_mutable_value(
            item.value
        ):
            continue
        if (
            isinstance(item, ast.AnnAssign)
            and annotation_name(item.annotation) == "ClassVar"
        ):
            continue
        for target in _binding_targets(item):
            if _is_shared_name(target):
                yield Finding(
                    line=item.lineno,
                    message=f"mutable class attribute `{target.id}` is shared by every instance of `{node.name}`",
                )


def _is_mutable_dataclass_decorator(decorator: ast.expr) -> bool:
    call = decorator if isinstance(decorator, ast.Call) else None
    target = call.func if call is not None else decorator
    if annotation_name(target) not in DATACLASS_DECORATORS:
        return False
    keywords = call.keywords if call is not None else []
    return not any(
        kw.arg == "frozen"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in keywords
    )


def dataclass_findings(node: ast.ClassDef) -> Iterator[Finding]:
    for decorator in node.decorator_list:
        if _is_mutable_dataclass_decorator(decorator):
            yield Finding(
                line=decorator.lineno,
                message=f"`{node.name}` is a dataclass without `frozen=True`",
                blocking=False,
            )


def _function_findings(func: FunctionNode, shared: frozenset[str]) -> Iterator[Finding]:
    yield from default_findings(func)
    yield from parameter_findings(func)
    yield from escape_findings(func)
    yield from global_findings(func)
    yield from module_state_findings(func, shared)


def tree_findings(tree: ast.Module) -> Iterator[Finding]:
    shared = module_mutables(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from _function_findings(node, shared)
        elif isinstance(node, ast.ClassDef):
            yield from class_attribute_findings(node)
            yield from dataclass_findings(node)


def parse_fragment(text: str) -> ast.Module | None:
    for candidate in (text, textwrap.dedent(text)):
        try:
            return ast.parse(candidate)
        except SyntaxError:
            continue
    return None


def regex_findings(text: str) -> Iterator[Finding]:
    for match in MUTABLE_DEFAULT_REGEX.finditer(text):
        yield Finding(
            line=text.count("\n", 0, match.start()) + 1, message=SHARED_DEFAULT
        )


def find(text: str) -> tuple[Finding, ...]:
    lines = text.splitlines()
    tree = parse_fragment(text)
    found = tree_findings(tree) if tree is not None else regex_findings(text)
    unique = dict.fromkeys(found)
    return tuple(
        hit for hit in unique if not line_or_prev_has_suppression(lines, hit.line - 1)
    )

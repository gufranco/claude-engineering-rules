"""Assignment-shaped mutation detectors.

Covers in-place mutations expressed as assignments rather than method calls:

  - Property assignment: `obj.prop = value`
  - Computed property assignment: `obj['prop'] = value`
  - Index assignment: `arr[i] = value`
  - Compound assignment: `obj.prop += value` plus 14 other operators
  - Increment / decrement: `obj.prop++`, `--obj.prop`
  - Object utility mutations: Object.assign with non-empty target,
    defineProperty, defineProperties, setPrototypeOf
  - Reflect counterparts: Reflect.set / deleteProperty / defineProperty /
    setPrototypeOf
  - delete operator on member access
  - Parameter reassignment and parameter-property reassignment
  - Let-could-be-const (heuristic, only on full-file Write payloads)

Each detector is pure and returns `Match` records. The orchestrator filters
hits via the suppression module and the state-management allowlist.
"""

from __future__ import annotations

import re

from mutation_allowlists import is_dom_assignment, is_dom_receiver
from mutation_detectors_core import Match, strip_strings_comments, truncate_excerpt


def _split_chain(chain: str) -> tuple[str, str]:
    """Return `(parent_chain, last_segment)` for `a.b.c` -> `("a.b", "c")`.

    Handles bare identifiers by returning `("", chain)`. Used to feed the
    DOM allowlist helpers when a detector regex captures the full receiver
    chain (e.g., `el.scrollTop` in compound assignments) but the DOM check
    needs the property name in isolation.
    """
    if "." not in chain:
        return "", chain
    parent, _, last = chain.rpartition(".")
    return parent, last


PROPERTY_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\.(?P<prop>[a-zA-Z_$][\w$]*)\s*(?P<op>=)(?!=)"
)

COMPUTED_PROPERTY_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\[\s*(?P<key>[^\]]+?)\s*\]\s*(?P<op>=)(?!=)"
)

COMPOUND_OPS: tuple[str, ...] = (
    r"\+=",
    r"-=",
    r"\*\*=",
    r"\*=",
    r"/=",
    r"%=",
    r"<<=",
    r">>>=",
    r">>=",
    r"&&=",
    r"\|\|=",
    r"\?\?=",
    r"&=",
    r"\|=",
    r"\^=",
)

COMPOUND_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)\s*(?P<op>"
    + "|".join(COMPOUND_OPS)
    + r")"
)

COMPOUND_INDEX_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*\s*\[[^\]]+\])\s*(?P<op>"
    + "|".join(COMPOUND_OPS)
    + r")"
)

UPDATE_POSTFIX_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)\s*(?P<op>\+\+|--)"
)

UPDATE_PREFIX_PATTERN = re.compile(
    r"(?P<op>\+\+|--)\s*(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)+)"
)

OBJECT_ASSIGN_PATTERN = re.compile(r"\bObject\.assign\s*\(")


def _extract_first_arg(masked: str, paren_idx: int) -> str | None:
    """Walk forward from `(` at `paren_idx` and return the first argument text.

    Tracks paren depth so nested calls like `new Object()` do not trip the
    parser. Stops at the first comma or unmatched `)` at depth 1, returning
    the text in between (stripped). Returns None if the parens are unbalanced
    or the input runs out before closure.
    """
    depth = 0
    start = paren_idx + 1
    end = -1
    for i in range(paren_idx, len(masked)):
        ch = masked[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
        elif ch == "," and depth == 1:
            end = i
            break
    if end < 0:
        return None
    return masked[start:end].strip()


OBJECT_DEFINE_PROPERTY_PATTERN = re.compile(r"\bObject\.defineProperty\s*\(")
OBJECT_DEFINE_PROPERTIES_PATTERN = re.compile(r"\bObject\.defineProperties\s*\(")
OBJECT_SET_PROTOTYPE_OF_PATTERN = re.compile(r"\bObject\.setPrototypeOf\s*\(")

REFLECT_SET_PATTERN = re.compile(r"\bReflect\.set\s*\(")
REFLECT_DELETE_PROPERTY_PATTERN = re.compile(r"\bReflect\.deleteProperty\s*\(")
REFLECT_DEFINE_PROPERTY_PATTERN = re.compile(r"\bReflect\.defineProperty\s*\(")
REFLECT_SET_PROTOTYPE_OF_PATTERN = re.compile(r"\bReflect\.setPrototypeOf\s*\(")

DELETE_PATTERN = re.compile(
    r"\bdelete\s+(?P<target>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*|\s*\[[^\]]+\])+)"
)

GLOBAL_ASSIGN_PATTERN = re.compile(
    r"\b(?:globalThis|process\.env)\.[a-zA-Z_$][\w$]*\s*=(?!=)"
)

LET_DECL_PATTERN = re.compile(
    r"^\s*(?:export\s+)?let\s+(?P<name>[a-zA-Z_$][\w$]*)(?:\s*:\s*[^=;]+)?\s*=\s*"
)

LET_NO_INIT_PATTERN = re.compile(
    r"^\s*(?:export\s+)?let\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=;]+)?\s*;\s*$"
)

LET_FOR_HEAD_PATTERN = re.compile(r"\bfor\s*\(\s*let\s+")

PARAM_REASSIGN_FN_PATTERN = re.compile(
    r"\bfunction\s+[a-zA-Z_$][\w$]*\s*\(\s*(?P<params>[^)]*)\)|"
    r"\(\s*(?P<arrow_params>[^)]*)\)\s*=>"
)

NEW_INSTANCE_TARGETS = re.compile(
    r"^\s*\{\s*\}|\bnew\s+Object\s*\(\s*\)|^\s*Object\.create\s*\("
)

KNOWN_PROP_REASSIGN_PARAM_NAMES: frozenset[str] = frozenset(
    {
        "acc",
        "accumulator",
        "result",
        "ctx",
        "context",
        "req",
        "request",
        "res",
        "response",
        "next",
        "e",
        "event",
        "draft",
    }
)


def _iter_lines(text: str) -> list[tuple[int, str, str]]:
    out: list[tuple[int, str, str]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        out.append((idx, line, strip_strings_comments(line)))
    return out


def _make_match(
    detector: str,
    lineno: int,
    col: int,
    raw: str,
    fix_hint: str,
    metadata: dict[str, str] | None = None,
) -> Match:
    return Match(
        line=lineno,
        col=col + 1,
        text=truncate_excerpt(raw, 120),
        detector=detector,
        fix_hint=fix_hint,
        metadata=metadata or {},
    )


def _looks_like_declaration(line: str, masked: str) -> bool:
    """True when the line is a declaration site, not a mutation.

    Recognizes `const`, `let`, `var` declarations, class field initializers,
    and function default-parameter values, all of which bind a value rather
    than rewrite an existing reference.
    """
    stripped = masked.strip()
    if stripped.startswith(
        ("const ", "let ", "var ", "export const ", "export let ", "export var ")
    ):
        return True
    if stripped.startswith(
        ("public ", "private ", "protected ", "readonly ", "static ")
    ):
        return True
    if re.match(r"^\s*[a-zA-Z_$][\w$]*\s*[?!]?\s*:\s*[^=]+$", line):
        return True
    return False


def detect_property_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect direct property mutation via `obj.prop = value`."""
    results: list[Match] = []
    fix_hint = (
        "Replace `obj.prop = value` with `obj = { ...obj, prop: value }` or return a copy. "
        "Mark parameters as `Readonly<T>` to enforce at the type level."
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        for m in PROPERTY_ASSIGN_PATTERN.finditer(masked):
            full = m.group(0)
            if "==" in full or "===" in full or "=>" in full:
                continue
            receiver = m.group("receiver") or ""
            prop = m.group("prop") or ""
            if is_dom_assignment(receiver, prop):
                continue
            results.append(
                _make_match(
                    "property.assignment",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": receiver, "prop": prop},
                )
            )
    return results


def detect_computed_or_index_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `obj['prop'] = value` and `arr[i] = value`."""
    results: list[Match] = []
    fix_hint = (
        "For arrays use `arr.with(i, value)` (ES2023) or `arr.map((v, j) => j === i ? value : v)`. "
        "For objects use `{ ...obj, [key]: value }`."
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        for m in COMPUTED_PROPERTY_PATTERN.finditer(masked):
            full = m.group(0)
            if "==" in full or "===" in full:
                continue
            receiver = m.group("receiver") or ""
            if is_dom_receiver(receiver):
                continue
            results.append(
                _make_match(
                    "property.computed",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "receiver": receiver,
                        "key": (m.group("key") or "").strip()[:60],
                    },
                )
            )
    return results


def detect_compound_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect compound operators on member targets (`obj.prop += x`)."""
    results: list[Match] = []
    fix_hint = (
        "Compound assignments mutate the receiver. Replace `obj.prop += value` with "
        "`obj = { ...obj, prop: obj.prop + value }` or compute a new value separately."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in COMPOUND_PATTERN.finditer(masked):
            chain = m.group("receiver") or ""
            parent, last = _split_chain(chain)
            if is_dom_assignment(parent, last):
                continue
            results.append(
                _make_match(
                    "property.compound",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": chain, "op": m.group("op") or ""},
                )
            )
        for m in COMPOUND_INDEX_PATTERN.finditer(masked):
            chain = m.group("receiver") or ""
            head = chain.split("[", 1)[0].strip()
            if is_dom_receiver(head):
                continue
            results.append(
                _make_match(
                    "property.compound-index",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": chain, "op": m.group("op") or ""},
                )
            )
    return results


def detect_increment_decrement(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `obj.prop++`, `--obj.prop`, and bracket-target equivalents."""
    results: list[Match] = []
    fix_hint = (
        "Increment / decrement on a member mutates the receiver. Replace `obj.prop++` with "
        "`obj = { ...obj, prop: obj.prop + 1 }`."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in UPDATE_POSTFIX_PATTERN.finditer(masked):
            chain = m.group("receiver") or ""
            parent, last = _split_chain(chain)
            if is_dom_assignment(parent, last):
                continue
            results.append(
                _make_match(
                    "property.increment",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": chain, "op": m.group("op") or ""},
                )
            )
        for m in UPDATE_PREFIX_PATTERN.finditer(masked):
            chain = m.group("receiver") or ""
            parent, last = _split_chain(chain)
            if is_dom_assignment(parent, last):
                continue
            results.append(
                _make_match(
                    "property.increment-prefix",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": chain, "op": m.group("op") or ""},
                )
            )
    return results


def detect_object_assign_target_mutation(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `Object.assign(target, ...sources)` with a non-fresh target."""
    results: list[Match] = []
    fix_hint = (
        "`Object.assign(target, source)` mutates `target`. Use `Object.assign({}, target, source)` "
        "or `{ ...target, ...source }` to produce a new object. When the target is dynamic, "
        "wrap with a fresh `{}` literal first."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in OBJECT_ASSIGN_PATTERN.finditer(masked):
            paren_idx = masked.find("(", m.start())
            first = _extract_first_arg(masked, paren_idx) if paren_idx >= 0 else None
            if first is None:
                continue
            if NEW_INSTANCE_TARGETS.match(first):
                continue
            results.append(
                _make_match(
                    "object.assign",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "first_arg": first[:60],
                    },
                )
            )
    return results


def detect_object_define_setprototype(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect Object.defineProperty / defineProperties / setPrototypeOf."""
    results: list[Match] = []
    define_fix = (
        "`Object.defineProperty` rewrites the descriptor. For static shapes declare the property "
        "in the type and the literal. For dynamic computed keys use `{ ...obj, [key]: value }`."
    )
    proto_fix = (
        "`Object.setPrototypeOf` is slow on V8 and breaks shape inference. Use class inheritance, "
        "a factory function, or `Object.create(proto, descriptors)` to produce a fresh object."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in OBJECT_DEFINE_PROPERTY_PATTERN.finditer(masked):
            results.append(
                _make_match("object.defineProperty", lineno, m.start(), raw, define_fix)
            )
        for m in OBJECT_DEFINE_PROPERTIES_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    "object.defineProperties", lineno, m.start(), raw, define_fix
                )
            )
        for m in OBJECT_SET_PROTOTYPE_OF_PATTERN.finditer(masked):
            results.append(
                _make_match("object.setPrototypeOf", lineno, m.start(), raw, proto_fix)
            )
    return results


def detect_reflect_mutations(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect Reflect mutations (set / deleteProperty / defineProperty / setPrototypeOf)."""
    results: list[Match] = []
    set_fix = "Replace `Reflect.set(obj, key, value)` with `{ ...obj, [key]: value }`."
    delete_fix = (
        "Replace `Reflect.deleteProperty(obj, key)` with destructured rest: "
        "`const { [key]: _omit, ...rest } = obj`."
    )
    define_fix = (
        "`Reflect.defineProperty` rewrites the descriptor. Declare the property in the type and "
        "the object literal instead."
    )
    proto_fix = (
        "`Reflect.setPrototypeOf` mutates the prototype chain at runtime. Use class inheritance "
        "or a factory function."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in REFLECT_SET_PATTERN.finditer(masked):
            results.append(_make_match("reflect.set", lineno, m.start(), raw, set_fix))
        for m in REFLECT_DELETE_PROPERTY_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    "reflect.deleteProperty", lineno, m.start(), raw, delete_fix
                )
            )
        for m in REFLECT_DEFINE_PROPERTY_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    "reflect.defineProperty", lineno, m.start(), raw, define_fix
                )
            )
        for m in REFLECT_SET_PROTOTYPE_OF_PATTERN.finditer(masked):
            results.append(
                _make_match("reflect.setPrototypeOf", lineno, m.start(), raw, proto_fix)
            )
    return results


def detect_delete_operator(text: str, lang: str | None, file_path: str) -> list[Match]:
    """Detect `delete obj.prop`, `delete obj['prop']`, `delete arr[i]`."""
    results: list[Match] = []
    fix_hint = (
        "For objects use destructured rest to omit a key: "
        "`const { [key]: _omit, ...rest } = obj; return rest;`. "
        "For arrays use `arr.toSpliced(i, 1)` (ES2023) or `arr.filter((_, j) => j !== i)`."
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in DELETE_PATTERN.finditer(masked):
            target = (m.group("target") or "").strip()
            results.append(
                _make_match(
                    "delete-operator",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"target": target[:60]},
                )
            )
    return results


def detect_global_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect mutation on globalThis, window, self, process.env."""
    results: list[Match] = []
    fix_hint = (
        "Mutating `globalThis`, `window`, `process.env`, or similar global objects is module-scope "
        "side effect. Use a typed module export or a configuration object passed by argument. "
        'Rule: ~/.claude/rules/code-style.md "No side effects at module level".'
    )
    for lineno, raw, masked in _iter_lines(text):
        for m in GLOBAL_ASSIGN_PATTERN.finditer(masked):
            results.append(
                _make_match("global.assignment", lineno, m.start(), raw, fix_hint)
            )
    return results


def detect_param_reassignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect parameter reassignment patterns.

    Two-pass heuristic: collect parameter names from function signatures
    in the file, then flag any subsequent line that reassigns or compound-
    assigns to one of them. Conventional names from
    `KNOWN_PROP_REASSIGN_PARAM_NAMES` are exempt for property mutation per
    the `no-param-reassign` `ignorePropertyModificationsFor` defaults.
    """
    results: list[Match] = []
    params = _collect_param_names(text)
    if not params:
        return results
    fix_hint = (
        "Never mutate function arguments. Copy at function entry: "
        "`const localOpts = { ...opts };`. Or accept the parameter as `Readonly<T>` and "
        'return a new object. Rule: ~/.claude/rules/code-style.md "Never mutate function arguments".'
    )
    pattern = re.compile(
        r"\b(?P<name>" + "|".join(re.escape(p) for p in params) + r")\b"
        r"(?:\s*=(?!=)|\s*\+=|\s*-=|\s*\*=|\s*/=|\s*%=|\s*\.[a-zA-Z_$][\w$]*\s*=(?!=)|\s*\[[^\]]+\]\s*=(?!=))"
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        if (
            "=>" in masked
            or re.match(r"^\s*function\b", masked)
            or re.match(r"^\s*[a-zA-Z_$][\w$]*\s*\(", masked)
        ):
            continue
        for m in pattern.finditer(masked):
            name = m.group("name") or ""
            if name in KNOWN_PROP_REASSIGN_PARAM_NAMES:
                continue
            results.append(
                _make_match(
                    "param.reassign", lineno, m.start(), raw, fix_hint, {"name": name}
                )
            )
    return results


def _collect_param_names(text: str) -> set[str]:
    """Return parameter identifiers seen across function signatures.

    Only handles simple parameter lists. Destructured and rest parameters
    are intentionally skipped: they need an AST walk to extract every
    bound name correctly, and over-flagging here would punish common
    React-style props destructuring.
    """
    found: set[str] = set()
    for raw in text.splitlines():
        masked = strip_strings_comments(raw)
        for m in PARAM_REASSIGN_FN_PATTERN.finditer(masked):
            params_text = m.group("params") or m.group("arrow_params") or ""
            for token in params_text.split(","):
                token = token.strip()
                if not token or token.startswith(("{", "[", "...")):
                    continue
                name_match = re.match(r"^([a-zA-Z_$][\w$]*)\s*[?:]?", token)
                if name_match:
                    name = name_match.group(1)
                    if name not in ("function", "async", "static", "return", "this"):
                        found.add(name)
    return found


def detect_let_could_be_const(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `let` declarations that are never reassigned later in the file.

    Runs only on full-file Write payloads so the analysis sees every line.
    Skips `for` heads, destructured declarations, and `let` declared without
    an initializer (handled as advisory in a future iteration).
    """
    results: list[Match] = []
    fix_hint = (
        "`let` that is never reassigned must be `const`. Rule: "
        '~/.claude/rules/code-style.md "let that could be const is a code review failure".'
    )
    lines = text.splitlines()
    declared: list[tuple[int, str, str]] = []
    for idx, raw in enumerate(lines, start=1):
        masked = strip_strings_comments(raw)
        if LET_FOR_HEAD_PATTERN.search(masked):
            continue
        m = LET_DECL_PATTERN.match(masked)
        if not m:
            continue
        name = m.group("name")
        if not name:
            continue
        declared.append((idx, raw, name))

    if not declared:
        return results

    body = "\n".join(strip_strings_comments(line) for line in lines)
    for lineno, raw, name in declared:
        reassign_pattern = re.compile(
            rf"\b{re.escape(name)}\b\s*(?:=(?!=)|\+=|-=|\*=|/=|%=|\+\+|--|\.[a-zA-Z_$][\w$]*\s*=(?!=)|\[[^\]]+\]\s*=(?!=))"
        )
        first_decl_idx = body.find(raw)
        scan_from = first_decl_idx + len(raw) if first_decl_idx >= 0 else 0
        if not reassign_pattern.search(body[scan_from:]):
            results.append(
                _make_match(
                    "let.could-be-const", lineno, 0, raw, fix_hint, {"name": name}
                )
            )
    return results


OPTIONAL_CHAIN_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\?\.(?P<prop>[a-zA-Z_$][\w$]*)\s*(?P<op>=)(?!=)"
)


def detect_optional_chain_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `obj?.prop = value` (experimental, plan items 291-292).

    Optional-chain assignment is parsed by some toolchains but rejected at
    runtime in strict mode and is illegal per the ECMAScript grammar's
    short-circuit assignment rules. Flag it as an experimental detector
    behind `MUTATION_METHOD_EXPERIMENTAL_OPTIONAL_CHAIN_ASSIGN=1`.

    The orchestrator gates the detector via the experimental flag check;
    this function performs the pattern match unconditionally so unit tests
    can exercise it directly.
    """
    results: list[Match] = []
    fix_hint = (
        "Optional-chain assignment is not allowed by the ECMAScript spec. "
        "Replace with an explicit guard: `if (obj) { obj = { ...obj, prop: v } }` "
        "or restructure to avoid the assignment."
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        for m in OPTIONAL_CHAIN_ASSIGN_PATTERN.finditer(masked):
            receiver = m.group("receiver") or ""
            prop = m.group("prop") or ""
            results.append(
                _make_match(
                    "experimental.optional-chain-assignment",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {"receiver": receiver, "prop": prop},
                )
            )
    return results


PRIVATE_FIELD_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)\s*(?P<op>=(?!=)|\+=|-=|\*\*=|\*=|/=|%=|<<=|>>>=|>>=|&&=|\|\|=|\?\?=|&=|\|=|\^=)"
)

PRIVATE_FIELD_UPDATE_POSTFIX_PATTERN = re.compile(
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)\s*(?P<op>\+\+|--)"
)

PRIVATE_FIELD_UPDATE_PREFIX_PATTERN = re.compile(
    r"(?P<op>\+\+|--)\s*"
    r"(?P<receiver>(?:this|[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*))\."
    r"(?P<field>#[a-zA-Z_$][\w$]*)"
)


def detect_private_field_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect mutation of private class fields: `this.#field = v` and friends.

    Private fields are TC39 stage 4 (shipped in all modern engines). They are
    a JS-level mutation surface that pattern-based detectors must cover. The
    state-management filename allowlist already exempts framework store files,
    so this detector fires for genuine class-body mutations only.
    """
    results: list[Match] = []
    fix_hint = (
        "Private fields are mutable by default. Prefer immutable patterns: "
        "return a new instance from the method that needs to change state, or expose "
        "a `with*` method that constructs a fresh class instance. When mutation is "
        "intentional, mark the file with `@claude-allow-mutation -- <reason>`."
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        for m in PRIVATE_FIELD_ASSIGN_PATTERN.finditer(masked):
            full = m.group(0)
            if "==" in full or "===" in full:
                continue
            results.append(
                _make_match(
                    "private-field.assignment",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "receiver": m.group("receiver") or "",
                        "field": m.group("field") or "",
                        "op": m.group("op") or "=",
                    },
                )
            )
        for m in PRIVATE_FIELD_UPDATE_POSTFIX_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    "private-field.update",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "receiver": m.group("receiver") or "",
                        "field": m.group("field") or "",
                        "op": m.group("op") or "++",
                    },
                )
            )
        for m in PRIVATE_FIELD_UPDATE_PREFIX_PATTERN.finditer(masked):
            results.append(
                _make_match(
                    "private-field.update",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "receiver": m.group("receiver") or "",
                        "field": m.group("field") or "",
                        "op": m.group("op") or "++",
                    },
                )
            )
    return results


SYMBOL_KEY_ASSIGN_PATTERN = re.compile(
    r"(?P<receiver>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*)*)\s*\[\s*"
    r"(?P<key>Symbol\.[a-zA-Z_$][\w$]*|[a-zA-Z_$][\w$]*Symbol|"
    r"[a-zA-Z_$][\w$]*\.[a-zA-Z_$]*[Ss]ymbol[\w$]*)\s*\]\s*(?P<op>=(?!=))"
)


def detect_symbol_key_assignment(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `obj[Symbol.iterator] = fn` and similar Symbol-keyed mutations.

    Well-known Symbol assignments (Symbol.iterator, Symbol.asyncIterator,
    Symbol.toPrimitive, Symbol.toStringTag, etc.) and user-defined Symbols
    are tracked. The fix hint shows the equivalent fresh-object construction.
    """
    results: list[Match] = []
    fix_hint = (
        "Symbol-keyed property assignment mutates the receiver. Build a fresh object "
        "with the symbol in the literal: `{ ...obj, [Symbol.iterator]: fn }`. For "
        "classes, declare the symbol property in the class body or in a factory."
    )
    for lineno, raw, masked in _iter_lines(text):
        if _looks_like_declaration(raw, masked):
            continue
        for m in SYMBOL_KEY_ASSIGN_PATTERN.finditer(masked):
            full = m.group(0)
            if "==" in full or "===" in full:
                continue
            receiver = m.group("receiver") or ""
            if is_dom_receiver(receiver):
                continue
            results.append(
                _make_match(
                    "symbol-key.assignment",
                    lineno,
                    m.start(),
                    raw,
                    fix_hint,
                    {
                        "receiver": receiver,
                        "key": (m.group("key") or "").strip(),
                    },
                )
            )
    return results


STATIC_BLOCK_OPEN_PATTERN = re.compile(r"\bstatic\s*\{")


def canonical_static_block_line_ranges(text: str) -> list[tuple[int, int]]:
    """Return inclusive 1-based line ranges for canonical class `static {}` blocks.

    A canonical block is a single static block per class with no conditional
    branching. Property mutation inside such a block is one-time class
    initialization, equivalent to constructor body, and should be auto-allowed.
    The static block detector still flags branching or multiple blocks; those
    ranges are excluded from this list.
    """
    lines = text.splitlines()
    ranges: list[tuple[int, int]] = []
    in_block = False
    depth = 0
    start = 0
    branched = False
    class_depth = 0
    class_block_seen = 0
    pending: list[tuple[int, int, bool, int]] = []
    for idx, raw in enumerate(lines, start=1):
        masked = strip_strings_comments(raw)
        if re.search(r"\bclass\s+[A-Z][\w$]*", masked):
            class_depth = class_depth + 1
            class_block_seen = 0
        if not in_block and STATIC_BLOCK_OPEN_PATTERN.search(masked):
            in_block = True
            depth = masked.count("{") - masked.count("}")
            start = idx
            branched = False
            class_block_seen = class_block_seen + 1
            continue
        if in_block:
            depth = depth + masked.count("{") - masked.count("}")
            if re.search(r"\b(if|else|switch|for|while|try|catch)\b", masked):
                branched = True
            if depth <= 0:
                pending.append((start, idx, branched, class_block_seen))
                in_block = False
                depth = 0
    canonical_counts: dict[int, int] = {}
    for _, _, _, count in pending:
        canonical_counts[count] = canonical_counts.get(count, 0) + 1
    for start_l, end_l, branched_flag, seen_count in pending:
        if branched_flag:
            continue
        if seen_count != 1:
            continue
        ranges.append((start_l, end_l))
    return ranges


def filter_matches_in_canonical_static_blocks(
    matches: list[Match], text: str
) -> list[Match]:
    """Drop property/compound/increment matches inside canonical static blocks.

    The `static-block.mutation` detector itself is kept regardless; only the
    line-scoped property/compound/increment/computed matches are filtered out,
    because canonical static initializers are an auto-allowed scope.
    """
    ranges = canonical_static_block_line_ranges(text)
    if not ranges:
        return matches
    filtered_detectors = {
        "property.assignment",
        "property.computed",
        "property.compound",
        "property.compound-index",
        "property.increment",
        "property.increment-prefix",
        "delete-operator",
        "object.assign",
        "reflect.set",
        "reflect.setPrototypeOf",
    }
    result: list[Match] = []
    for m in matches:
        if m.detector in filtered_detectors:
            inside = any(start <= m.line <= end for start, end in ranges)
            if inside:
                continue
        result.append(m)
    return result


def detect_static_block_mutation(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect mutation inside class `static { ... }` blocks beyond canonical init.

    The canonical static block pattern is a single block with sequential
    assignments and no conditional branching, used for one-time class
    initialization. Multiple static blocks or branching inside a block are
    flagged: those patterns suggest the static initializer is doing more
    than declarative setup.
    """
    results: list[Match] = []
    fix_hint = (
        "Class `static {}` blocks should perform one-time initialization in a single "
        "sequential block. If the logic needs branching, extract a factory function "
        "and assign its result to a static class field. Multiple static blocks per "
        "class are flagged."
    )
    lines = text.splitlines()
    in_static_block = False
    block_depth = 0
    block_start_line = 0
    block_has_branch = False
    block_count_by_class: list[int] = []
    class_depth = 0
    class_block_count = 0
    for idx, raw in enumerate(lines, start=1):
        masked = strip_strings_comments(raw)
        if re.search(r"\bclass\s+[A-Z][\w$]*", masked):
            class_depth = class_depth + 1
            class_block_count = 0
        if not in_static_block and STATIC_BLOCK_OPEN_PATTERN.search(masked):
            in_static_block = True
            block_depth = masked.count("{") - masked.count("}")
            block_start_line = idx
            block_has_branch = False
            class_block_count = class_block_count + 1
            continue
        if in_static_block:
            block_depth = block_depth + masked.count("{") - masked.count("}")
            if re.search(r"\b(if|else|switch|for|while|try|catch)\b", masked):
                block_has_branch = True
            if block_depth <= 0:
                if block_has_branch or class_block_count > 1:
                    excerpt = (
                        lines[block_start_line - 1]
                        if block_start_line - 1 < len(lines)
                        else ""
                    )
                    results.append(
                        _make_match(
                            "static-block.mutation",
                            block_start_line,
                            0,
                            excerpt,
                            fix_hint,
                            {
                                "reason": "branching inside static block"
                                if block_has_branch
                                else "multiple static blocks per class",
                            },
                        )
                    )
                in_static_block = False
                block_depth = 0
        if "}" in masked and class_depth > 0 and not in_static_block:
            block_count_by_class.append(class_block_count)
    return results


SVELTE_DERIVED_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*\$derived\s*[(<]"
)


def detect_svelte_derived_reassign(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect reassignment of a binding declared via Svelte 5 `$derived(...)`.

    `$derived` returns a read-only reactive value. The runtime throws a
    `state_unsafe_mutation` error when a derived binding is reassigned, but
    the static signal here catches the bug at write-time. The declaration
    site itself is excluded.
    """
    derived_names = {
        m.group("name") for m in SVELTE_DERIVED_DECL_PATTERN.finditer(text)
    }
    if not derived_names:
        return []
    fix_hint = (
        "`$derived(...)` bindings are read-only. Reassigning them throws "
        "`state_unsafe_mutation` at runtime. Move the source of truth into a "
        "`$state(...)` binding and let `$derived` recompute, or wrap the "
        "computation in a function. See "
        "https://svelte.dev/docs/svelte/$derived for the reactive contract."
    )
    pattern = re.compile(
        r"^(?P<lead>\s*)(?P<name>"
        + "|".join(re.escape(n) for n in derived_names)
        + r")\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if SVELTE_DERIVED_DECL_PATTERN.search(masked):
            continue
        m = pattern.match(masked)
        if not m:
            continue
        name = m.group("name")
        results.append(
            _make_match(
                "svelte.derived-reassign",
                lineno,
                m.start("name"),
                raw,
                fix_hint,
                {"name": name, "confidence": "4"},
            )
        )
    return results


XSTATE_CONTEXT_ASSIGN_PATTERN = re.compile(
    r"(?<![\w$.])context\."
    r"(?P<chain>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])*)"
    r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
)
XSTATE_ASSIGN_OPENER_PATTERN = re.compile(r"\bassign\s*\(")


def detect_xstate_non_assign_context_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect `context.x = v` writes outside an `assign(...)` callback.

    XState v5 enforces `assign(...)` as the only context mutation
    primitive. Writing directly to `context` from a non-assign action
    callback silently no-ops because the action receives an immutable
    snapshot. The detector scans lines containing `context.<x> =` and
    walks back to verify the hit sits inside an unmatched `assign(`
    brace scope. Plain `assign` opener lines are skipped because the
    callback's parameter destructuring rebinds `context` to a draft.
    """
    if "xstate" not in text:
        return []
    if not re.search(r"['\"]xstate(?:/[\w/-]+)?['\"]", text):
        return []
    if "context." not in text:
        return []
    lines = text.splitlines()
    if not lines:
        return []
    fix_hint = (
        "XState v5 enforces `assign(...)` as the only context mutation "
        "primitive. Direct writes like `context.x = v` from a non-assign "
        "action silently no-op because the callback receives an immutable "
        "snapshot. Wrap the update in `assign({ x: ({ context }) => v })` "
        "or `assign(({ context }) => ({ x: v }))`. See "
        "https://stately.ai/docs/actions#assign-action."
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        m = XSTATE_CONTEXT_ASSIGN_PATTERN.search(masked)
        if not m:
            continue
        lookback_start = max(0, lineno - 61)
        between_lines = lines[lookback_start : lineno]
        between = "\n".join(between_lines)
        between_masked = strip_strings_comments(between) if between else ""
        inside_assign = False
        if between_masked:
            last_assign = between_masked.rfind("assign(")
            if last_assign >= 0:
                scope_text = between_masked[last_assign:]
                paren_opens = scope_text.count("(")
                paren_closes = scope_text.count(")")
                if paren_opens > paren_closes:
                    inside_assign = True
        if inside_assign:
            continue
        results.append(
            _make_match(
                "xstate.non-assign-context-write",
                lineno,
                m.start(),
                raw,
                fix_hint,
                {"chain": m.group("chain"), "confidence": "3"},
            )
        )
    return results


EFFECT_TS_REF_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*"
    r"(?:yield\*?\s+)?"
    r"(?:Ref|SubscriptionRef|SynchronizedRef)\.make\s*\("
)


def detect_effect_ts_ref_value_assign(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect bare `ref.value = v` writes on Effect-TS Ref bindings.

    Effect-TS Refs are opaque handles. They have no `.value` property.
    Updates flow through `Ref.update`, `Ref.set`, `Ref.modify`, or their
    SubscriptionRef / SynchronizedRef siblings, and must be `yield*`-ed
    inside an `Effect.gen` generator. Writing `ref.value = v` is the
    Vue/Preact-signals pattern leaking into an Effect-TS codebase. The
    detector is import-gated on the Effect-TS package family.
    """
    if "effect" not in text:
        return []
    if not re.search(
        r"['\"](?:effect|@effect/(?:io|core|data|stm)(?:/[\w/-]+)?)['\"]", text
    ):
        return []
    names = {m.group("name") for m in EFFECT_TS_REF_DECL_PATTERN.finditer(text)}
    if not names:
        return []
    fix_hint = (
        "Effect-TS Ref bindings have no `.value` property. Updates go "
        "through `Ref.update`, `Ref.set`, or `Ref.modify` and must be "
        "`yield*`-ed inside an `Effect.gen` generator: "
        "`yield* Ref.set(ref, next)`. See "
        "https://effect.website/docs/state-management/ref."
    )
    name_alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alt + r")\.value"
        r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if EFFECT_TS_REF_DECL_PATTERN.search(masked):
            continue
        for m in pattern.finditer(masked):
            results.append(
                _make_match(
                    "effect-ts.ref-value-assign",
                    lineno,
                    m.start("name"),
                    raw,
                    fix_hint,
                    {"name": m.group("name"), "confidence": "4"},
                )
            )
    return results


NANOSTORES_COMPUTED_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*computed\s*\("
)


def detect_nanostores_computed_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect mutating calls against a Nanostores computed binding.

    Nanostores computed stores expose only read methods (subscribe,
    listen, plus the read accessor). Calling write methods on a computed
    binding bypasses the recompute contract and silently desynchronizes
    downstream subscribers.
    """
    if "nanostores" not in text:
        return []
    if not re.search(r"['\"]nanostores(?:/[\w/-]+)?['\"]", text):
        return []
    names = {
        m.group("name") for m in NANOSTORES_COMPUTED_DECL_PATTERN.finditer(text)
    }
    if not names:
        return []
    fix_hint = (
        "Nanostores computed stores are read-only derived values. Only the "
        "read accessors and subscription methods are public. Mutating "
        "methods such as setKey or the value setter bypass the recompute "
        "contract. Move the source-of-truth into an atom or map binding "
        "and let computed recompute. See "
        "https://github.com/nanostores/nanostores#computed-stores."
    )
    name_alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alt + r")\."
        r"(?P<method>set|setKey|notify)\s*\("
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if NANOSTORES_COMPUTED_DECL_PATTERN.search(masked):
            continue
        for m in pattern.finditer(masked):
            results.append(
                _make_match(
                    "nanostores.computed-write",
                    lineno,
                    m.start("name"),
                    raw,
                    fix_hint,
                    {
                        "name": m.group("name"),
                        "method": m.group("method"),
                        "confidence": "4",
                    },
                )
            )
    return results


TANSTACK_STORE_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*"
    r"(?:new\s+Store\s*\(|createStore\s*\()"
)


def detect_tanstack_store_state_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect direct writes against a TanStack `Store.state` property.

    TanStack Store exposes `store.state` as a read-only snapshot. Updates
    must go through `store.setState((prev) => next)`. Direct mutation like
    `store.state.count = 1` silently bypasses subscribers and breaks
    reactivity. The detector is import-gated to avoid false positives on
    unrelated `store.state` shapes.
    """
    if "@tanstack/" not in text:
        return []
    if not re.search(r"['\"]@tanstack/(?:store|react-store|solid-store)['\"]", text):
        return []
    names = {m.group("name") for m in TANSTACK_STORE_DECL_PATTERN.finditer(text)}
    if not names:
        return []
    fix_hint = (
        "TanStack `Store.state` is a read-only snapshot. Direct writes "
        "(`store.state.x = v`) bypass subscribers and break reactivity. "
        "Use `store.setState((prev) => ({ ...prev, x: v }))` so the "
        "subscription system observes the change. See "
        "https://tanstack.com/store/latest/docs/reference/store#setstate."
    )
    name_alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alt + r")\.state"
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])*)"
        r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if TANSTACK_STORE_DECL_PATTERN.search(masked):
            continue
        for m in pattern.finditer(masked):
            results.append(
                _make_match(
                    "tanstack.store-state-write",
                    lineno,
                    m.start("name"),
                    raw,
                    fix_hint,
                    {
                        "name": m.group("name"),
                        "chain": m.group("chain"),
                        "confidence": "4",
                    },
                )
            )
    return results


VUE_SHALLOW_READONLY_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*shallowReadonly\s*\("
)


def detect_vue_shallow_readonly_nested_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect nested property writes against a Vue `shallowReadonly(...)` binding.

    `shallowReadonly(obj)` freezes only the top level. `x.foo = v` triggers a
    runtime warning, but `x.foo.bar = v` silently mutates the underlying
    reactive object, defeating the contract. This detector fires on chains
    of two or more property accesses ending in an assignment.
    """
    names = {
        m.group("name") for m in VUE_SHALLOW_READONLY_DECL_PATTERN.finditer(text)
    }
    if not names:
        return []
    fix_hint = (
        "`shallowReadonly(obj)` only freezes the top level. Nested writes "
        "(`x.a.b = v`) silently mutate the underlying reactive object. Use "
        "`readonly(obj)` for deep immutability, or rebuild the nested branch "
        "with spread (`{ ...x, a: { ...x.a, b: v } }`) and assign the result "
        "to a fresh ref. See https://vuejs.org/api/reactivity-advanced.html#shallowreadonly"
    )
    name_alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alt + r")"
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])+)"
        r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if VUE_SHALLOW_READONLY_DECL_PATTERN.search(masked):
            continue
        for m in pattern.finditer(masked):
            chain = m.group("chain")
            access_count = chain.count(".") + chain.count("[")
            if access_count < 2:
                continue
            results.append(
                _make_match(
                    "vue.shallow-readonly-nested-write",
                    lineno,
                    m.start("name"),
                    raw,
                    fix_hint,
                    {
                        "name": m.group("name"),
                        "chain": chain,
                        "confidence": "4",
                    },
                )
            )
    return results


RECOIL_IMPORT_LINE_PATTERN = re.compile(
    r"^\s*import\b[^;]*\bfrom\s+['\"]recoil['\"]"
)


def detect_recoil_deprecation_pointer(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Emit an info-level pointer when a file imports from `recoil`.

    Recoil's last release shipped in early 2024 and Meta confirmed the
    project is unmaintained. New code should migrate to Jotai, Zustand,
    or Nanostores. The detector fires once at the first `from 'recoil'`
    import line and emits an info-severity finding so authors get a
    migration nudge without blocking the write.
    """
    if "recoil" not in text:
        return []
    fix_hint = (
        "Recoil is unmaintained as of 2024. Migrate to Jotai (atom-based, "
        "closest API), Zustand (store-based with simpler boilerplate), or "
        "Nanostores (tiny, framework-agnostic). See "
        "https://github.com/facebookexperimental/Recoil/issues for context "
        "and https://jotai.org/docs/migrations/from-recoil for a "
        "Recoil-to-Jotai mapping."
    )
    for lineno, raw, _masked in _iter_lines(text):
        if RECOIL_IMPORT_LINE_PATTERN.match(raw):
            return [
                _make_match(
                    "recoil.deprecation-pointer",
                    lineno,
                    0,
                    raw,
                    fix_hint,
                    {"confidence": "1", "severity": "info"},
                )
            ]
    return []


MOBX_ENFORCE_ACTIONS_PATTERN = re.compile(
    r"enforceActions\s*:\s*['\"]always['\"]"
)
MOBX_OBSERVABLE_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
    r"(?::\s*[^=]+)?\s*=\s*"
    r"(?:observable|makeAutoObservable|makeObservable)\s*\("
)


def detect_mobx_observable_outside_action(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    """Detect MobX observable property writes outside an action scope
    when `enforceActions: 'always'` is configured.

    MobX strict mode requires every observable mutation to happen inside
    `runInAction`, `action`, or a `flow` generator. With strict mode
    enabled, a plain `store.count = 1` throws at runtime instead of
    updating state. The detector activates only when the file or its
    config sets `enforceActions: 'always'`, collects observable bindings
    declared via `observable`, `makeAutoObservable`, or `makeObservable`,
    and flags property writes on those bindings that sit outside an
    unmatched `runInAction(` / `action(` / `flow(` paren scope.
    """
    if "mobx" not in text:
        return []
    if not re.search(r"['\"]mobx(?:-[\w/-]+)?['\"]", text):
        return []
    if not MOBX_ENFORCE_ACTIONS_PATTERN.search(text):
        return []
    names = {m.group("name") for m in MOBX_OBSERVABLE_DECL_PATTERN.finditer(text)}
    if not names:
        return []
    lines = text.splitlines()
    if not lines:
        return []
    fix_hint = (
        "MobX strict mode (`enforceActions: 'always'`) requires every "
        "observable mutation to flow through an action. Wrap the write in "
        "`runInAction(() => { store.count = 1 })` or call an `action`-decorated "
        "method. See "
        "https://mobx.js.org/configuration.html#enforceactions for the strict "
        "mode contract."
    )
    name_alt = "|".join(re.escape(n) for n in names)
    pattern = re.compile(
        r"(?<![\w$.])(?P<name>" + name_alt + r")"
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])+)"
        r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=|\+\+|--)"
    )
    results: list[Match] = []
    for lineno, raw, masked in _iter_lines(text):
        if MOBX_OBSERVABLE_DECL_PATTERN.search(masked):
            continue
        for m in pattern.finditer(masked):
            lookback_start = max(0, lineno - 61)
            between_lines = lines[lookback_start : lineno]
            between = "\n".join(between_lines)
            between_masked = strip_strings_comments(between) if between else ""
            inside_action = False
            if between_masked:
                for opener in ("runInAction(", "action(", "flow("):
                    idx = between_masked.rfind(opener)
                    if idx < 0:
                        continue
                    scope_text = between_masked[idx:]
                    opens = scope_text.count("(")
                    closes = scope_text.count(")")
                    if opens > closes:
                        inside_action = True
                        break
            if inside_action:
                continue
            results.append(
                _make_match(
                    "mobx.observable-outside-action",
                    lineno,
                    m.start("name"),
                    raw,
                    fix_hint,
                    {
                        "name": m.group("name"),
                        "chain": m.group("chain"),
                        "confidence": "4",
                    },
                )
            )
    return results

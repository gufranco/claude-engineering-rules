from __future__ import annotations

import re
from collections.abc import Callable

from .mutation_detectors_core import Match
from .mutation_scan_helpers import (
    ASSIGN_OP_ALTERNATION,
    NamedWriteSpec,
    collect_names,
    is_inside_open_call,
    iter_masked_lines,
    make_match,
    masked_lookback,
    name_alternation,
    scan_named_writes,
)

XSTATE_CONTEXT_ASSIGN_PATTERN = re.compile(
    r"(?<![\w$.])context\."
    r"(?P<chain>[a-zA-Z_$][\w$]*(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])*)"
    r"\s*(?P<op>=(?!=)|\+=|-=|\*=|/=|%=|\*\*=|<<=|>>=|>>>=|&=|\|=|\^=|&&=|\|\|=|\?\?=)"
)
XSTATE_ASSIGN_OPENER_PATTERN = re.compile(r"\bassign\s*\(")

YJS_CRDT_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
    r"(?::\s*[^=]+)?\s*=\s*"
    r"(?:new\s+Y\.(?:Array|Map|Text|XmlElement|XmlFragment|XmlText)\s*\(|"
    r"[a-zA-Z_$][\w$]*\.get(?:Map|Array|Text|XmlFragment|XmlElement)\s*\()"
)

YJS_MUTATING_METHODS: tuple[str, ...] = (
    "set",
    "delete",
    "clear",
    "push",
    "unshift",
    "insert",
    "applyDelta",
    "format",
)

MOBX_ENFORCE_ACTIONS_PATTERN = re.compile(r"enforceActions\s*:\s*['\"]always['\"]")
MOBX_OBSERVABLE_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
    r"(?::\s*[^=]+)?\s*=\s*"
    r"(?:observable|makeAutoObservable|makeObservable)\s*\("
)

AUTOMERGE_DOC_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
    r"(?::\s*[^=]+)?\s*=\s*"
    r"(?:await\s+)?Automerge\."
    r"(?:init|from|load|clone|change|emptyChange|applyChanges|merge)\s*\("
)

_XSTATE_IMPORT_PATTERN = re.compile(r"['\"]xstate(?:/[\w/-]+)?['\"]")
_MOBX_IMPORT_PATTERN = re.compile(r"['\"]mobx(?:-[\w/-]+)?['\"]")
_AUTOMERGE_IMPORT_PATTERN = re.compile(r"['\"]@?automerge(?:/[\w-]+)?['\"]")
_MOBX_ACTION_OPENERS = ("runInAction(", "action(", "flow(")
_UPDATE_OP_ALTERNATION = ASSIGN_OP_ALTERNATION + r"|\+\+|--"

_XSTATE_FIX = (
    "XState v5 enforces `assign(...)` as the only context mutation "
    "primitive. Direct writes like `context.x = v` from a non-assign "
    "action silently no-op because the callback receives an immutable "
    "snapshot. Wrap the update in `assign({ x: ({ context }) => v })` "
    "or `assign(({ context }) => ({ x: v }))`. See "
    "https://stately.ai/docs/actions#assign-action."
)
_YJS_FIX = (
    "Yjs CRDT mutations belong inside a transaction. Wrap the write in "
    "`doc.transact(() => { ymap.set(key, value) })` so observers receive "
    "a single consolidated update and remote peers replicate the change "
    "atomically. See "
    "https://docs.yjs.dev/api/transactions for the transaction contract."
)
_MOBX_FIX = (
    "MobX strict mode (`enforceActions: 'always'`) requires every "
    "observable mutation to flow through an action. Wrap the write in "
    "`runInAction(() => { store.count = 1 })` or call an `action`-decorated "
    "method. See "
    "https://mobx.js.org/configuration.html#enforceactions for the strict "
    "mode contract."
)
_AUTOMERGE_FIX = (
    "Automerge documents are frozen outside `Automerge.change`. Wrap the "
    "write in `doc = Automerge.change(doc, draft => { draft.foo = 1 })` "
    "so the mutation flows through the CRDT history and remote peers "
    "replicate the change. See "
    "https://automerge.org/docs/hello/ for the change-callback contract."
)


def _name_method_and_confidence(m: re.Match[str]) -> dict[str, str]:
    return {"name": m.group("name"), "method": m.group("method"), "confidence": "4"}


def _name_chain_and_confidence(m: re.Match[str]) -> dict[str, str]:
    return {"name": m.group("name"), "chain": m.group("chain"), "confidence": "4"}


def _outside_openers(
    lines: list[str], openers: tuple[str, ...]
) -> Callable[[re.Match[str], int], bool]:
    def accepts(_match: re.Match[str], lineno: int) -> bool:
        window = masked_lookback(lines, lineno)
        return not any(is_inside_open_call(window, opener) for opener in openers)

    return accepts


def _named_write_pattern(names: frozenset[str], tail: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w$.])(?P<name>" + name_alternation(names) + r")" + tail)


def _has_xstate_import(text: str) -> bool:
    return "xstate" in text and bool(_XSTATE_IMPORT_PATTERN.search(text))


def detect_xstate_non_assign_context_write(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not _has_xstate_import(text) or "context." not in text:
        return []
    lines = text.splitlines()
    outside_assign = _outside_openers(lines, ("assign(",))
    hits = (
        (lineno, raw, XSTATE_CONTEXT_ASSIGN_PATTERN.search(masked))
        for lineno, raw, masked in iter_masked_lines(text)
    )
    return [
        make_match(
            "xstate.non-assign-context-write",
            lineno,
            m.start(),
            raw,
            _XSTATE_FIX,
            {"chain": m.group("chain"), "confidence": "3"},
        )
        for lineno, raw, m in hits
        if m and outside_assign(m, lineno)
    ]


def detect_yjs_mutation_outside_transact(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if "yjs" not in text and "Y." not in text:
        return []
    names = collect_names(YJS_CRDT_DECL_PATTERN, text)
    if not names:
        return []
    lines = text.splitlines()
    tail = r"\.(?P<method>" + name_alternation(YJS_MUTATING_METHODS) + r")\s*\("
    spec = NamedWriteSpec(
        detector="yjs.mutation-outside-transact",
        pattern=_named_write_pattern(names, tail),
        skip_line=YJS_CRDT_DECL_PATTERN,
        fix_hint=_YJS_FIX,
        metadata=_name_method_and_confidence,
        accepts=_outside_openers(lines, (".transact(",)),
    )
    return scan_named_writes(text, spec)


def _mobx_strict_mode(text: str) -> bool:
    return (
        "mobx" in text
        and bool(_MOBX_IMPORT_PATTERN.search(text))
        and bool(MOBX_ENFORCE_ACTIONS_PATTERN.search(text))
    )


def detect_mobx_observable_outside_action(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not _mobx_strict_mode(text):
        return []
    names = collect_names(MOBX_OBSERVABLE_DECL_PATTERN, text)
    if not names:
        return []
    lines = text.splitlines()
    tail = (
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])+)"
        r"\s*(?P<op>" + _UPDATE_OP_ALTERNATION + r")"
    )
    spec = NamedWriteSpec(
        detector="mobx.observable-outside-action",
        pattern=_named_write_pattern(names, tail),
        skip_line=MOBX_OBSERVABLE_DECL_PATTERN,
        fix_hint=_MOBX_FIX,
        metadata=_name_chain_and_confidence,
        accepts=_outside_openers(lines, _MOBX_ACTION_OPENERS),
    )
    return scan_named_writes(text, spec)


def _has_automerge_import(text: str) -> bool:
    mentioned = "Automerge" in text or "automerge" in text
    return mentioned and bool(_AUTOMERGE_IMPORT_PATTERN.search(text))


def detect_automerge_direct_mutation(
    text: str, lang: str | None, file_path: str
) -> list[Match]:
    if not _has_automerge_import(text):
        return []
    names = collect_names(AUTOMERGE_DOC_DECL_PATTERN, text)
    if not names:
        return []
    tail = (
        r"(?P<chain>(?:\.[a-zA-Z_$][\w$]*|\[[^\]]+\])+)"
        r"\s*(?P<op>" + _UPDATE_OP_ALTERNATION + r")"
    )
    spec = NamedWriteSpec(
        detector="automerge.direct-mutation",
        pattern=_named_write_pattern(names, tail),
        skip_line=AUTOMERGE_DOC_DECL_PATTERN,
        fix_hint=_AUTOMERGE_FIX,
        metadata=_name_chain_and_confidence,
    )
    return scan_named_writes(text, spec)

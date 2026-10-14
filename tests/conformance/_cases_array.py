from __future__ import annotations

from _case_model import Case, allow, block

ARRAY_MUTATORS = (
    ("push", "items.push(1)"),
    ("pop", "items.pop()"),
    ("shift", "items.shift()"),
    ("unshift", "items.unshift(0)"),
    ("splice", "items.splice(0, 1)"),
    ("sort", "items.sort()"),
    ("reverse", "items.reverse()"),
    ("fill", "items.fill(0)"),
    ("copyWithin", "items.copyWithin(0, 1)"),
)

ARRAY_NON_MUTATING = (
    ("toSorted", "items.toSorted()"),
    ("toReversed", "items.toReversed()"),
    ("toSpliced", "items.toSpliced(0, 1)"),
    ("with", "items.with(0, 99)"),
    ("map", "items.map((x) => x * 2)"),
    ("filter", "items.filter((x) => x > 0)"),
    ("reduce", "items.reduce((a, b) => a + b, 0)"),
    ("flatMap", "items.flatMap((x) => [x, x])"),
)

ARRAY_LOOKALIKE_RECEIVERS = (
    ("router-push", "router.push", "router.push('/home')\n"),
    ("history-push", "history.push", "history.push('/dashboard')\n"),
    ("navigation-push", "navigation.push", "navigation.push('/page')\n"),
    ("stream-push", "stream.push", "stream.push(chunk)\n"),
    ("subject-next", "subject.next", "subject.next(value)\n"),
)

ARRAY_CASES: tuple[Case, ...] = (
    *(
        block(
            "array/",
            f"{method}-blocks",
            f"array.{method} blocks",
            "array.",
            "edit",
            f"const items = [1, 2, 3]\n{snippet}\n",
        )
        for method, snippet in ARRAY_MUTATORS
    ),
    *(
        allow(
            "array/",
            f"{method}-allows",
            f"array.{method} allows",
            "write",
            f"const items = [1, 2, 3]\nconst out = {snippet}\n",
        )
        for method, snippet in ARRAY_NON_MUTATING
    ),
    allow(
        "array/",
        "spread-allows",
        "spread append allows",
        "write",
        "const items = [1, 2, 3]\nconst out = [...items, 4]\n",
    ),
    *(
        allow("array/", f"{label}-allows", f"{name} allows", "edit", body)
        for label, name, body in ARRAY_LOOKALIKE_RECEIVERS
    ),
    block(
        "array/",
        "bracket-push-blocks",
        "items['push'] dispatch blocks",
        "array.bracket-dispatch",
        "edit",
        "const items = [1]\nitems['push'](2)\n",
    ),
    block(
        "array/",
        "bracket-sort-blocks",
        "items['sort'] dispatch blocks",
        "array.bracket-dispatch",
        "edit",
        'const items = [3, 1, 2]\nitems["sort"]()\n',
    ),
)

COLLECTION_MUTATORS = (
    ("Map", "set", "m", "m.set('k', 1)"),
    ("Map", "delete", "m", "m.delete('k')"),
    ("Map", "clear", "m", "m.clear()"),
    ("Set", "add", "s", "s.add(1)"),
    ("Set", "delete", "s", "s.delete(1)"),
    ("Set", "clear", "s", "s.clear()"),
    ("WeakMap", "set", "wm", "wm.set(obj, 1)"),
    ("WeakMap", "delete", "wm", "wm.delete(obj)"),
    ("WeakSet", "add", "ws", "ws.add(obj)"),
    ("WeakSet", "delete", "ws", "ws.delete(obj)"),
)

SET_ES2024_NON_MUTATING = (
    ("union", "a.union(b)"),
    ("intersection", "a.intersection(b)"),
    ("difference", "a.difference(b)"),
    ("symmetricDifference", "a.symmetricDifference(b)"),
    ("isSubsetOf", "a.isSubsetOf(b)"),
    ("isSupersetOf", "a.isSupersetOf(b)"),
    ("isDisjointFrom", "a.isDisjointFrom(b)"),
)

COLLECTION_CASES: tuple[Case, ...] = (
    *(
        block(
            "collection/",
            f"{kind.lower()}-{method}-blocks",
            f"{kind}.{method} blocks",
            "collection.",
            "edit",
            f"const obj = {{}}\nconst {receiver} = new {kind}()\n{snippet}\n",
        )
        for kind, method, receiver, snippet in COLLECTION_MUTATORS
    ),
    *(
        allow(
            "collection/",
            f"set-{method.lower()}-allows",
            f"Set.{method} allows",
            "write",
            f"const a = new Set([1, 2])\nconst b = new Set([2, 3])\nconst out = {snippet}\n",
        )
        for method, snippet in SET_ES2024_NON_MUTATING
    ),
    allow(
        "collection/",
        "new-map-spread-allows",
        "new Map with spread allows",
        "write",
        "const a = new Map([['x', 1]])\nconst b = new Map([...a, ['y', 2]])\n",
    ),
    allow(
        "collection/",
        "new-set-spread-allows",
        "new Set with spread allows",
        "write",
        "const a = new Set([1, 2])\nconst b = new Set([...a, 3])\n",
    ),
)

TYPED_ARRAY_METHOD_ARGS = (
    ("set", "[1, 2]"),
    ("fill", "0"),
    ("sort", ""),
    ("reverse", ""),
    ("copyWithin", "0"),
)

TYPED_ARRAY_CASES: tuple[Case, ...] = (
    *(
        block(
            "array/typed_",
            f"uint8-{method}-blocks",
            f"Uint8Array.{method} blocks in business scope",
            "typed-array.",
            "edit",
            f"const buf = new Uint8Array(4)\nbuf.{method}({arg})\n",
            "/repo/src/business/data.ts",
        )
        for method, arg in TYPED_ARRAY_METHOD_ARGS
    ),
    *(
        allow(
            "array/typed_",
            f"uint8-{method}-hot-allows",
            f"Uint8Array.{method} allows in crypto hot path",
            "edit",
            f"const buf = new Uint8Array(4)\nbuf.{method}({arg})\n",
            "/repo/src/crypto/hash.ts",
        )
        for method, arg in TYPED_ARRAY_METHOD_ARGS
    ),
)

EXTRA_PUSH_ARGS = ("1", "1, 2", "1, 2, 3", "...rest", "x")

EXTRA_SPLICE_ARGS = ("", "0, 1", "1, 2, 'a'", "0, 0, 'x', 'y'")

EXTRA_ARRAY_CASES: tuple[Case, ...] = (
    *(
        block(
            "array/extra_push_",
            "args-blocks",
            f"items.push({arg}) blocks",
            "array.",
            "edit",
            f"const items: any[] = []\nconst rest = [9, 9]\nconst x = 7\nitems.push({arg})\n",
        )
        for arg in EXTRA_PUSH_ARGS
    ),
    *(
        block(
            "array/extra_splice_",
            "args-blocks",
            f"items.splice({arg}) blocks",
            "array.",
            "edit",
            f"const items = [1, 2, 3]\nitems.splice({arg})\n",
        )
        for arg in EXTRA_SPLICE_ARGS
    ),
)

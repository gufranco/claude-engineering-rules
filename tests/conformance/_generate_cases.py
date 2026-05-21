"""Generator for mutation-method-blocker conformance cases (plan item 386).

Run once to populate `tests/conformance/cases/`. Idempotent: re-running
overwrites existing files. Generated cases cover >=200 scenarios across
all detector categories.
"""

from __future__ import annotations

import os
import textwrap

BASE = os.path.join(os.path.dirname(__file__), "cases")


def write_case(path: str, frontmatter: dict[str, str], body: str) -> None:
    """Write one case file with `---` YAML frontmatter and body."""
    target = os.path.join(BASE, path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    lines = ["---"]
    for k, v in frontmatter.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append(body)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def gen_array_cases() -> int:
    """Array prototype mutation cases."""
    n = 0
    methods_block = [
        ("push", "items.push(1)"),
        ("pop", "items.pop()"),
        ("shift", "items.shift()"),
        ("unshift", "items.unshift(0)"),
        ("splice", "items.splice(0, 1)"),
        ("sort", "items.sort()"),
        ("reverse", "items.reverse()"),
        ("fill", "items.fill(0)"),
        ("copyWithin", "items.copyWithin(0, 1)"),
    ]
    for method, snippet in methods_block:
        n += 1
        body = f"const items = [1, 2, 3]\n{snippet}\n"
        write_case(
            f"array/{n:03d}-{method}-blocks.test.ts",
            {
                "description": f"array.{method} blocks",
                "verdict": "block",
                "detector": "array.",
                "payload": "edit",
            },
            body,
        )
    non_mutating = [
        ("toSorted", "items.toSorted()"),
        ("toReversed", "items.toReversed()"),
        ("toSpliced", "items.toSpliced(0, 1)"),
        ("with", "items.with(0, 99)"),
        ("map", "items.map((x) => x * 2)"),
        ("filter", "items.filter((x) => x > 0)"),
        ("reduce", "items.reduce((a, b) => a + b, 0)"),
        ("flatMap", "items.flatMap((x) => [x, x])"),
    ]
    for method, snippet in non_mutating:
        n += 1
        body = f"const items = [1, 2, 3]\nconst out = {snippet}\n"
        write_case(
            f"array/{n:03d}-{method}-allows.test.ts",
            {
                "description": f"array.{method} allows",
                "verdict": "allow",
                "payload": "write",
            },
            body,
        )
    n += 1
    write_case(
        f"array/{n:03d}-spread-allows.test.ts",
        {
            "description": "spread append allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const items = [1, 2, 3]\nconst out = [...items, 4]\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-router-push-allows.test.ts",
        {
            "description": "router.push allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "router.push('/home')\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-history-push-allows.test.ts",
        {
            "description": "history.push allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "history.push('/dashboard')\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-navigation-push-allows.test.ts",
        {
            "description": "navigation.push allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "navigation.push('/page')\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-stream-push-allows.test.ts",
        {
            "description": "stream.push allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "stream.push(chunk)\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-subject-next-allows.test.ts",
        {
            "description": "subject.next allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "subject.next(value)\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-bracket-push-blocks.test.ts",
        {
            "description": "items['push'] dispatch blocks",
            "verdict": "block",
            "detector": "array.bracket-dispatch",
            "payload": "edit",
        },
        "const items = [1]\nitems['push'](2)\n",
    )
    n += 1
    write_case(
        f"array/{n:03d}-bracket-sort-blocks.test.ts",
        {
            "description": "items['sort'] dispatch blocks",
            "verdict": "block",
            "detector": "array.bracket-dispatch",
            "payload": "edit",
        },
        'const items = [3, 1, 2]\nitems["sort"]()\n',
    )
    return n


def gen_collection_cases() -> int:
    """Map/Set/WeakMap/WeakSet mutation cases."""
    n = 0
    mutating = [
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
    ]
    for kind, method, receiver, snippet in mutating:
        n += 1
        body = f"const obj = {{}}\nconst {receiver} = new {kind}()\n{snippet}\n"
        write_case(
            f"collection/{n:03d}-{kind.lower()}-{method}-blocks.test.ts",
            {
                "description": f"{kind}.{method} blocks",
                "verdict": "block",
                "detector": "collection.",
                "payload": "edit",
            },
            body,
        )
    es2024_non_mutating = [
        ("union", "a.union(b)"),
        ("intersection", "a.intersection(b)"),
        ("difference", "a.difference(b)"),
        ("symmetricDifference", "a.symmetricDifference(b)"),
        ("isSubsetOf", "a.isSubsetOf(b)"),
        ("isSupersetOf", "a.isSupersetOf(b)"),
        ("isDisjointFrom", "a.isDisjointFrom(b)"),
    ]
    for method, snippet in es2024_non_mutating:
        n += 1
        body = f"const a = new Set([1, 2])\nconst b = new Set([2, 3])\nconst out = {snippet}\n"
        write_case(
            f"collection/{n:03d}-set-{method.lower()}-allows.test.ts",
            {
                "description": f"Set.{method} allows",
                "verdict": "allow",
                "payload": "write",
            },
            body,
        )
    n += 1
    write_case(
        f"collection/{n:03d}-new-map-spread-allows.test.ts",
        {
            "description": "new Map with spread allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const a = new Map([['x', 1]])\nconst b = new Map([...a, ['y', 2]])\n",
    )
    n += 1
    write_case(
        f"collection/{n:03d}-new-set-spread-allows.test.ts",
        {
            "description": "new Set with spread allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const a = new Set([1, 2])\nconst b = new Set([...a, 3])\n",
    )
    return n


def gen_property_cases() -> int:
    """Direct property/computed/compound/increment assignment cases."""
    n = 0
    cases = [
        ("property", "obj.x = 1", "property.assignment"),
        ("computed", "obj['x'] = 1", "property.computed"),
        ("compound-add", "obj.x += 1", "property.compound"),
        ("compound-sub", "obj.x -= 1", "property.compound"),
        ("compound-mul", "obj.x *= 2", "property.compound"),
        ("compound-div", "obj.x /= 2", "property.compound"),
        ("compound-mod", "obj.x %= 3", "property.compound"),
        ("compound-pow", "obj.x **= 2", "property.compound"),
        ("compound-and", "obj.x &= 1", "property.compound"),
        ("compound-or", "obj.x |= 1", "property.compound"),
        ("compound-xor", "obj.x ^= 1", "property.compound"),
        ("compound-shl", "obj.x <<= 1", "property.compound"),
        ("compound-shr", "obj.x >>= 1", "property.compound"),
        ("compound-shru", "obj.x >>>= 1", "property.compound"),
        ("compound-nullish", "obj.x ??= 1", "property.compound"),
        ("compound-and-and", "obj.x &&= 1", "property.compound"),
        ("compound-or-or", "obj.x ||= 1", "property.compound"),
        ("postfix-inc", "obj.x++", "property.increment"),
        ("postfix-dec", "obj.x--", "property.increment"),
        ("prefix-inc", "++obj.x", "property.increment"),
        ("prefix-dec", "--obj.x", "property.increment"),
        ("delete-prop", "delete obj.x", "delete-operator"),
        ("delete-computed", "delete obj['x']", "delete-operator"),
        ("array-index", "arr[0] = 1", "property.computed"),
    ]
    for label, snippet, detector in cases:
        n += 1
        body = f"const obj: any = {{ x: 0 }}\nconst arr = [1, 2, 3]\n{snippet}\n"
        write_case(
            f"property/{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{label} blocks",
                "verdict": "block",
                "detector": detector,
                "payload": "edit",
            },
            body,
        )
    n += 1
    write_case(
        f"property/{n:03d}-spread-update-allows.test.ts",
        {
            "description": "spread-update pattern allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const obj = { x: 0 }\nconst next = { ...obj, x: 1 }\n",
    )
    n += 1
    write_case(
        f"property/{n:03d}-with-allows.test.ts",
        {
            "description": "arr.with(i, v) allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const arr = [1, 2, 3]\nconst next = arr.with(0, 99)\n",
    )
    n += 1
    write_case(
        f"property/{n:03d}-rest-omit-allows.test.ts",
        {
            "description": "rest-omit pattern allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const obj = { x: 1, y: 2 }\nconst { x, ...rest } = obj\n",
    )
    return n


def gen_date_cases() -> int:
    """Date setter mutation cases."""
    n = 0
    setters = [
        "setDate(15)",
        "setFullYear(2030)",
        "setHours(12)",
        "setMilliseconds(500)",
        "setMinutes(30)",
        "setMonth(6)",
        "setSeconds(45)",
        "setTime(0)",
        "setUTCDate(15)",
        "setUTCFullYear(2030)",
        "setUTCHours(12)",
        "setUTCMilliseconds(500)",
        "setUTCMinutes(30)",
        "setUTCMonth(6)",
        "setUTCSeconds(45)",
        "setYear(99)",
    ]
    for snippet in setters:
        n += 1
        method = snippet.split("(")[0]
        body = f"const d = new Date()\nd.{snippet}\n"
        write_case(
            f"date/{n:03d}-{method.lower()}-blocks.test.ts",
            {
                "description": f"Date.{method} blocks",
                "verdict": "block",
                "detector": "date.",
                "payload": "edit",
            },
            body,
        )
    n += 1
    write_case(
        f"date/{n:03d}-temporal-with-allows.test.ts",
        {
            "description": "Temporal.with allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const d = Temporal.PlainDate.from('2026-01-01')\nconst next = d.with({ month: 6 })\n",
    )
    n += 1
    write_case(
        f"date/{n:03d}-temporal-add-allows.test.ts",
        {
            "description": "Temporal.add allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const d = Temporal.PlainDate.from('2026-01-01')\nconst next = d.add({ days: 7 })\n",
    )
    return n


def gen_symbol_cases() -> int:
    """Symbol-keyed property assignment cases (Phase 39)."""
    n = 0
    keys = [
        ("Symbol.iterator", "function* () { yield 1 }"),
        ("Symbol.asyncIterator", "async function* () { yield 1 }"),
        ("Symbol.toPrimitive", "() => 0"),
        ("Symbol.toStringTag", "'Custom'"),
        ("Symbol.hasInstance", "() => true"),
    ]
    for key, val in keys:
        n += 1
        label = key.split(".")[1].lower()
        body = f"const obj: any = {{}}\nobj[{key}] = {val}\n"
        write_case(
            f"symbol/{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{key} assignment blocks",
                "verdict": "block",
                "detector": "symbol-key.assignment",
                "payload": "edit",
            },
            body,
        )
    n += 1
    write_case(
        f"symbol/{n:03d}-literal-allows.test.ts",
        {
            "description": "Symbol-keyed literal allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const obj = {\n  [Symbol.iterator]: function* () { yield 1 }\n}\n",
    )
    return n


def gen_private_field_cases() -> int:
    """Private class field mutation cases (Phase 39)."""
    n = 0
    cases = [
        ("assign", "this.#count = 1"),
        ("compound", "this.#count += 1"),
        ("postfix-inc", "this.#count++"),
        ("prefix-inc", "++this.#count"),
        ("postfix-dec", "this.#count--"),
    ]
    for label, snippet in cases:
        n += 1
        body = textwrap.dedent(f"""\
            class Counter {{
              #count = 0;
              bump() {{ {snippet} }}
            }}
        """)
        write_case(
            f"private_field/{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"private field {label} blocks",
                "verdict": "block",
                "detector": "private-field.",
                "payload": "edit",
            },
            body,
        )
    n += 1
    write_case(
        f"private_field/{n:03d}-declaration-allows.test.ts",
        {
            "description": "private field declaration allows",
            "verdict": "allow",
            "payload": "write",
        },
        textwrap.dedent("""\
            class Counter {
              #count = 0;
              current(): number { return this.#count }
            }
        """),
    )
    return n


def gen_static_block_cases() -> int:
    """Static initialization block cases (Phase 39)."""
    n = 0
    n += 1
    write_case(
        f"static_block/{n:03d}-canonical-allows.test.ts",
        {
            "description": "canonical single static block allows",
            "verdict": "allow",
            "payload": "write",
        },
        textwrap.dedent("""\
            class Config {
              static endpoint: string;
              static {
                Config.endpoint = 'https://api.example.com'
              }
            }
        """),
    )
    n += 1
    write_case(
        f"static_block/{n:03d}-branching-blocks.test.ts",
        {
            "description": "static block with if/else blocks",
            "verdict": "block",
            "detector": "static-block.mutation",
            "payload": "write",
        },
        textwrap.dedent("""\
            class Cache {
              static items: Map<string, number>;
              static {
                if (globalThis.testEnv) {
                  Cache.items = new Map()
                } else {
                  Cache.items = new Map([['default', 0]])
                }
              }
            }
        """),
    )
    return n


def gen_allowlist_cases() -> int:
    """State-management filename auto-allow cases."""
    n = 0
    n += 1
    write_case(
        f"allowlist/{n:03d}-store-suffix-allows.test.ts",
        {
            "description": "*Store.ts auto-allows mutation",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/counterStore.ts",
        },
        textwrap.dedent("""\
            class CounterStore {
              #count = 0;
              bump() { this.#count += 1 }
            }
        """),
    )
    n += 1
    write_case(
        f"allowlist/{n:03d}-slice-suffix-allows.test.ts",
        {
            "description": "*Slice.ts auto-allows array.push",
            "verdict": "allow",
            "payload": "edit",
            "file": "/repo/src/business/todosSlice.ts",
        },
        "state.items.push(action.payload)\n",
    )
    n += 1
    write_case(
        f"allowlist/{n:03d}-reducer-suffix-allows.test.ts",
        {
            "description": "*reducer.ts auto-allows assignment",
            "verdict": "allow",
            "payload": "edit",
            "file": "/repo/src/business/todoReducer.ts",
        },
        "state.count = state.count + 1\n",
    )
    n += 1
    write_case(
        f"allowlist/{n:03d}-pinia-suffix-allows.test.ts",
        {
            "description": "*.pinia.ts auto-allows array.push",
            "verdict": "allow",
            "payload": "edit",
            "file": "/repo/src/business/items.pinia.ts",
        },
        "state.items.push(item)\n",
    )
    n += 1
    write_case(
        f"allowlist/{n:03d}-machine-suffix-allows.test.ts",
        {
            "description": "*.machine.ts auto-allows mutation",
            "verdict": "allow",
            "payload": "edit",
            "file": "/repo/src/business/order.machine.ts",
        },
        "context.items.push(action.value)\n",
    )
    return n


def gen_object_utility_cases() -> int:
    """Object.assign/defineProperty/setPrototypeOf and Reflect cases."""
    n = 0
    cases = [
        ("object-assign-target", "Object.assign(target, src)", "object.assign"),
        (
            "define-property",
            "Object.defineProperty(obj, 'x', { value: 1 })",
            "object.defineProperty",
        ),
        (
            "define-properties",
            "Object.defineProperties(obj, { x: { value: 1 } })",
            "object.defineProperties",
        ),
        (
            "set-prototype-of",
            "Object.setPrototypeOf(obj, proto)",
            "object.setPrototypeOf",
        ),
        ("reflect-set", "Reflect.set(obj, 'x', 1)", "reflect.set"),
        (
            "reflect-delete",
            "Reflect.deleteProperty(obj, 'x')",
            "reflect.deleteProperty",
        ),
        (
            "reflect-define",
            "Reflect.defineProperty(obj, 'x', { value: 1 })",
            "reflect.defineProperty",
        ),
        (
            "reflect-setproto",
            "Reflect.setPrototypeOf(obj, proto)",
            "reflect.setPrototypeOf",
        ),
    ]
    for label, snippet, detector in cases:
        n += 1
        body = f"const target: any = {{}}\nconst src = {{ a: 1 }}\nconst obj: any = {{}}\nconst proto = null\n{snippet}\n"
        write_case(
            f"property/util_{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{label} blocks",
                "verdict": "block",
                "detector": detector,
                "payload": "edit",
            },
            body,
        )
    n += 1
    write_case(
        f"property/util_{n:03d}-object-assign-fresh-allows.test.ts",
        {
            "description": "Object.assign with fresh literal target allows",
            "verdict": "allow",
            "payload": "write",
        },
        "const obj = { a: 1 }\nconst merged = Object.assign({}, obj, { b: 2 })\n",
    )
    return n


def gen_global_mutation_cases() -> int:
    """globalThis/window/process.env mutation cases."""
    n = 0
    cases = [
        ("globalthis-x", "globalThis.x = 1", "global.assignment"),
        ("process-env", "process.env.X = '1'", "global.assignment"),
    ]
    for label, snippet, detector in cases:
        n += 1
        body = f"{snippet}\n"
        write_case(
            f"property/global_{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{label} blocks",
                "verdict": "block",
                "detector": detector,
                "payload": "edit",
            },
            body,
        )
    return n


def gen_url_headers_formdata_cases() -> int:
    """URLSearchParams/Headers/FormData mutation cases."""
    n = 0
    cases = [
        ("usp-append", "params.append('k', 'v')", "web-api.url-search-params."),
        ("usp-set", "params.set('k', 'v')", "web-api.url-search-params."),
        ("usp-delete", "params.delete('k')", "web-api.url-search-params."),
        ("usp-sort", "params.sort()", "web-api.url-search-params."),
        ("headers-append", "headers.append('X', 'y')", "web-api.headers."),
        ("headers-set", "headers.set('X', 'y')", "web-api.headers."),
        ("headers-delete", "headers.delete('X')", "web-api.headers."),
        ("formdata-append", "form.append('k', 'v')", "web-api.form-data."),
        ("formdata-set", "form.set('k', 'v')", "web-api.form-data."),
        ("formdata-delete", "form.delete('k')", "web-api.form-data."),
    ]
    for label, snippet, detector in cases:
        n += 1
        body = textwrap.dedent(f"""\
            const params = new URLSearchParams()
            const headers = new Headers()
            const form = new FormData()
            {snippet}
        """)
        write_case(
            f"property/webapi_{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{label} blocks",
                "verdict": "block",
                "detector": detector,
                "payload": "edit",
            },
            body,
        )
    return n


def gen_typed_array_cases() -> int:
    """TypedArray mutation cases (default scope flags, hot path allows)."""
    n = 0
    methods = ["set", "fill", "sort", "reverse", "copyWithin"]
    for method in methods:
        n += 1
        arg = (
            "[1, 2]"
            if method == "set"
            else ""
            if method in ("sort", "reverse")
            else "0"
        )
        body = f"const buf = new Uint8Array(4)\nbuf.{method}({arg})\n"
        write_case(
            f"array/typed_{n:03d}-uint8-{method}-blocks.test.ts",
            {
                "description": f"Uint8Array.{method} blocks in business scope",
                "verdict": "block",
                "detector": "typed-array.",
                "payload": "edit",
                "file": "/repo/src/business/data.ts",
            },
            body,
        )
    for method in methods:
        n += 1
        arg = (
            "[1, 2]"
            if method == "set"
            else ""
            if method in ("sort", "reverse")
            else "0"
        )
        body = f"const buf = new Uint8Array(4)\nbuf.{method}({arg})\n"
        write_case(
            f"array/typed_{n:03d}-uint8-{method}-hot-allows.test.ts",
            {
                "description": f"Uint8Array.{method} allows in crypto hot path",
                "verdict": "allow",
                "payload": "edit",
                "file": "/repo/src/crypto/hash.ts",
            },
            body,
        )
    return n


def gen_let_const_cases() -> int:
    """let-could-be-const cases (full-file Write only)."""
    n = 0
    n += 1
    write_case(
        f"property/letconst_{n:03d}-could-be-const-blocks.test.ts",
        {
            "description": "let never reassigned blocks",
            "verdict": "block",
            "detector": "let.could-be-const",
            "payload": "write",
        },
        "let value = 1\nconst doubled = value * 2\nexport { doubled }\n",
    )
    n += 1
    write_case(
        f"property/letconst_{n:03d}-reassigned-allows.test.ts",
        {
            "description": "let reassigned allows",
            "verdict": "allow",
            "payload": "write",
        },
        "let value = 1\nvalue = value + 1\nexport { value }\n",
    )
    return n


def gen_suppression_cases() -> int:
    """Suppression marker cases."""
    n = 0
    n += 1
    write_case(
        f"allowlist/sup_{n:03d}-line-marker-allows.test.ts",
        {
            "description": "line marker with justification allows",
            "verdict": "allow",
            "payload": "edit",
        },
        "const items = []\nitems.push(1) // allow-mutation -- legacy hot path\n",
    )
    n += 1
    write_case(
        f"allowlist/sup_{n:03d}-line-marker-no-justification-blocks.test.ts",
        {
            "description": "line marker without justification still blocks",
            "verdict": "block",
            "detector": "array.",
            "payload": "edit",
        },
        "const items = []\nitems.push(1) // allow-mutation\n",
    )
    n += 1
    write_case(
        f"allowlist/sup_{n:03d}-file-marker-allows.test.ts",
        {
            "description": "file-level marker with justification allows",
            "verdict": "allow",
            "payload": "write",
        },
        "// @allow-mutation -- ported from legacy module\nconst items = []\nitems.push(1)\n",
    )
    return n


def gen_increment_index_cases() -> int:
    """Compound and increment on computed/index targets."""
    n = 0
    cases = [
        ("prop-postinc", "obj.x++", "property.increment"),
        ("prop-postdec", "obj.x--", "property.increment"),
        ("prop-preinc", "++obj.x", "property.increment-prefix"),
        ("prop-predec", "--obj.x", "property.increment-prefix"),
        ("idx-compound-add", "arr[i] += 1", "property.compound-index"),
        ("idx-compound-sub", "arr[i] -= 1", "property.compound-index"),
        ("idx-compound-mul", "arr[i] *= 2", "property.compound-index"),
        ("idx-compound-div", "arr[i] /= 2", "property.compound-index"),
    ]
    for label, snippet, detector in cases:
        n += 1
        body = f"const arr = [1, 2, 3]\nconst obj: any = {{ x: 0 }}\nconst i = 0\n{snippet}\n"
        write_case(
            f"property/idx_{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"{label} blocks",
                "verdict": "block",
                "detector": detector,
                "payload": "edit",
            },
            body,
        )
    return n


def gen_zustand_jotai_cases() -> int:
    """Zustand/Jotai/Valtio callback auto-allow cases."""
    n = 0
    n += 1
    write_case(
        f"allowlist/lib_zus_{n:03d}-zustand-set-produce-allows.test.ts",
        {
            "description": "Zustand set(produce) callback allows",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/useStore.ts",
        },
        textwrap.dedent("""\
            import { create } from 'zustand'
            import { produce } from 'immer'
            export const useStore = create((set: any) => ({
              items: [] as number[],
              add: (x: number) => set(produce((draft: any) => { draft.items.push(x) })),
            }))
        """),
    )
    n += 1
    write_case(
        f"allowlist/lib_jot_{n:03d}-jotai-set-allows.test.ts",
        {
            "description": "Jotai useAtom setter callback allows mutation",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/atomStore.ts",
        },
        textwrap.dedent("""\
            import { atom, useAtom } from 'jotai'
            const itemsAtom = atom<number[]>([])
            export function useItems() {
              const [items, setItems] = useAtom(itemsAtom)
              return () => setItems((prev) => [...prev, 1])
            }
        """),
    )
    n += 1
    write_case(
        f"allowlist/lib_val_{n:03d}-valtio-proxy-allows.test.ts",
        {
            "description": "Valtio proxy state mutation allows",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/proxyStore.ts",
        },
        textwrap.dedent("""\
            import { proxy } from 'valtio'
            export const state = proxy({ count: 0 })
            export function bump() { state.count += 1 }
        """),
    )
    n += 1
    write_case(
        f"allowlist/lib_mob_{n:03d}-mobx-action-allows.test.ts",
        {
            "description": "MobX action allows mutation",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/mobxStore.ts",
        },
        textwrap.dedent("""\
            import { makeAutoObservable, action } from 'mobx'
            export class Counter {
              count = 0
              constructor() { makeAutoObservable(this) }
              bump = action(() => { this.count += 1 })
            }
        """),
    )
    return n


def gen_param_reassign_cases() -> int:
    """Parameter reassignment cases."""
    n = 0
    n += 1
    write_case(
        f"property/param_{n:03d}-arbitrary-blocks.test.ts",
        {
            "description": "param reassignment blocks for non-allowlisted name",
            "verdict": "block",
            "detector": "param.reassign",
            "payload": "write",
        },
        "export function handler(input: string) {\n  input = input.trim()\n  return input\n}\n",
    )
    n += 1
    write_case(
        f"property/param_{n:03d}-acc-allowed-allows.test.ts",
        {
            "description": "param reassign 'acc' allows in reducer",
            "verdict": "allow",
            "payload": "write",
        },
        "export function sum(arr: number[]) {\n  return arr.reduce((acc, x) => { acc = acc + x; return acc }, 0)\n}\n",
    )
    n += 1
    write_case(
        f"property/param_{n:03d}-req-allowed-allows.test.ts",
        {
            "description": "param reassign 'req' allows in middleware",
            "verdict": "allow",
            "payload": "write",
        },
        "export function middleware(req: any) {\n  req = { ...req, user: null }\n  return req\n}\n",
    )
    n += 1
    write_case(
        f"property/param_{n:03d}-draft-allowed-allows.test.ts",
        {
            "description": "param reassign 'draft' allows",
            "verdict": "allow",
            "payload": "write",
        },
        "export function update(draft: any) {\n  draft = { ...draft, edited: true }\n  return draft\n}\n",
    )
    return n


def gen_extra_property_cases() -> int:
    """Additional property-assignment variants on nested receivers."""
    n = 0
    receivers = ["state", "config", "settings", "data", "model"]
    for r in receivers:
        n += 1
        body = f"const {r}: any = {{}}\n{r}.value = 1\n"
        write_case(
            f"property/extra_{n:03d}-{r}-value-blocks.test.ts",
            {
                "description": f"{r}.value = 1 blocks",
                "verdict": "block",
                "detector": "property.assignment",
                "payload": "edit",
            },
            body,
        )
    return n


def gen_extra_array_cases() -> int:
    """Additional array method block variants."""
    n = 0
    for arg in ["1", "1, 2", "1, 2, 3", "...rest", "x"]:
        n += 1
        body = f"const items: any[] = []\nconst rest = [9, 9]\nconst x = 7\nitems.push({arg})\n"
        write_case(
            f"array/extra_push_{n:03d}-args-blocks.test.ts",
            {
                "description": f"items.push({arg}) blocks",
                "verdict": "block",
                "detector": "array.",
                "payload": "edit",
            },
            body,
        )
    for arg in ["", "0, 1", "1, 2, 'a'", "0, 0, 'x', 'y'"]:
        n += 1
        body = f"const items = [1, 2, 3]\nitems.splice({arg})\n"
        write_case(
            f"array/extra_splice_{n:03d}-args-blocks.test.ts",
            {
                "description": f"items.splice({arg}) blocks",
                "verdict": "block",
                "detector": "array.",
                "payload": "edit",
            },
            body,
        )
    return n


def gen_atomics_cases() -> int:
    """Atomics mutation cases (SharedArrayBuffer)."""
    n = 0
    cases = [
        ("store", "Atomics.store(buf, 0, 1)"),
        ("add", "Atomics.add(buf, 0, 1)"),
        ("sub", "Atomics.sub(buf, 0, 1)"),
        ("and", "Atomics.and(buf, 0, 1)"),
        ("or", "Atomics.or(buf, 0, 1)"),
        ("xor", "Atomics.xor(buf, 0, 1)"),
        ("exchange", "Atomics.exchange(buf, 0, 1)"),
        ("compareExchange", "Atomics.compareExchange(buf, 0, 0, 1)"),
    ]
    for label, snippet in cases:
        n += 1
        body = f"const sab = new SharedArrayBuffer(8)\nconst buf = new Int32Array(sab)\n{snippet}\n"
        write_case(
            f"property/atomics_{n:03d}-{label}-blocks.test.ts",
            {
                "description": f"Atomics.{label} blocks in business scope",
                "verdict": "block",
                "detector": "shared-memory.atomics.",
                "payload": "edit",
                "file": "/repo/src/business/atomic.ts",
            },
            body,
        )
    return n


def gen_dom_cases() -> int:
    """DOM-receiver cases must allow (out of scope per typescript-immutability.md)."""
    n = 0
    cases = [
        "element.innerHTML = '<p>x</p>'",
        "element.textContent = 'x'",
        "element.className = 'foo'",
        "el.style.color = 'red'",
        "el.classList.add('x')",
        "el.dataset.x = '1'",
        "el.scrollTop = 0",
        "input.disabled = true",
        "shadowRoot.innerHTML = '<x />'",
        "document.title = 'x'",
        "window.name = 'x'",
        "localStorage.setItem('k', 'v')",
        "localStorage.removeItem('k')",
        "sessionStorage.clear()",
        "store.put(item)",
        "cursor.update(value)",
        "cursor.delete()",
    ]
    for i, snippet in enumerate(cases, start=1):
        n += 1
        body = f"const element: any = document.body\nconst el: any = element\nconst input: any = element\nconst shadowRoot: any = element.shadowRoot\nconst store: any = {{}}\nconst cursor: any = {{}}\n{snippet}\n"
        write_case(
            f"allowlist/dom_{n:03d}-{i:02d}-allows.test.ts",
            {
                "description": f"DOM/storage receiver allows: {snippet[:40]}",
                "verdict": "allow",
                "payload": "edit",
            },
            body,
        )
    return n


def gen_immer_mutative_cases() -> int:
    """Library callback auto-allow cases."""
    n = 0
    n += 1
    write_case(
        f"allowlist/lib_{n:03d}-immer-produce-allows.test.ts",
        {
            "description": "Immer produce(draft) callback allows mutation",
            "verdict": "allow",
            "payload": "write",
        },
        textwrap.dedent("""\
            import { produce } from 'immer'
            const state = { items: [] as number[] }
            const next = produce(state, (draft) => {
              draft.items.push(1)
              draft.count = 0
            })
        """),
    )
    n += 1
    write_case(
        f"allowlist/lib_{n:03d}-mutative-create-allows.test.ts",
        {
            "description": "Mutative create(draft) callback allows mutation",
            "verdict": "allow",
            "payload": "write",
        },
        textwrap.dedent("""\
            import { create } from 'mutative'
            const state = { items: [] as number[] }
            const next = create(state, (draft) => {
              draft.items.push(1)
            })
        """),
    )
    n += 1
    write_case(
        f"allowlist/lib_{n:03d}-redux-toolkit-allows.test.ts",
        {
            "description": "Redux Toolkit createSlice reducer allows mutation",
            "verdict": "allow",
            "payload": "write",
            "file": "/repo/src/business/todosSlice.ts",
        },
        textwrap.dedent("""\
            import { createSlice } from '@reduxjs/toolkit'
            export const todos = createSlice({
              name: 'todos',
              initialState: { items: [] as string[] },
              reducers: {
                add(state, action) {
                  state.items.push(action.payload)
                },
              },
            })
        """),
    )
    return n


def main() -> None:
    total = 0
    total += gen_array_cases()
    total += gen_collection_cases()
    total += gen_property_cases()
    total += gen_date_cases()
    total += gen_symbol_cases()
    total += gen_private_field_cases()
    total += gen_static_block_cases()
    total += gen_allowlist_cases()
    total += gen_object_utility_cases()
    total += gen_global_mutation_cases()
    total += gen_url_headers_formdata_cases()
    total += gen_typed_array_cases()
    total += gen_let_const_cases()
    total += gen_suppression_cases()
    total += gen_immer_mutative_cases()
    total += gen_increment_index_cases()
    total += gen_zustand_jotai_cases()
    total += gen_param_reassign_cases()
    total += gen_extra_property_cases()
    total += gen_extra_array_cases()
    total += gen_dom_cases()
    total += gen_atomics_cases()
    print(f"generated {total} cases")


if __name__ == "__main__":
    main()

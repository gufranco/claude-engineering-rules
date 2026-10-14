from __future__ import annotations

import textwrap

from _case_model import Case, allow, block

PROPERTY_WRITES = (
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
)

PROPERTY_CASES: tuple[Case, ...] = (
    *(
        block(
            "property/",
            f"{label}-blocks",
            f"{label} blocks",
            detector,
            "edit",
            f"const obj: any = {{ x: 0 }}\nconst arr = [1, 2, 3]\n{snippet}\n",
        )
        for label, snippet, detector in PROPERTY_WRITES
    ),
    allow(
        "property/",
        "spread-update-allows",
        "spread-update pattern allows",
        "write",
        "const obj = { x: 0 }\nconst next = { ...obj, x: 1 }\n",
    ),
    allow(
        "property/",
        "with-allows",
        "arr.with(i, v) allows",
        "write",
        "const arr = [1, 2, 3]\nconst next = arr.with(0, 99)\n",
    ),
    allow(
        "property/",
        "rest-omit-allows",
        "rest-omit pattern allows",
        "write",
        "const obj = { x: 1, y: 2 }\nconst { x, ...rest } = obj\n",
    ),
)

OBJECT_UTILITY_CALLS = (
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
    ("set-prototype-of", "Object.setPrototypeOf(obj, proto)", "object.setPrototypeOf"),
    ("reflect-set", "Reflect.set(obj, 'x', 1)", "reflect.set"),
    ("reflect-delete", "Reflect.deleteProperty(obj, 'x')", "reflect.deleteProperty"),
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
)

OBJECT_UTILITY_PRELUDE = "const target: any = {}\nconst src = { a: 1 }\nconst obj: any = {}\nconst proto = null\n"

OBJECT_UTILITY_CASES: tuple[Case, ...] = (
    *(
        block(
            "property/util_",
            f"{label}-blocks",
            f"{label} blocks",
            detector,
            "edit",
            f"{OBJECT_UTILITY_PRELUDE}{snippet}\n",
        )
        for label, snippet, detector in OBJECT_UTILITY_CALLS
    ),
    allow(
        "property/util_",
        "object-assign-fresh-allows",
        "Object.assign with fresh literal target allows",
        "write",
        "const obj = { a: 1 }\nconst merged = Object.assign({}, obj, { b: 2 })\n",
    ),
)

GLOBAL_MUTATION_CASES: tuple[Case, ...] = (
    block(
        "property/global_",
        "globalthis-x-blocks",
        "globalthis-x blocks",
        "global.assignment",
        "edit",
        "globalThis.x = 1\n",
    ),
    block(
        "property/global_",
        "process-env-blocks",
        "process-env blocks",
        "global.assignment",
        "edit",
        "process.env.X = '1'\n",
    ),
)

WEB_API_CALLS = (
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
)

URL_HEADERS_FORMDATA_CASES: tuple[Case, ...] = tuple(
    block(
        "property/webapi_",
        f"{label}-blocks",
        f"{label} blocks",
        detector,
        "edit",
        textwrap.dedent(f"""\
            const params = new URLSearchParams()
            const headers = new Headers()
            const form = new FormData()
            {snippet}
        """),
    )
    for label, snippet, detector in WEB_API_CALLS
)

LET_CONST_CASES: tuple[Case, ...] = (
    block(
        "property/letconst_",
        "could-be-const-blocks",
        "let never reassigned blocks",
        "let.could-be-const",
        "write",
        "let value = 1\nconst doubled = value * 2\nexport { doubled }\n",
    ),
    allow(
        "property/letconst_",
        "reassigned-allows",
        "let reassigned allows",
        "write",
        "let value = 1\nvalue = value + 1\nexport { value }\n",
    ),
)

INCREMENT_INDEX_WRITES = (
    ("prop-postinc", "obj.x++", "property.increment"),
    ("prop-postdec", "obj.x--", "property.increment"),
    ("prop-preinc", "++obj.x", "property.increment-prefix"),
    ("prop-predec", "--obj.x", "property.increment-prefix"),
    ("idx-compound-add", "arr[i] += 1", "property.compound-index"),
    ("idx-compound-sub", "arr[i] -= 1", "property.compound-index"),
    ("idx-compound-mul", "arr[i] *= 2", "property.compound-index"),
    ("idx-compound-div", "arr[i] /= 2", "property.compound-index"),
)

INCREMENT_INDEX_CASES: tuple[Case, ...] = tuple(
    block(
        "property/idx_",
        f"{label}-blocks",
        f"{label} blocks",
        detector,
        "edit",
        f"const arr = [1, 2, 3]\nconst obj: any = {{ x: 0 }}\nconst i = 0\n{snippet}\n",
    )
    for label, snippet, detector in INCREMENT_INDEX_WRITES
)

PARAM_REASSIGN_CASES: tuple[Case, ...] = (
    block(
        "property/param_",
        "arbitrary-blocks",
        "param reassignment blocks for non-allowlisted name",
        "param.reassign",
        "write",
        "export function handler(input: string) {\n  input = input.trim()\n  return input\n}\n",
    ),
    allow(
        "property/param_",
        "acc-allowed-allows",
        "param reassign 'acc' allows in reducer",
        "write",
        "export function sum(arr: number[]) {\n  return arr.reduce((acc, x) => { acc = acc + x; return acc }, 0)\n}\n",
    ),
    allow(
        "property/param_",
        "req-allowed-allows",
        "param reassign 'req' allows in middleware",
        "write",
        "export function middleware(req: any) {\n  req = { ...req, user: null }\n  return req\n}\n",
    ),
    allow(
        "property/param_",
        "draft-allowed-allows",
        "param reassign 'draft' allows",
        "write",
        "export function update(draft: any) {\n  draft = { ...draft, edited: true }\n  return draft\n}\n",
    ),
)

EXTRA_PROPERTY_RECEIVERS = ("state", "config", "settings", "data", "model")

EXTRA_PROPERTY_CASES: tuple[Case, ...] = tuple(
    block(
        "property/extra_",
        f"{r}-value-blocks",
        f"{r}.value = 1 blocks",
        "property.assignment",
        "edit",
        f"const {r}: any = {{}}\n{r}.value = 1\n",
    )
    for r in EXTRA_PROPERTY_RECEIVERS
)

ATOMICS_CALLS = (
    ("store", "Atomics.store(buf, 0, 1)"),
    ("add", "Atomics.add(buf, 0, 1)"),
    ("sub", "Atomics.sub(buf, 0, 1)"),
    ("and", "Atomics.and(buf, 0, 1)"),
    ("or", "Atomics.or(buf, 0, 1)"),
    ("xor", "Atomics.xor(buf, 0, 1)"),
    ("exchange", "Atomics.exchange(buf, 0, 1)"),
    ("compareExchange", "Atomics.compareExchange(buf, 0, 0, 1)"),
)

ATOMICS_CASES: tuple[Case, ...] = tuple(
    block(
        "property/atomics_",
        f"{label}-blocks",
        f"Atomics.{label} blocks in business scope",
        "shared-memory.atomics.",
        "edit",
        f"const sab = new SharedArrayBuffer(8)\nconst buf = new Int32Array(sab)\n{snippet}\n",
        "/repo/src/business/atomic.ts",
    )
    for label, snippet in ATOMICS_CALLS
)

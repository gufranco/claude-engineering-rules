from __future__ import annotations

import textwrap

from _case_model import Case, allow, block

DATE_SETTERS = (
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
)

DATE_CASES: tuple[Case, ...] = (
    *(
        block(
            "date/",
            f"{snippet.split('(')[0].lower()}-blocks",
            f"Date.{snippet.split('(')[0]} blocks",
            "date.",
            "edit",
            f"const d = new Date()\nd.{snippet}\n",
        )
        for snippet in DATE_SETTERS
    ),
    allow(
        "date/",
        "temporal-with-allows",
        "Temporal.with allows",
        "write",
        "const d = Temporal.PlainDate.from('2026-01-01')\nconst next = d.with({ month: 6 })\n",
    ),
    allow(
        "date/",
        "temporal-add-allows",
        "Temporal.add allows",
        "write",
        "const d = Temporal.PlainDate.from('2026-01-01')\nconst next = d.add({ days: 7 })\n",
    ),
)

SYMBOL_KEYS = (
    ("Symbol.iterator", "function* () { yield 1 }"),
    ("Symbol.asyncIterator", "async function* () { yield 1 }"),
    ("Symbol.toPrimitive", "() => 0"),
    ("Symbol.toStringTag", "'Custom'"),
    ("Symbol.hasInstance", "() => true"),
)

SYMBOL_CASES: tuple[Case, ...] = (
    *(
        block(
            "symbol/",
            f"{key.split('.')[1].lower()}-blocks",
            f"{key} assignment blocks",
            "symbol-key.assignment",
            "edit",
            f"const obj: any = {{}}\nobj[{key}] = {val}\n",
        )
        for key, val in SYMBOL_KEYS
    ),
    allow(
        "symbol/",
        "literal-allows",
        "Symbol-keyed literal allows",
        "write",
        "const obj = {\n  [Symbol.iterator]: function* () { yield 1 }\n}\n",
    ),
)

PRIVATE_FIELD_WRITES = (
    ("assign", "this.#count = 1"),
    ("compound", "this.#count += 1"),
    ("postfix-inc", "this.#count++"),
    ("prefix-inc", "++this.#count"),
    ("postfix-dec", "this.#count--"),
)

PRIVATE_FIELD_CASES: tuple[Case, ...] = (
    *(
        block(
            "private_field/",
            f"{label}-blocks",
            f"private field {label} blocks",
            "private-field.",
            "edit",
            textwrap.dedent(f"""\
                class Counter {{
                  #count = 0;
                  bump() {{ {snippet} }}
                }}
            """),
        )
        for label, snippet in PRIVATE_FIELD_WRITES
    ),
    allow(
        "private_field/",
        "declaration-allows",
        "private field declaration allows",
        "write",
        textwrap.dedent("""\
            class Counter {
              #count = 0;
              current(): number { return this.#count }
            }
        """),
    ),
)

STATIC_BLOCK_CASES: tuple[Case, ...] = (
    allow(
        "static_block/",
        "canonical-allows",
        "canonical single static block allows",
        "write",
        textwrap.dedent("""\
            class Config {
              static endpoint: string;
              static {
                Config.endpoint = 'https://api.example.com'
              }
            }
        """),
    ),
    block(
        "static_block/",
        "branching-blocks",
        "static block with if/else blocks",
        "static-block.mutation",
        "write",
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
    ),
)

from __future__ import annotations

import re

JS_EXTS: tuple[str, ...] = (
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)
TS_EXTS: tuple[str, ...] = (".ts", ".tsx", ".mts", ".cts")

SKIP_SEGMENTS: tuple[str, ...] = (
    "/scripts/",
    "/bin/",
    "/tools/",
    "/cli/",
    "/__tests__/",
    "/__test__/",
    "/.claude/hooks/",
    "/test-utils/",
    "/testing/",
    "/migrations/",
    "/seed",
    "/e2e/",
    "/fixtures/",
)

SKIP_SUFFIXES: tuple[str, ...] = (
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    ".config.ts",
    ".config.js",
    ".config.mjs",
    ".stories.ts",
    ".stories.tsx",
    ".d.ts",
)

HOT_PATH_SEGMENTS: tuple[str, ...] = (
    "/crypto/",
    "/crypt/",
    "/cipher/",
    "/hash/",
    "/image/",
    "/images/",
    "/audio/",
    "/media/",
    "/parser/",
    "/decoder/",
    "/encoder/",
    "/codec/",
    "/webgl/",
    "/canvas/",
    "/pixel/",
    "/simd/",
    "/wasm/",
    "/bench/",
    "/benchmark/",
    "/dsp/",
    "/signal/",
    "/fft/",
    "/ml/",
    "/tensor/",
    "/webassembly/",
    "/wgpu/",
    "/webgpu/",
)

TYPED_ARRAY_SUBTYPES: tuple[str, ...] = (
    "Int8Array",
    "Uint8Array",
    "Uint8ClampedArray",
    "Int16Array",
    "Uint16Array",
    "Int32Array",
    "Uint32Array",
    "Float16Array",
    "Float32Array",
    "Float64Array",
    "BigInt64Array",
    "BigUint64Array",
)

THIRD_PARTY_COMMAND_QUEUES: frozenset[str] = frozenset(
    {
        "dataLayer",
        "dgEvent",
        "_paq",
        "_hsq",
        "_gaq",
        "_mtm",
        "uetq",
    }
)


PUSH_FRAMEWORK_RECEIVERS: frozenset[str] = frozenset(
    {
        "router",
        "Router",
        "routerRef",
        "navigation",
        "nav",
        "history",
        "pathname",
        "location",
        "stream",
        "streams",
        "Readable",
        "Writable",
        "Duplex",
        "Transform",
        "PassThrough",
        "res",
        "response",
        "ws",
        "socket",
        "client",
    }
    | THIRD_PARTY_COMMAND_QUEUES
)

PUSH_FRAMEWORK_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(name) for name in PUSH_FRAMEWORK_RECEIVERS)
    + r")(?:\.current)?\.push\b"
)

PUSH_CALL_PATTERN = re.compile(r"\.push\b")

DOM_RECEIVER_NAMES: frozenset[str] = frozenset(
    {
        "document",
        "body",
        "head",
        "html",
        "window",
        "self",
        "navigator",
        "screen",
        "history",
        "location",
        "element",
        "el",
        "node",
        "target",
        "currentTarget",
        "parent",
        "parentNode",
        "parentElement",
        "child",
        "childNode",
        "sibling",
        "root",
        "container",
        "wrapper",
        "host",
        "shadowRoot",
        "canvas",
        "ctx",
        "context2d",
        "context3d",
        "audio",
        "video",
        "img",
        "image",
        "form",
        "input",
        "button",
        "anchor",
        "link",
        "iframe",
        "ref",
        "domRef",
    }
)

DOM_TYPED_RECEIVER_PATTERN = re.compile(
    r".*(?:Element|HTMLElement|Node|Target|Btn|Button|Input|Img|Ref|Canvas|Anchor|Iframe|El)$"
)

DOM_PROPERTY_NAMES: frozenset[str] = frozenset(
    {
        "innerHTML",
        "outerHTML",
        "innerText",
        "outerText",
        "textContent",
        "className",
        "tabIndex",
        "scrollTop",
        "scrollLeft",
        "contentEditable",
        "spellcheck",
        "ariaLabel",
        "ariaHidden",
        "ariaDescribedBy",
        "ariaLabelledBy",
    }
)


def is_dom_receiver(receiver: str | None) -> bool:
    if not receiver:
        return False
    short = receiver.strip()
    if not short:
        return False
    last = short.rsplit(".", maxsplit=1)[-1]
    if last in DOM_RECEIVER_NAMES:
        return True
    if DOM_TYPED_RECEIVER_PATTERN.match(last):
        return True
    if "." in short:
        accessor_suffixes = (
            ".target",
            ".currentTarget",
            ".parentNode",
            ".parentElement",
            ".firstChild",
            ".lastChild",
            ".firstElementChild",
            ".lastElementChild",
            ".nextSibling",
            ".previousSibling",
            ".style",
            ".classList",
            ".dataset",
            ".attributes",
        )
        if any(short.endswith(s) for s in accessor_suffixes):
            return True
    return False


def is_dom_assignment(receiver: str | None, prop: str | None) -> bool:
    if is_dom_receiver(receiver):
        return True
    if prop and prop in DOM_PROPERTY_NAMES:
        return True
    return False


STATE_MGMT_FILENAME_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:(?:^|[/._-])[Ss]|(?<=[a-z0-9])S)lice\.(?:ts|tsx|js|jsx)$"),
    re.compile(r"(?:(?:^|[/._-])[Ss]|(?<=[a-z0-9])S)tore\.(?:ts|tsx|js|jsx)$"),
    re.compile(r"(?:(?:^|[/._-])[Rr]|(?<=[a-z0-9])R)educers?\.(?:ts|tsx|js|jsx)$"),
    re.compile(r"\.pinia\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.mobx\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.valtio\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.proxy\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.machine\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.actor\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.atom\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.svelte$", re.IGNORECASE),
    re.compile(r"\.svelte\.(?:ts|js)$", re.IGNORECASE),
    re.compile(r"\.signal\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.qwik\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
    re.compile(r"\.effect\.(?:ts|tsx|js|jsx)$", re.IGNORECASE),
)

IMMER_PRODUCE_PATTERN = re.compile(
    r"\bproduce\s*\(\s*(?:[^,)]*,\s*)?\(?\s*(?:draft|state|[a-zA-Z_$][\w$]*)\s*[,):]"
)
MUTATIVE_CREATE_PATTERN = re.compile(
    r"\bcreate\s*\(\s*(?:[^,)]*,\s*)?\(?\s*(?:draft|state|[a-zA-Z_$][\w$]*)\s*[,):]"
)
REDUX_TOOLKIT_PATTERN = re.compile(
    r"\bcreateSlice\s*\(|builder\.addCase\s*\(|builder\.addMatcher\s*\(|extraReducers\s*[:=]"
)
PINIA_STORE_PATTERN = re.compile(
    r"\bdefineStore\s*\(|\.\$patch\s*\(\s*(?:\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>"
)
VUEX_MUTATIONS_PATTERN = re.compile(r"\bmutations\s*:\s*\{|new\s+Vuex\.Store\s*\(")
MOBX_ACTION_PATTERN = re.compile(
    r"\b(?:runInAction|action)\s*\(|@action\b|"
    r"\bmakeAutoObservable\s*\(\s*this\b|\bmakeObservable\s*\(\s*this\b"
)
ZUSTAND_PRODUCE_PATTERN = re.compile(r"\bset\s*\(\s*produce\s*\(")
YJS_TYPE_PATTERN = re.compile(
    r"\bnew\s+Y\.(?:Array|Map|Text|XmlElement|XmlFragment|XmlText|Doc)\b"
)
VALTIO_IMPORT_PATTERN = re.compile(r"""['"]valtio(?:/[\w/-]+)?['"]""")
VALTIO_PROXY_PATTERN = re.compile(r"\b(?:proxy|proxyMap|proxySet)\s*\(")
JOTAI_IMPORT_PATTERN = re.compile(r"""['"]jotai(?:/[\w/-]+)?['"]""")
JOTAI_USAGE_PATTERN = re.compile(
    r"\b(?:useAtom|useSetAtom|useAtomValue|atomWithReducer|atom)\s*\("
)
RECOIL_IMPORT_PATTERN = re.compile(r"""['"]recoil['"]""")
RECOIL_USAGE_PATTERN = re.compile(
    r"\b(?:useRecoilState|useSetRecoilState|useRecoilValue|atom|selector)\s*\("
)
XSTATE_IMPORT_PATTERN = re.compile(r"""['"]xstate(?:/[\w/-]+)?['"]""")
XSTATE_ASSIGN_PATTERN = re.compile(
    r"\bassign\s*\(\s*\{|"
    r"\bassign\s*\(\s*\(\s*[^)]*\)\s*=>|"
    r"\bsetup\s*\(|"
    r"\bcreateMachine\s*\("
)
SOLID_STORE_IMPORT_PATTERN = re.compile(r"""['"]solid-js/store['"]""")
SOLID_STORE_USAGE_PATTERN = re.compile(r"\bcreateStore\s*\(|\bcreateMutable\s*\(")
NANOSTORES_IMPORT_PATTERN = re.compile(r"""['"]nanostores(?:/[\w/-]+)?['"]""")
NANOSTORES_USAGE_PATTERN = re.compile(
    r"\b(?:atom|map|computed|deepMap|persistentAtom|persistentMap)\s*\("
)
LEGENDAPP_IMPORT_PATTERN = re.compile(r"""['"]@legendapp/state(?:/[\w/-]+)?['"]""")
LEGENDAPP_USAGE_PATTERN = re.compile(r"\bobservable\s*\(")
TANSTACK_STORE_IMPORT_PATTERN = re.compile(
    r"""['"]@tanstack/(?:store|react-store|solid-store)['"]"""
)
TANSTACK_STORE_USAGE_PATTERN = re.compile(r"\bnew\s+Store\s*\(|\bcreateStore\s*\(")
TANSTACK_STORE_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*"
    r"(?:new\s+Store\s*\(|createStore\s*\()"
)
EFFECT_DATA_IMPORT_PATTERN = re.compile(
    r"""['"](?:@effect/data|effect/Data|effect)['"]"""
)
EFFECT_DATA_USAGE_PATTERN = re.compile(
    r"\bData\.(?:struct|tagged|tuple|array|case|TaggedClass|Class)\s*\("
)
VUE_READONLY_IMPORT_PATTERN = re.compile(r"""['"]vue['"]""")
VUE_READONLY_USAGE_PATTERN = re.compile(
    r"\b(?:readonly|shallowReadonly|toReactive|reactive|ref|shallowRef)\s*\("
)
SVELTE_RUNES_PATTERN = re.compile(
    r"\$state\s*[(.]|\$derived\s*\(|\$effect\s*\(|\$props\s*\(\s*\)"
)

ANGULAR_SIGNALS_IMPORT_PATTERN = re.compile(r"""['"]@angular/core(?:/[\w/-]+)?['"]""")
ANGULAR_SIGNALS_USAGE_PATTERN = re.compile(
    r"\b(?:signal|computed|effect|untracked|linkedSignal|resource)\s*\("
)
ANGULAR_SIGNAL_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*(?:Writable)?Signal[^=]*)?\s*=\s*"
    r"(?:signal|computed|linkedSignal|resource)\s*\("
)

QWIK_SIGNALS_IMPORT_PATTERN = re.compile(
    r"""['"]@builder\.io/qwik(?:[-/][\w/-]+)?['"]"""
)
QWIK_SIGNALS_USAGE_PATTERN = re.compile(
    r"\b(?:useSignal|useStore|useTask\$|useComputed\$|useResource\$)\s*\("
)
QWIK_SIGNAL_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*Signal[^=]*)?\s*=\s*"
    r"(?:useSignal|useStore|useComputed\$)\s*\("
)

PREACT_SIGNALS_IMPORT_PATTERN = re.compile(
    r"""['"]@preact/signals(?:-(?:core|react|vue|preact))?['"]"""
)
PREACT_SIGNALS_USAGE_PATTERN = re.compile(
    r"\b(?:signal|computed|batch|effect|useSignal|useComputed|useSignalEffect)\s*\("
)
PREACT_SIGNAL_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*(?:Signal|ReadonlySignal)[^=]*)?\s*=\s*"
    r"(?:signal|computed|useSignal|useComputed)\s*\("
)

REACT_19_FORMSTATE_PATTERN = re.compile(
    r"\b(?:useFormState|useActionState|useOptimistic)\s*\("
)
REACT_USE_REDUCER_PATTERN = re.compile(r"\b(?:useReducer|useSyncExternalStore)\s*\(")
REACT_SERVER_DIRECTIVE_PATTERN = re.compile(
    r"""^\s*['"]use server['"]\s*;?\s*$""", re.MULTILINE
)

SOLID_RESOURCE_USAGE_PATTERN = re.compile(
    r"\b(?:createResource|createMemo|createDeferred|createComputed|createReaction|createSelector)\s*\("
)
SOLID_PRODUCE_PATTERN = re.compile(r"\b(?:produce|unwrap|reconcile)\s*\(")
SOLID_RECONCILE_PATTERN = re.compile(r"\breconcile\s*\(")
SOLID_PRODUCE_ONLY_PATTERN = re.compile(r"\bproduce\s*\(")

TC39_SIGNALS_IMPORT_PATTERN = re.compile(r"""['"]signal-polyfill['"]""")
TC39_SIGNALS_USAGE_PATTERN = re.compile(
    r"\bnew\s+Signal\.(?:State|Computed)\s*\(|"
    r"\bSignal\.(?:State|Computed|subtle)\b"
)
TC39_SIGNAL_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*Signal\.[^=]+)?\s*=\s*"
    r"new\s+Signal\.(?:State|Computed)\s*\("
)

EFFECT_TS_IMPORT_PATTERN = re.compile(
    r"""['"](?:effect|@effect/(?:io|core|data|stm)(?:/[\w/-]+)?)['"]"""
)
EFFECT_TS_GEN_PATTERN = re.compile(r"\bEffect\.gen\s*\(\s*function\s*\*")
EFFECT_TS_REF_PATTERN = re.compile(
    r"\bRef\.(?:update|set|modify|get|make|getAndSet|updateAndGet|modifyAndGet|setAndGet|unsafeGet|unsafeSet)\s*\(|"
    r"\bSubscriptionRef\.(?:make|update|set|modify)\s*\(|"
    r"\bSynchronizedRef\.(?:make|update|set|modify)\s*\("
)

FP_TS_IMPORT_PATTERN = re.compile(r"""['"]fp-ts(?:/[\w/-]+)?['"]""")
FP_TS_USAGE_PATTERN = re.compile(
    r"\b(?:pipe|flow|chain|fold|map|filter|traverse|sequence)\s*\("
)

VALTIO_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:proxy|proxyMap|proxySet)\s*\("
)
SOLID_DIRECT_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*createMutable\s*\("
)
SOLID_TUPLE_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+\[\s*([a-zA-Z_$][\w$]*)\s*,\s*[a-zA-Z_$][\w$]*\s*\]\s*=\s*createStore\s*\("
)
LEGENDAPP_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*observable\s*\("
)
VUE_REACTIVE_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:reactive|shallowReactive|ref|shallowRef)\s*\("
)
NANOSTORES_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:atom|map|computed|deepMap|persistentAtom|persistentMap)\s*\("
)
NANOSTORES_COMPUTED_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*computed\s*\("
)
SVELTE_RUNES_VAR_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+([a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*\$(?:state|derived)\s*[(<]"
)
SVELTE_STATE_RAW_VAR_DECL_PATTERN = re.compile(
    r"\b(?:let|const|var)\s+([a-zA-Z_$][\w$]*)\s*(?::\s*[^=]+)?\s*=\s*\$state\.raw\s*[(<]"
)
JOTAI_CALLBACK_OPENER_PATTERN = re.compile(r"\batomWithReducer\s*\(")

SHADOW_REALM_IMPORT_PATTERN = re.compile(r"""['"]shadow-realm['"]""")
SHADOW_REALM_USAGE_PATTERN = re.compile(r"\bnew\s+ShadowRealm\s*\(\s*\)")

SYMBOL_METADATA_USAGE_PATTERN = re.compile(r"\bSymbol\.metadata\b")

HMR_BOUNDARY_PATTERN = re.compile(
    r"\b(?:module\.hot\.(?:accept|dispose|decline|invalidate)|"
    r"import\.meta\.hot\.(?:accept|dispose|decline|invalidate|prune))\s*\("
)

TEMPORAL_IMPORT_PATTERN = re.compile(
    r"""['"](?:@js-temporal/polyfill|temporal-polyfill)['"]"""
)
TEMPORAL_USAGE_PATTERN = re.compile(
    r"\bTemporal\.(?:Now|Instant|PlainDate|PlainTime|PlainDateTime|"
    r"PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration|TimeZone|Calendar)\b"
)
TEMPORAL_FACTORY_VAR_DECL_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+([a-zA-Z_$][\w$]*)"
    r"(?:\s*:\s*[^=]+)?\s*=\s*"
    r"Temporal\.(?:Now\.(?:instant|zonedDateTimeISO|plainDateISO|"
    r"plainTimeISO|plainDateTimeISO)\s*\(|"
    r"(?:Instant|PlainDate|PlainTime|PlainDateTime|PlainMonthDay|"
    r"PlainYearMonth|ZonedDateTime|Duration)\.(?:from|fromEpoch[A-Za-z]+)\s*\()"
)
TEMPORAL_TYPED_NAME_PATTERN = re.compile(
    r"\b([a-zA-Z_$][\w$]*)\s*:\s*Temporal\.(?:Instant|PlainDate|PlainTime|"
    r"PlainDateTime|PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration)\b"
)
TEMPORAL_IMMUTABLE_METHODS: frozenset[str] = frozenset(
    {
        "add",
        "subtract",
        "with",
        "withCalendar",
        "withTimeZone",
        "withPlainDate",
        "withPlainTime",
        "until",
        "since",
        "round",
        "equals",
        "compare",
        "toPlainDate",
        "toPlainTime",
        "toPlainDateTime",
        "toPlainYearMonth",
        "toPlainMonthDay",
        "toZonedDateTime",
        "toInstant",
        "toString",
        "toJSON",
        "toLocaleString",
        "valueOf",
        "getISOFields",
        "negated",
        "abs",
        "total",
    }
)


def has_temporal_usage(full_text: str) -> bool:
    if not full_text:
        return False
    if TEMPORAL_IMPORT_PATTERN.search(full_text):
        return True
    return bool(TEMPORAL_USAGE_PATTERN.search(full_text))


def collect_temporal_receivers(full_text: str) -> frozenset[str]:
    if not full_text:
        return frozenset()
    names: set[str] = set()
    for m in TEMPORAL_FACTORY_VAR_DECL_PATTERN.finditer(full_text):
        names.add(m.group(1))
    for m in TEMPORAL_TYPED_NAME_PATTERN.finditer(full_text):
        names.add(m.group(1))
    return frozenset(names)


def is_temporal_chain_call(
    line: str, owner: str | None, receivers: frozenset[str]
) -> bool:
    if owner and owner in receivers:
        return True
    if not line:
        return False
    if "Temporal." in line:
        chain_pattern = re.compile(
            r"Temporal\.(?:Now|Instant|PlainDate|PlainTime|PlainDateTime|"
            r"PlainMonthDay|PlainYearMonth|ZonedDateTime|Duration)\."
        )
        if chain_pattern.search(line):
            return True
    return False


ES2024_STATIC_NON_MUTATING_FACTORIES: frozenset[str] = frozenset(
    {
        "Promise.withResolvers",
        "Promise.try",
        "Array.fromAsync",
        "RegExp.escape",
        "Atomics.pause",
        "Error.isError",
        "Object.groupBy",
        "Map.groupBy",
        "Iterator.from",
    }
)


WEB_API_TYPED_RECEIVER_TYPES: tuple[str, ...] = (
    "URLSearchParams",
    "Headers",
    "FormData",
)

_WEB_API_RECEIVER_PATTERNS: tuple[tuple[str, re.Pattern[str], re.Pattern[str]], ...] = (
    tuple(
        (
            type_name,
            re.compile(
                r"(?:const|let|var|function\s+\w+\s*\(|,|\()\s*"
                r"(?P<name>[a-zA-Z_$][\w$]*)\s*:\s*" + re.escape(type_name) + r"\b"
            ),
            re.compile(
                r"(?:const|let|var)\s+(?P<name>[a-zA-Z_$][\w$]*)\s*"
                r"(?::\s*[^=]+)?\s*=\s*new\s+" + re.escape(type_name) + r"\s*\("
            ),
        )
        for type_name in WEB_API_TYPED_RECEIVER_TYPES
    )
)


def collect_web_api_receivers(full_text: str) -> frozenset[str]:
    if not full_text:
        return frozenset()
    names: set[str] = set()
    for _type_name, typed, constructed in _WEB_API_RECEIVER_PATTERNS:
        for m in typed.finditer(full_text):
            names.add(m.group("name"))
        for m in constructed.finditer(full_text):
            names.add(m.group("name"))
    return frozenset(names)


def is_web_api_receiver(owner: str | None, receivers: frozenset[str]) -> bool:
    if not owner:
        return False
    return owner in receivers


def is_es2024_static_factory(line: str) -> bool:
    if not line:
        return False
    return any(
        f"{factory}(" in line for factory in ES2024_STATIC_NON_MUTATING_FACTORIES
    )


def collect_state_mgmt_receivers(
    full_text: str, file_path: str
) -> dict[str, frozenset[str]]:
    receivers: dict[str, frozenset[str]] = {}
    if not full_text:
        return receivers

    if VALTIO_IMPORT_PATTERN.search(full_text):
        receivers["valtio-proxy"] = frozenset(
            m.group(1) for m in VALTIO_VAR_DECL_PATTERN.finditer(full_text)
        )

    if SOLID_STORE_IMPORT_PATTERN.search(full_text):
        solid_names = {
            m.group(1) for m in SOLID_DIRECT_VAR_DECL_PATTERN.finditer(full_text)
        }
        solid_names.update(
            m.group(1) for m in SOLID_TUPLE_VAR_DECL_PATTERN.finditer(full_text)
        )
        receivers["solid-store"] = frozenset(solid_names)

    if LEGENDAPP_IMPORT_PATTERN.search(full_text):
        receivers["legendapp-state"] = frozenset(
            m.group(1) for m in LEGENDAPP_VAR_DECL_PATTERN.finditer(full_text)
        )

    if VUE_READONLY_IMPORT_PATTERN.search(full_text):
        receivers["vue-reactive"] = frozenset(
            m.group(1) for m in VUE_REACTIVE_VAR_DECL_PATTERN.finditer(full_text)
        )

    if NANOSTORES_IMPORT_PATTERN.search(full_text):
        receivers["nanostores"] = frozenset(
            m.group(1) for m in NANOSTORES_VAR_DECL_PATTERN.finditer(full_text)
        )

    if file_path and file_path.lower().endswith(
        (".svelte", ".svelte.ts", ".svelte.js")
    ):
        receivers["svelte-runes"] = frozenset(
            m.group(1) for m in SVELTE_RUNES_VAR_DECL_PATTERN.finditer(full_text)
        )

    if ANGULAR_SIGNALS_IMPORT_PATTERN.search(full_text):
        receivers["angular-signals"] = frozenset(
            m.group(1) for m in ANGULAR_SIGNAL_VAR_DECL_PATTERN.finditer(full_text)
        )

    if QWIK_SIGNALS_IMPORT_PATTERN.search(full_text):
        receivers["qwik-signals"] = frozenset(
            m.group(1) for m in QWIK_SIGNAL_VAR_DECL_PATTERN.finditer(full_text)
        )

    if PREACT_SIGNALS_IMPORT_PATTERN.search(full_text):
        receivers["preact-signals"] = frozenset(
            m.group(1) for m in PREACT_SIGNAL_VAR_DECL_PATTERN.finditer(full_text)
        )

    if TC39_SIGNALS_IMPORT_PATTERN.search(full_text):
        receivers["tc39-signals"] = frozenset(
            m.group(1) for m in TC39_SIGNAL_VAR_DECL_PATTERN.finditer(full_text)
        )

    return {label: names for label, names in receivers.items() if names}


def hit_uses_receiver(hit_line: str, receivers: frozenset[str]) -> bool:
    if not hit_line or not receivers:
        return False
    for name in receivers:
        if not name:
            continue
        if f"{name}." in hit_line and (
            f" {name}." in hit_line
            or hit_line.startswith(f"{name}.")
            or f"({name}." in hit_line
            or f"\t{name}." in hit_line
            or f"={name}." in hit_line
        ):
            return True
        pattern = re.compile(rf"(?:^|[^\w$]){re.escape(name)}(?:[^\w$.]|$)")
        if pattern.search(hit_line):
            return True
    return False


def skip_extension(file_path: str) -> bool:
    if not file_path:
        return True
    return not file_path.lower().endswith(JS_EXTS)


def skip_path(file_path: str) -> bool:
    if not file_path:
        return True
    p = file_path.lower()
    if any(seg in p for seg in SKIP_SEGMENTS):
        return True
    if any(p.endswith(suf) for suf in SKIP_SUFFIXES):
        return True
    return False


def is_hot_path(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.lower()
    return any(seg in p for seg in HOT_PATH_SEGMENTS)


def is_framework_receiver(line: str, owner: str | None) -> bool:
    if owner and owner in PUSH_FRAMEWORK_RECEIVERS:
        return True
    framework = PUSH_FRAMEWORK_PATTERN.findall(line)
    return bool(framework) and len(framework) == len(PUSH_CALL_PATTERN.findall(line))


def collect_svelte_state_raw_receivers(full_text: str) -> frozenset[str]:
    return frozenset(
        m.group(1) for m in SVELTE_STATE_RAW_VAR_DECL_PATTERN.finditer(full_text)
    )


def is_state_mgmt_filename(file_path: str) -> bool:
    if not file_path:
        return False
    return any(pat.search(file_path) for pat in STATE_MGMT_FILENAME_PATTERNS)


def is_in_state_mgmt_scope(window: str, file_path: str) -> tuple[bool, str | None]:
    if not window:
        return False, None

    if ZUSTAND_PRODUCE_PATTERN.search(window):
        return True, "zustand-produce"
    if IMMER_PRODUCE_PATTERN.search(window):
        return True, "immer-produce"
    if MUTATIVE_CREATE_PATTERN.search(window):
        return True, "mutative-create"
    if REDUX_TOOLKIT_PATTERN.search(window):
        return True, "redux-toolkit"
    if PINIA_STORE_PATTERN.search(window):
        return True, "pinia-define-store"
    if VUEX_MUTATIONS_PATTERN.search(window):
        return True, "vuex-mutations"
    if MOBX_ACTION_PATTERN.search(window):
        return True, "mobx-action"
    if YJS_TYPE_PATTERN.search(window):
        return True, "yjs-crdt"
    if VALTIO_IMPORT_PATTERN.search(window) and VALTIO_PROXY_PATTERN.search(window):
        return True, "valtio-proxy"
    if JOTAI_IMPORT_PATTERN.search(window) and JOTAI_USAGE_PATTERN.search(window):
        return True, "jotai-atom"
    if RECOIL_IMPORT_PATTERN.search(window) and RECOIL_USAGE_PATTERN.search(window):
        return True, "recoil-atom"
    if XSTATE_IMPORT_PATTERN.search(window) and XSTATE_ASSIGN_PATTERN.search(window):
        return True, "xstate-assign"
    if SOLID_STORE_IMPORT_PATTERN.search(window) and SOLID_PRODUCE_PATTERN.search(
        window
    ):
        if SOLID_RECONCILE_PATTERN.search(
            window
        ) and not SOLID_PRODUCE_ONLY_PATTERN.search(window):
            return True, "solid-reconcile"
        return True, "solid-produce"
    if SOLID_STORE_IMPORT_PATTERN.search(window) and SOLID_STORE_USAGE_PATTERN.search(
        window
    ):
        return True, "solid-store"
    if NANOSTORES_IMPORT_PATTERN.search(window) and NANOSTORES_USAGE_PATTERN.search(
        window
    ):
        return True, "nanostores"
    if LEGENDAPP_IMPORT_PATTERN.search(window) and LEGENDAPP_USAGE_PATTERN.search(
        window
    ):
        return True, "legendapp-state"
    if TANSTACK_STORE_IMPORT_PATTERN.search(
        window
    ) and TANSTACK_STORE_USAGE_PATTERN.search(window):
        return True, "tanstack-store"
    if EFFECT_DATA_IMPORT_PATTERN.search(window) and EFFECT_DATA_USAGE_PATTERN.search(
        window
    ):
        return True, "effect-data"
    if VUE_READONLY_IMPORT_PATTERN.search(window) and VUE_READONLY_USAGE_PATTERN.search(
        window
    ):
        return True, "vue-readonly"
    if SVELTE_RUNES_PATTERN.search(window) and file_path.lower().endswith(
        (".svelte", ".svelte.ts", ".svelte.js")
    ):
        return True, "svelte-runes"
    if ANGULAR_SIGNALS_IMPORT_PATTERN.search(
        window
    ) and ANGULAR_SIGNALS_USAGE_PATTERN.search(window):
        return True, "angular-signals"
    if QWIK_SIGNALS_IMPORT_PATTERN.search(window) and QWIK_SIGNALS_USAGE_PATTERN.search(
        window
    ):
        return True, "qwik-signals"
    if PREACT_SIGNALS_IMPORT_PATTERN.search(
        window
    ) and PREACT_SIGNALS_USAGE_PATTERN.search(window):
        return True, "preact-signals"
    if TC39_SIGNALS_IMPORT_PATTERN.search(window) and TC39_SIGNALS_USAGE_PATTERN.search(
        window
    ):
        return True, "tc39-signals"
    if EFFECT_TS_IMPORT_PATTERN.search(window) and (
        EFFECT_TS_GEN_PATTERN.search(window) or EFFECT_TS_REF_PATTERN.search(window)
    ):
        return True, "effect-ts"
    if REACT_19_FORMSTATE_PATTERN.search(window) or REACT_USE_REDUCER_PATTERN.search(
        window
    ):
        return True, "react-19-state-hooks"
    if REACT_SERVER_DIRECTIVE_PATTERN.search(window):
        return True, "react-server-action"
    if SHADOW_REALM_IMPORT_PATTERN.search(window) or SHADOW_REALM_USAGE_PATTERN.search(
        window
    ):
        return True, "shadow-realm"
    if SYMBOL_METADATA_USAGE_PATTERN.search(window):
        return True, "symbol-metadata"
    if HMR_BOUNDARY_PATTERN.search(window):
        return True, "hmr-boundary"

    if is_state_mgmt_filename(file_path):
        return True, "state-mgmt-filename"

    return False, None


PARAM_REASSIGN_ALLOWLIST: frozenset[str] = frozenset(
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


def is_param_reassign_allowed_name(name: str) -> bool:
    return name in PARAM_REASSIGN_ALLOWLIST

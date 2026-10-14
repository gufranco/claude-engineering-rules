from __future__ import annotations

import re

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

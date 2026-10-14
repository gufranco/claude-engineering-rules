from __future__ import annotations

import textwrap

from _case_model import Case, allow, block

ALLOWLIST_CASES: tuple[Case, ...] = (
    allow(
        "allowlist/",
        "store-suffix-allows",
        "*Store.ts auto-allows mutation",
        "write",
        textwrap.dedent("""\
            class CounterStore {
              #count = 0;
              bump() { this.#count += 1 }
            }
        """),
        "/repo/src/business/counterStore.ts",
    ),
    allow(
        "allowlist/",
        "slice-suffix-allows",
        "*Slice.ts auto-allows array.push",
        "edit",
        "state.items.push(action.payload)\n",
        "/repo/src/business/todosSlice.ts",
    ),
    allow(
        "allowlist/",
        "reducer-suffix-allows",
        "*reducer.ts auto-allows assignment",
        "edit",
        "state.count = state.count + 1\n",
        "/repo/src/business/todoReducer.ts",
    ),
    allow(
        "allowlist/",
        "pinia-suffix-allows",
        "*.pinia.ts auto-allows array.push",
        "edit",
        "state.items.push(item)\n",
        "/repo/src/business/items.pinia.ts",
    ),
    allow(
        "allowlist/",
        "machine-suffix-allows",
        "*.machine.ts auto-allows mutation",
        "edit",
        "context.items.push(action.value)\n",
        "/repo/src/business/order.machine.ts",
    ),
)

SUPPRESSION_CASES: tuple[Case, ...] = (
    block(
        "allowlist/sup_",
        "line-marker-blocks",
        "our own line allow marker does not suppress",
        "array.",
        "edit",
        "const items = []\nitems.push(1) // allow-mutation -- legacy hot path\n",
    ),
    block(
        "allowlist/sup_",
        "line-marker-no-justification-blocks",
        "bare allow marker blocks, same as the justified form",
        "array.",
        "edit",
        "const items = []\nitems.push(1) // allow-mutation\n",
    ),
    block(
        "allowlist/sup_",
        "file-marker-blocks",
        "our own file allow marker does not suppress",
        "array.",
        "write",
        "// @allow-mutation -- ported from legacy module\nconst items = []\nitems.push(1)\n",
    ),
)

IMMER_MUTATIVE_CASES: tuple[Case, ...] = (
    allow(
        "allowlist/lib_",
        "immer-produce-allows",
        "Immer produce(draft) callback allows mutation",
        "write",
        textwrap.dedent("""\
            import { produce } from 'immer'
            const state = { items: [] as number[] }
            const next = produce(state, (draft) => {
              draft.items.push(1)
              draft.count = 0
            })
        """),
    ),
    allow(
        "allowlist/lib_",
        "mutative-create-allows",
        "Mutative create(draft) callback allows mutation",
        "write",
        textwrap.dedent("""\
            import { create } from 'mutative'
            const state = { items: [] as number[] }
            const next = create(state, (draft) => {
              draft.items.push(1)
            })
        """),
    ),
    allow(
        "allowlist/lib_",
        "redux-toolkit-allows",
        "Redux Toolkit createSlice reducer allows mutation",
        "write",
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
        "/repo/src/business/todosSlice.ts",
    ),
)

ZUSTAND_JOTAI_CASES: tuple[Case, ...] = (
    allow(
        "allowlist/lib_zus_",
        "zustand-set-produce-allows",
        "Zustand set(produce) callback allows",
        "write",
        textwrap.dedent("""\
            import { create } from 'zustand'
            import { produce } from 'immer'
            export const useStore = create((set: any) => ({
              items: [] as number[],
              add: (x: number) => set(produce((draft: any) => { draft.items.push(x) })),
            }))
        """),
        "/repo/src/business/useStore.ts",
    ),
    allow(
        "allowlist/lib_jot_",
        "jotai-set-allows",
        "Jotai useAtom setter callback allows mutation",
        "write",
        textwrap.dedent("""\
            import { atom, useAtom } from 'jotai'
            const itemsAtom = atom<number[]>([])
            export function useItems() {
              const [items, setItems] = useAtom(itemsAtom)
              return () => setItems((prev) => [...prev, 1])
            }
        """),
        "/repo/src/business/atomStore.ts",
    ),
    allow(
        "allowlist/lib_val_",
        "valtio-proxy-allows",
        "Valtio proxy state mutation allows",
        "write",
        textwrap.dedent("""\
            import { proxy } from 'valtio'
            export const state = proxy({ count: 0 })
            export function bump() { state.count += 1 }
        """),
        "/repo/src/business/proxyStore.ts",
    ),
    allow(
        "allowlist/lib_mob_",
        "mobx-action-allows",
        "MobX action allows mutation",
        "write",
        textwrap.dedent("""\
            import { makeAutoObservable, action } from 'mobx'
            export class Counter {
              count = 0
              constructor() { makeAutoObservable(this) }
              bump = action(() => { this.count += 1 })
            }
        """),
        "/repo/src/business/mobxStore.ts",
    ),
)

DOM_SNIPPETS = (
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
)

DOM_PRELUDE = (
    "const element: any = document.body\nconst el: any = element\n"
    "const input: any = element\nconst shadowRoot: any = element.shadowRoot\n"
    "const store: any = {}\nconst cursor: any = {}\n"
)

DOM_CASES: tuple[Case, ...] = tuple(
    allow(
        "allowlist/dom_",
        f"{i:02d}-allows",
        f"DOM/storage receiver allows: {snippet[:40]}",
        "edit",
        f"{DOM_PRELUDE}{snippet}\n",
    )
    for i, snippet in enumerate(DOM_SNIPPETS, start=1)
)

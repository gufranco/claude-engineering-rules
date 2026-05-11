---
description: Zustand set(produce) callback allows
verdict: allow
payload: write
file: /repo/src/business/useStore.ts
---
import { create } from 'zustand'
import { produce } from 'immer'
export const useStore = create((set: any) => ({
  items: [] as number[],
  add: (x: number) => set(produce((draft: any) => { draft.items.push(x) })),
}))


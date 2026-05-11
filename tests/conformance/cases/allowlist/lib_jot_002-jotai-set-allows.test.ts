---
description: Jotai useAtom setter callback allows mutation
verdict: allow
payload: write
file: /repo/src/business/atomStore.ts
---
import { atom, useAtom } from 'jotai'
const itemsAtom = atom<number[]>([])
export function useItems() {
  const [items, setItems] = useAtom(itemsAtom)
  return () => setItems((prev) => [...prev, 1])
}


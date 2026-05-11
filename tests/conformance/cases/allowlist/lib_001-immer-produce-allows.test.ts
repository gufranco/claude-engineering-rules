---
description: Immer produce(draft) callback allows mutation
verdict: allow
payload: write
---
import { produce } from 'immer'
const state = { items: [] as number[] }
const next = produce(state, (draft) => {
  draft.items.push(1)
  draft.count = 0
})


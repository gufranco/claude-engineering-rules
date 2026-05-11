---
description: Mutative create(draft) callback allows mutation
verdict: allow
payload: write
---
import { create } from 'mutative'
const state = { items: [] as number[] }
const next = create(state, (draft) => {
  draft.items.push(1)
})


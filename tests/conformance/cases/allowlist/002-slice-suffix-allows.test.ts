---
description: *Slice.ts auto-allows array.push
verdict: allow
payload: edit
file: /repo/src/business/todosSlice.ts
---
state.items.push(action.payload)


---
description: *.machine.ts auto-allows mutation
verdict: allow
payload: edit
file: /repo/src/business/order.machine.ts
---
context.items.push(action.value)


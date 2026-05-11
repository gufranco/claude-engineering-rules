---
description: delete-computed blocks
verdict: block
detector: delete-operator
payload: edit
---
const obj: any = { x: 0 }
const arr = [1, 2, 3]
delete obj['x']


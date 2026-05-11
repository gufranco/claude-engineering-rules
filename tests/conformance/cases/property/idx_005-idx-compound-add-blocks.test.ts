---
description: idx-compound-add blocks
verdict: block
detector: property.compound-index
payload: edit
---
const arr = [1, 2, 3]
const obj: any = { x: 0 }
const i = 0
arr[i] += 1


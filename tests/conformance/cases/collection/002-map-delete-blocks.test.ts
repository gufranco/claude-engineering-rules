---
description: Map.delete blocks
verdict: block
detector: collection.
payload: edit
---
const obj = {}
const m = new Map()
m.delete('k')


---
description: WeakSet.delete blocks
verdict: block
detector: collection.
payload: edit
---
const obj = {}
const ws = new WeakSet()
ws.delete(obj)


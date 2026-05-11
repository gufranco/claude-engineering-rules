---
description: WeakSet.add blocks
verdict: block
detector: collection.
payload: edit
---
const obj = {}
const ws = new WeakSet()
ws.add(obj)


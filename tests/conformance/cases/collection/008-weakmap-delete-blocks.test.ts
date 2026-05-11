---
description: WeakMap.delete blocks
verdict: block
detector: collection.
payload: edit
---
const obj = {}
const wm = new WeakMap()
wm.delete(obj)


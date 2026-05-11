---
description: WeakMap.set blocks
verdict: block
detector: collection.
payload: edit
---
const obj = {}
const wm = new WeakMap()
wm.set(obj, 1)


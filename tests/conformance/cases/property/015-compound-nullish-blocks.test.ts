---
description: compound-nullish blocks
verdict: block
detector: property.compound
payload: edit
---
const obj: any = { x: 0 }
const arr = [1, 2, 3]
obj.x ??= 1


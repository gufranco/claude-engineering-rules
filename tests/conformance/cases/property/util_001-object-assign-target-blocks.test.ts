---
description: object-assign-target blocks
verdict: block
detector: object.assign
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Object.assign(target, src)


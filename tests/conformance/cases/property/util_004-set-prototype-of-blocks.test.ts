---
description: set-prototype-of blocks
verdict: block
detector: object.setPrototypeOf
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Object.setPrototypeOf(obj, proto)


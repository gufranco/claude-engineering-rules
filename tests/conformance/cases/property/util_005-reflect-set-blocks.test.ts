---
description: reflect-set blocks
verdict: block
detector: reflect.set
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Reflect.set(obj, 'x', 1)


---
description: reflect-delete blocks
verdict: block
detector: reflect.deleteProperty
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Reflect.deleteProperty(obj, 'x')


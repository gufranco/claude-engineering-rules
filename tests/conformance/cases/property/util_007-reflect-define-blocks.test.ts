---
description: reflect-define blocks
verdict: block
detector: reflect.defineProperty
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Reflect.defineProperty(obj, 'x', { value: 1 })


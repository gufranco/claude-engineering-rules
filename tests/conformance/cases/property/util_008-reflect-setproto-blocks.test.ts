---
description: reflect-setproto blocks
verdict: block
detector: reflect.setPrototypeOf
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Reflect.setPrototypeOf(obj, proto)


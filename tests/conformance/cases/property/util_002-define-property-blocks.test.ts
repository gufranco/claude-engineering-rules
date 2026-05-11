---
description: define-property blocks
verdict: block
detector: object.defineProperty
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Object.defineProperty(obj, 'x', { value: 1 })


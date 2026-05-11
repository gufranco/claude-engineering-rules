---
description: define-properties blocks
verdict: block
detector: object.defineProperties
payload: edit
---
const target: any = {}
const src = { a: 1 }
const obj: any = {}
const proto = null
Object.defineProperties(obj, { x: { value: 1 } })


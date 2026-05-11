---
description: Symbol.hasInstance assignment blocks
verdict: block
detector: symbol-key.assignment
payload: edit
---
const obj: any = {}
obj[Symbol.hasInstance] = () => true


---
description: Symbol.toPrimitive assignment blocks
verdict: block
detector: symbol-key.assignment
payload: edit
---
const obj: any = {}
obj[Symbol.toPrimitive] = () => 0


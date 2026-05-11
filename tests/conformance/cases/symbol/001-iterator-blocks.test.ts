---
description: Symbol.iterator assignment blocks
verdict: block
detector: symbol-key.assignment
payload: edit
---
const obj: any = {}
obj[Symbol.iterator] = function* () { yield 1 }


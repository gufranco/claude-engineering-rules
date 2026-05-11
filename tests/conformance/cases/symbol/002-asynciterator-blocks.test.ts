---
description: Symbol.asyncIterator assignment blocks
verdict: block
detector: symbol-key.assignment
payload: edit
---
const obj: any = {}
obj[Symbol.asyncIterator] = async function* () { yield 1 }


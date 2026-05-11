---
description: Symbol-keyed literal allows
verdict: allow
payload: write
---
const obj = {
  [Symbol.iterator]: function* () { yield 1 }
}


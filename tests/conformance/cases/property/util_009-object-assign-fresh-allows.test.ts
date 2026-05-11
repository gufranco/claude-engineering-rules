---
description: Object.assign with fresh literal target allows
verdict: allow
payload: write
---
const obj = { a: 1 }
const merged = Object.assign({}, obj, { b: 2 })


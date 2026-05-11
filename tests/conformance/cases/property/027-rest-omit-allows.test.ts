---
description: rest-omit pattern allows
verdict: allow
payload: write
---
const obj = { x: 1, y: 2 }
const { x, ...rest } = obj


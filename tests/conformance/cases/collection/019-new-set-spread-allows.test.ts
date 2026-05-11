---
description: new Set with spread allows
verdict: allow
payload: write
---
const a = new Set([1, 2])
const b = new Set([...a, 3])


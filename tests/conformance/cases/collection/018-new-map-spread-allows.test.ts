---
description: new Map with spread allows
verdict: allow
payload: write
---
const a = new Map([['x', 1]])
const b = new Map([...a, ['y', 2]])


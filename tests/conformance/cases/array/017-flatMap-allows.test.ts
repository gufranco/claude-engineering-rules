---
description: array.flatMap allows
verdict: allow
payload: write
---
const items = [1, 2, 3]
const out = items.flatMap((x) => [x, x])


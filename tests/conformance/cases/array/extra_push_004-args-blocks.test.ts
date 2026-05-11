---
description: items.push(...rest) blocks
verdict: block
detector: array.
payload: edit
---
const items: any[] = []
const rest = [9, 9]
const x = 7
items.push(...rest)


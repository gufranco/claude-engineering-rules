---
description: items.splice(0, 0, 'x', 'y') blocks
verdict: block
detector: array.
payload: edit
---
const items = [1, 2, 3]
items.splice(0, 0, 'x', 'y')


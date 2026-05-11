---
description: items.splice(1, 2, 'a') blocks
verdict: block
detector: array.
payload: edit
---
const items = [1, 2, 3]
items.splice(1, 2, 'a')


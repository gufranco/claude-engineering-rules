---
description: our own file allow marker does not suppress
verdict: block
detector: array.
payload: write
---
// @allow-mutation -- ported from legacy module
const items = []
items.push(1)


---
description: our own line allow marker does not suppress
verdict: block
detector: array.
payload: edit
---
const items = []
items.push(1) // allow-mutation -- legacy hot path


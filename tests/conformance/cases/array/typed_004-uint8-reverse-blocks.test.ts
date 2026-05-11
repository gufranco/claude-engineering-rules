---
description: Uint8Array.reverse blocks in business scope
verdict: block
detector: typed-array.
payload: edit
file: /repo/src/business/data.ts
---
const buf = new Uint8Array(4)
buf.reverse()


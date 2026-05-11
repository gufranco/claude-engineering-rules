---
description: Uint8Array.sort blocks in business scope
verdict: block
detector: typed-array.
payload: edit
file: /repo/src/business/data.ts
---
const buf = new Uint8Array(4)
buf.sort()


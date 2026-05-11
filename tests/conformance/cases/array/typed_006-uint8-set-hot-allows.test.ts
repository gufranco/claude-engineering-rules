---
description: Uint8Array.set allows in crypto hot path
verdict: allow
payload: edit
file: /repo/src/crypto/hash.ts
---
const buf = new Uint8Array(4)
buf.set([1, 2])


---
description: Uint8Array.copyWithin allows in crypto hot path
verdict: allow
payload: edit
file: /repo/src/crypto/hash.ts
---
const buf = new Uint8Array(4)
buf.copyWithin(0)


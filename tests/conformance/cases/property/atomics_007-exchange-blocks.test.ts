---
description: Atomics.exchange blocks in business scope
verdict: block
detector: shared-memory.atomics.
payload: edit
file: /repo/src/business/atomic.ts
---
const sab = new SharedArrayBuffer(8)
const buf = new Int32Array(sab)
Atomics.exchange(buf, 0, 1)


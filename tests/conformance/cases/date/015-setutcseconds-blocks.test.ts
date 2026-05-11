---
description: Date.setUTCSeconds blocks
verdict: block
detector: date.
payload: edit
---
const d = new Date()
d.setUTCSeconds(45)


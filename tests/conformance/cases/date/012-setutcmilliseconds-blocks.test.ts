---
description: Date.setUTCMilliseconds blocks
verdict: block
detector: date.
payload: edit
---
const d = new Date()
d.setUTCMilliseconds(500)


---
description: Temporal.add allows
verdict: allow
payload: write
---
const d = Temporal.PlainDate.from('2026-01-01')
const next = d.add({ days: 7 })


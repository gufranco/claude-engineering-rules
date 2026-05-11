---
description: Temporal.with allows
verdict: allow
payload: write
---
const d = Temporal.PlainDate.from('2026-01-01')
const next = d.with({ month: 6 })


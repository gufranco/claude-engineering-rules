---
description: headers-append blocks
verdict: block
detector: web-api.headers.
payload: edit
---
const params = new URLSearchParams()
const headers = new Headers()
const form = new FormData()
headers.append('X', 'y')


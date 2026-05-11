---
description: usp-delete blocks
verdict: block
detector: web-api.url-search-params.
payload: edit
---
const params = new URLSearchParams()
const headers = new Headers()
const form = new FormData()
params.delete('k')


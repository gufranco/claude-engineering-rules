---
description: formdata-set blocks
verdict: block
detector: web-api.form-data.
payload: edit
---
const params = new URLSearchParams()
const headers = new Headers()
const form = new FormData()
form.set('k', 'v')


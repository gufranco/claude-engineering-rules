---
description: formdata-append blocks
verdict: block
detector: web-api.form-data.
payload: edit
---
const params = new URLSearchParams()
const headers = new Headers()
const form = new FormData()
form.append('k', 'v')


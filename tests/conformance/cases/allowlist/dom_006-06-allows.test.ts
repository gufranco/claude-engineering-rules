---
description: DOM/storage receiver allows: el.dataset.x = '1'
verdict: allow
payload: edit
---
const element: any = document.body
const el: any = element
const input: any = element
const shadowRoot: any = element.shadowRoot
const store: any = {}
const cursor: any = {}
el.dataset.x = '1'


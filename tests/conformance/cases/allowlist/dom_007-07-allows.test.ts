---
description: DOM/storage receiver allows: el.scrollTop = 0
verdict: allow
payload: edit
---
const element: any = document.body
const el: any = element
const input: any = element
const shadowRoot: any = element.shadowRoot
const store: any = {}
const cursor: any = {}
el.scrollTop = 0


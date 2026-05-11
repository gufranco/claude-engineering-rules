---
description: DOM/storage receiver allows: element.innerHTML = '<p>x</p>'
verdict: allow
payload: edit
---
const element: any = document.body
const el: any = element
const input: any = element
const shadowRoot: any = element.shadowRoot
const store: any = {}
const cursor: any = {}
element.innerHTML = '<p>x</p>'


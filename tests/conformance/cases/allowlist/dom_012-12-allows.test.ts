---
description: DOM/storage receiver allows: localStorage.setItem('k', 'v')
verdict: allow
payload: edit
---
const element: any = document.body
const el: any = element
const input: any = element
const shadowRoot: any = element.shadowRoot
const store: any = {}
const cursor: any = {}
localStorage.setItem('k', 'v')


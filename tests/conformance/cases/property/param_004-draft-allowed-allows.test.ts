---
description: param reassign 'draft' allows
verdict: allow
payload: write
---
export function update(draft: any) {
  draft = { ...draft, edited: true }
  return draft
}


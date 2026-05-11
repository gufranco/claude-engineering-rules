---
description: param reassign 'acc' allows in reducer
verdict: allow
payload: write
---
export function sum(arr: number[]) {
  return arr.reduce((acc, x) => { acc = acc + x; return acc }, 0)
}


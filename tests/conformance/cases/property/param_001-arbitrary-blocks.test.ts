---
description: param reassignment blocks for non-allowlisted name
verdict: block
detector: param.reassign
payload: write
---
export function handler(input: string) {
  input = input.trim()
  return input
}


---
description: Valtio proxy state mutation allows
verdict: allow
payload: write
file: /repo/src/business/proxyStore.ts
---
import { proxy } from 'valtio'
export const state = proxy({ count: 0 })
export function bump() { state.count += 1 }


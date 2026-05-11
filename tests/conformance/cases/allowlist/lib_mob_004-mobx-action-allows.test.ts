---
description: MobX action allows mutation
verdict: allow
payload: write
file: /repo/src/business/mobxStore.ts
---
import { makeAutoObservable, action } from 'mobx'
export class Counter {
  count = 0
  constructor() { makeAutoObservable(this) }
  bump = action(() => { this.count += 1 })
}


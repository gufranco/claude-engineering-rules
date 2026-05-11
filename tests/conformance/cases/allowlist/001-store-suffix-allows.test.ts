---
description: *Store.ts auto-allows mutation
verdict: allow
payload: write
file: /repo/src/business/counterStore.ts
---
class CounterStore {
  #count = 0;
  bump() { this.#count += 1 }
}


---
description: private field declaration allows
verdict: allow
payload: write
---
class Counter {
  #count = 0;
  current(): number { return this.#count }
}


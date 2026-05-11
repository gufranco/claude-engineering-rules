---
description: private field assign blocks
verdict: block
detector: private-field.
payload: edit
---
class Counter {
  #count = 0;
  bump() { this.#count = 1 }
}


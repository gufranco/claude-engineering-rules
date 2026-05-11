---
description: private field prefix-inc blocks
verdict: block
detector: private-field.
payload: edit
---
class Counter {
  #count = 0;
  bump() { ++this.#count }
}


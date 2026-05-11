---
description: static block with if/else blocks
verdict: block
detector: static-block.mutation
payload: write
---
class Cache {
  static items: Map<string, number>;
  static {
    if (globalThis.testEnv) {
      Cache.items = new Map()
    } else {
      Cache.items = new Map([['default', 0]])
    }
  }
}


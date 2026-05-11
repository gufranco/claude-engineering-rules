---
description: let never reassigned blocks
verdict: block
detector: let.could-be-const
payload: write
---
let value = 1
const doubled = value * 2
export { doubled }


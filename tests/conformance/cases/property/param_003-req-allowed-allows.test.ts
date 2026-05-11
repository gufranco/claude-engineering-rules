---
description: param reassign 'req' allows in middleware
verdict: allow
payload: write
---
export function middleware(req: any) {
  req = { ...req, user: null }
  return req
}


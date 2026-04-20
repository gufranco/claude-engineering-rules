# Security Vulnerability Patterns

Condensed reference for code review and architecture assessment. Each pattern includes CWE mapping, detection guidance, and one vulnerable/safe TypeScript example.

Derived from internal penetration testing knowledge. Used by `/review`, `/assessment`, and `/audit`.

---

## Injection Patterns

### Raw Query Injection
**CWE-89.** A raw database query interpolates user input into the query string. The database treats user input as command structure, not data.

**Detect:** `$queryRawUnsafe`, `$executeRawUnsafe`, string concatenation near SQL keywords, template literals in raw query calls.

```typescript
// VULNERABLE
const users = await prisma.$queryRawUnsafe(
  `SELECT * FROM users WHERE email = '${req.body.email}'`
)

// SAFE — parameterized tagged template
const users = await prisma.$queryRaw`
  SELECT * FROM users WHERE email = ${req.body.email}
`
```

### Second-Order Injection
**CWE-89.** User input is stored safely but retrieved later and interpolated into a raw query. The developer trusts data from the database.

**Detect:** `$queryRawUnsafe` or `$executeRawUnsafe` using values from ORM reads, not from `req.body`.

```typescript
// VULNERABLE — stored username used in raw query
const user = await prisma.user.findUnique({ where: { id: userId } })
const logs = await prisma.$queryRawUnsafe(
  `SELECT * FROM audit_logs WHERE actor = '${user.username}'`
)

// SAFE
const logs = await prisma.$queryRaw`
  SELECT * FROM audit_logs WHERE actor = ${user!.username}
`
```

### ORM Operator Injection
**CWE-943.** User-controlled input passed directly as an ORM filter object. The attacker supplies query operators instead of plain values.

**Detect:** ORM `where` clauses receiving `req.body` or `req.query` directly, `as any` casts on filter objects.

```typescript
// VULNERABLE
const users = await prisma.user.findMany({
  where: req.query.filter as any
})

// SAFE — explicit field extraction
const users = await prisma.user.findMany({
  where: { role: String(req.query.role ?? 'user') }
})
```

### Command Injection via Library
**CWE-78.** User input reaches an OS command through library calls like image conversion, archive handling, or PDF generation.

**Detect:** `child_process.exec` with string interpolation, `execSync` with user-derived arguments, `spawn` with `shell: true`.

```typescript
// VULNERABLE
exec(`convert ${req.body.filename} output.png`, (err, stdout) => {
  res.send(stdout)
})

// SAFE — execFile with argument array, no shell
execFile('convert', [safePath, 'output.png'], (err, stdout) => {
  res.send(stdout)
})
```

---

## Authentication and Session Patterns

### Weak JWT Secret
**CWE-798.** JWT signed with a short, common, or default HMAC secret. An attacker cracks it offline and forges tokens with arbitrary claims.

**Detect:** `jwt.sign` with hardcoded strings, `JWT_SECRET` defaulting to a fallback, secrets shorter than 32 characters.

```typescript
// VULNERABLE
const token = jwt.sign({ userId: user.id }, 'secret')
const token2 = jwt.sign({ userId: user.id }, process.env.JWT_SECRET || 'changeme')

// SAFE
const secret = process.env.JWT_SECRET
if (!secret || secret.length < 32) {
  throw new Error('JWT_SECRET must be set and at least 32 characters')
}
const token = jwt.sign({ userId: user.id }, secret, { expiresIn: '15m' })
```

### Session Cookie Missing Security Flags
**CWE-1004.** Session cookies without HttpOnly (JS can read them), Secure (transmitted over HTTP), or SameSite (sent in cross-site requests).

**Detect:** Cookie configuration missing `httpOnly`, `secure`, or `sameSite` properties.

```typescript
// VULNERABLE
app.use(session({
  cookie: { maxAge: 86400000 }
}))

// SAFE
app.use(session({
  cookie: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
    maxAge: 86400000
  }
}))
```

### Auth State in Mutable Session
**CWE-384.** Multi-step auth flow stores intermediate state in a mutable session shared across concurrent requests. A concurrent request can skip steps.

**Detect:** `req.session.pending*`, `req.session.step`, `req.session.mfa*` set in one handler and read in another.

```typescript
// VULNERABLE — shared mutable session
app.post('/auth/login', async (req, res) => {
  const user = await verifyPassword(req.body.email, req.body.password)
  req.session.pendingUserId = user.id
  res.json({ nextStep: '2fa' })
})

// SAFE — single-use state token
app.post('/auth/login', async (req, res) => {
  const user = await verifyPassword(req.body.email, req.body.password)
  const stateToken = await createAuthState(user.id, '2fa_pending', { ttl: 300 })
  res.json({ stateToken, nextStep: '2fa' })
})
```

### OAuth Code Non-Atomic Consumption
**CWE-367.** OAuth authorization code checked in one query and marked used in a separate query. Concurrent requests both pass the check.

**Detect:** `findFirst` with `usedAt: null` followed by a separate `update` on the same record.

```typescript
// VULNERABLE — two queries, race window between them
const authCode = await prisma.oauthCode.findFirst({
  where: { code, usedAt: null }
})
await prisma.oauthCode.update({
  where: { id: authCode.id },
  data: { usedAt: new Date() }
})

// SAFE — atomic conditional update
const result = await prisma.oauthCode.updateMany({
  where: { code, usedAt: null, expiresAt: { gt: new Date() } },
  data: { usedAt: new Date() }
})
if (result.count === 0) throw new Error('Invalid or already-used code')
```

---

## Authorization Patterns

### IDOR via Sequential IDs
**CWE-639.** Resource endpoint accepts an ID parameter but checks authentication without checking ownership. An attacker enumerates adjacent IDs.

**Detect:** `findUnique`/`findById` with `req.params` but no `userId`/`req.user` in the where clause.

```typescript
// VULNERABLE — no ownership check
app.get('/orders/:id', async (req, res) => {
  const order = await prisma.order.findUnique({
    where: { id: parseInt(req.params.id) }
  })
  res.json(order)
})

// SAFE — ownership in query
app.get('/orders/:id', async (req, res) => {
  const order = await prisma.order.findFirst({
    where: { id: parseInt(req.params.id), userId: req.userId }
  })
  if (!order) return res.status(404).json({ error: 'Not found' })
  res.json(order)
})
```

### Mass Assignment
**CWE-915.** ORM create/update receives `req.body` directly, allowing the client to set privileged fields like `role`, `isAdmin`, `balance`.

**Detect:** `prisma.*.create({ data: req.body })`, `data: { ...req.body }`, spread of user input into ORM data argument.

```typescript
// VULNERABLE
await prisma.user.update({
  where: { id: req.userId },
  data: req.body  // attacker sets role, balance, isAdmin
})

// SAFE — explicit field allowlist
await prisma.user.update({
  where: { id: req.userId },
  data: { displayName: req.body.displayName, bio: req.body.bio }
})
```

---

## Race Condition Patterns

### Read-Modify-Write Race
**CWE-362.** Balance or counter is read, modified in application memory, then written back. Concurrent requests read the same value and overwrite each other.

**Detect:** `findUnique` followed by `update` with computed value, balance arithmetic before save, missing `decrement`/`increment`.

```typescript
// VULNERABLE
const account = await prisma.account.findUnique({ where: { userId } })
if (account.balance < amount) throw new Error('Insufficient funds')
await prisma.account.update({
  where: { userId },
  data: { balance: account.balance - amount }
})

// SAFE — atomic conditional update
const result = await prisma.account.updateMany({
  where: { userId, balance: { gte: amount } },
  data: { balance: { decrement: amount } }
})
if (result.count === 0) throw new Error('Insufficient funds')
```

### Single-Use Token Race (Find-Then-Update)
**CWE-367.** A single-use resource (coupon, bonus, OTP) is checked in one query and marked used in another. Concurrent requests both see it as unused.

**Detect:** `findFirst` with `usedAt: null` or `used: false` followed by a separate `update`.

```typescript
// VULNERABLE
const coupon = await prisma.coupon.findFirst({
  where: { code, usedAt: null }
})
await prisma.coupon.update({
  where: { id: coupon.id },
  data: { usedAt: new Date(), usedBy: userId }
})

// SAFE — atomic updateMany in transaction
await prisma.$transaction(async (tx) => {
  const result = await tx.coupon.updateMany({
    where: { code, usedAt: null },
    data: { usedAt: new Date(), usedBy: userId }
  })
  if (result.count === 0) throw new Error('Already used')
  const coupon = await tx.coupon.findFirst({ where: { code } })
  await tx.account.update({
    where: { userId },
    data: { balance: { increment: coupon!.value } }
  })
})
```

### Transaction Isolation Race (READ COMMITTED)
**CWE-362.** Two transactions under READ COMMITTED each read the same row, compute a new value, and write back. Neither sees the other's uncommitted write.

**Detect:** `$transaction` containing `findUnique` + arithmetic + `update` without `FOR UPDATE` or atomic `decrement`/`increment`.

```typescript
// VULNERABLE — READ COMMITTED allows both to read same balance
await prisma.$transaction(async (tx) => {
  const account = await tx.account.findUnique({ where: { userId } })
  await tx.account.update({
    where: { id: account.id },
    data: { balance: account.balance - amount }
  })
})

// SAFE — SELECT FOR UPDATE serializes access
await prisma.$transaction(async (tx) => {
  const [account] = await tx.$queryRaw<Account[]>`
    SELECT * FROM accounts WHERE user_id = ${userId} FOR UPDATE
  `
  if (account.balance < amount) throw new Error('Insufficient funds')
  await tx.account.update({
    where: { id: account.id },
    data: { balance: account.balance - amount }
  })
})
```

### Lock Fail-Open
**CWE-362.** Distributed lock acquisition error handler returns true or proceeds without the lock. When the lock store is down, the critical section runs unprotected.

**Detect:** Lock acquisition in try/catch where the catch returns `true`, does not rethrow, or calls the protected function.

```typescript
// VULNERABLE — catch returns true, lock becomes decorative
async function tryLock(key: string): Promise<boolean> {
  try {
    await prisma.lock.create({ data: { key } })
    return true
  } catch {
    return true  // typo: should be false
  }
}

// SAFE
async function tryLock(key: string): Promise<boolean> {
  try {
    await prisma.lock.create({ data: { key } })
    return true
  } catch {
    return false
  }
}
```

### Lock TTL Shorter Than Operation
**CWE-362.** Lock expires before the protected operation completes under load. A concurrent request acquires the expired lock and runs simultaneously.

**Detect:** Lock with hardcoded TTL followed by calls to external APIs, batch updates, or expensive queries.

```typescript
// VULNERABLE — 2s TTL, operation takes 5-15s
const lock = await prisma.lock.upsert({
  where: { key: `user-${userId}` },
  create: { key: `user-${userId}`, expiresAt: new Date(Date.now() + 2000) },
  update: { expiresAt: new Date(Date.now() + 2000) }
})
await runExpensiveBatchUpdate(userId)

// SAFE — row-level lock held for the duration of the transaction
await prisma.$transaction(async (tx) => {
  await tx.$queryRaw`SELECT id FROM accounts WHERE user_id = ${userId} FOR UPDATE`
  await runExpensiveBatchUpdate(userId)
})
```

### Missing Idempotency on Jobs/Webhooks
**CWE-841.** Job handler or webhook performs a side effect every invocation without checking if the event was already processed. At-least-once delivery causes double execution.

**Detect:** Job handlers and webhook endpoints that write without checking a dedup key or `processedEvent` table.

```typescript
// VULNERABLE — no dedup, retries double-credit
async function handlePaymentWebhook(event: PaymentEvent) {
  await prisma.account.update({
    where: { userId: event.userId },
    data: { balance: { increment: event.amount } }
  })
}

// SAFE — dedup key in same transaction
async function handlePaymentWebhook(event: PaymentEvent) {
  await prisma.$transaction(async (tx) => {
    await tx.processedEvent.create({ data: { eventId: event.id } })
    await tx.account.update({
      where: { userId: event.userId },
      data: { balance: { increment: event.amount } }
    })
  })
}
```

### Retry Without Idempotency Key
**CWE-841.** HTTP client retries on timeout, but the endpoint runs the write again. The first attempt may have succeeded before the timeout.

**Detect:** `axiosRetry` or retry configuration on POST/PUT/PATCH without `Idempotency-Key` header.

```typescript
// VULNERABLE — retries re-execute the charge
axiosRetry(axios, { retries: 3 })
await axios.post('/charge', { userId, amount })

// SAFE — idempotency key reused across retries
const key = uuidv4()
await axios.post('/charge', { userId, amount }, {
  headers: { 'Idempotency-Key': key }
})
```

---

## Web Security Patterns

### CORS Wildcard with Credentials
**CWE-346.** CORS policy reflects any origin with `credentials: true`. An attacker's page can make credentialed cross-origin requests and read responses.

**Detect:** `cors({ origin: true, credentials: true })`, reflected `Origin` header in `Access-Control-Allow-Origin` with credentials.

```typescript
// VULNERABLE
app.use(cors({ origin: true, credentials: true }))

// SAFE — explicit allowlist
const ALLOWED_ORIGINS = new Set(['https://app.example.com'])
app.use(cors({
  origin: (origin, cb) => {
    if (!origin || ALLOWED_ORIGINS.has(origin)) cb(null, true)
    else cb(new Error('Not allowed'))
  },
  credentials: true
}))
```

### Unvalidated Redirect
**CWE-601.** Redirect destination taken from user input without validating it belongs to the application's domain.

**Detect:** `res.redirect` with `req.query`, `req.body`, or `req.params` as argument.

```typescript
// VULNERABLE
app.get('/login', (req, res) => {
  res.redirect(req.query.next as string || '/dashboard')
})

// SAFE — allowlist of relative paths
const ALLOWED_PATHS = /^\/[a-zA-Z0-9/_-]*$/
app.get('/login', (req, res) => {
  const next = req.query.next as string
  res.redirect(next && ALLOWED_PATHS.test(next) ? next : '/dashboard')
})
```

### GraphQL Missing Depth/Batching Limits
**CWE-400.** No depth or complexity limits on GraphQL queries. Clients can construct deeply nested queries causing O(n^k) database queries, or batch hundreds of operations.

**Detect:** `ApolloServer` without `validationRules`, missing `depthLimit` or `createComplexityLimitRule`.

```typescript
// VULNERABLE
const server = new ApolloServer({ typeDefs, resolvers })

// SAFE
import depthLimit from 'graphql-depth-limit'
import { createComplexityLimitRule } from 'graphql-validation-complexity'

const server = new ApolloServer({
  typeDefs, resolvers,
  validationRules: [depthLimit(10), createComplexityLimitRule(1000)],
  allowBatchedHttpRequests: false,
})
```

---

## Source-to-Sink Analysis Reference

When reviewing code that handles user input, trace from entry points to dangerous sinks. Each sink type requires specific validation.

### Entry Points

`req.query`, `req.body`, `req.params`, `req.headers`, `req.cookies`, `req.files`

### Sink Categories

| Sink | Grep pattern | CWE | Severity |
|------|-------------|-----|----------|
| SQL query | `$queryRaw`, `$executeRaw`, `connection.query(`, `cursor.execute(` | CWE-89 | CRITICAL |
| OS command | `exec(`, `execSync(`, `spawn` with `shell: true`, `os.system(` | CWE-78 | CRITICAL |
| Template engine | `nunjucks.renderString(`, `ejs.render(` with user input, `eval(`, `new Function(` | CWE-1336 | CRITICAL |
| File system | `fs.readFile`, `fs.createReadStream`, `path.join` with user input | CWE-22 | HIGH |
| HTTP client (SSRF) | `fetch(`, `axios(`, `http.get(` with user-controlled URL | CWE-918 | HIGH |
| Redirect | `res.redirect(` with user-controlled destination | CWE-601 | MEDIUM |
| XSS | `res.send(` with unencoded user input, `innerHTML`, `dangerouslySetInnerHTML` | CWE-79 | HIGH |
| Deserialization | `pickle.loads(`, `yaml.load(` without SafeLoader, `JSON.parse(` on untrusted input | CWE-502 | CRITICAL |
| Log injection | `logger.info(` with unsanitized user input containing newlines | CWE-117 | MEDIUM |
| Header injection | `res.setHeader(` with user input containing CRLF | CWE-113 | HIGH |
| Dynamic regex | `new RegExp(` with user input (ReDoS) | CWE-1333 | HIGH |
| Prototype pollution | `Object.assign`, `_.merge`, `deepmerge` with user-controlled objects | CWE-1321 | HIGH |
| NoSQL operator | MongoDB `.find(` with user-controlled filter objects | CWE-943 | CRITICAL |
| CSV formula | Data export functions with values starting with `=`, `+`, `-`, `@` | CWE-1236 | MEDIUM |

### Verification Steps

1. Map all entry points in changed files
2. For each entry point, trace the data flow to any sink above
3. Verify sanitization or validation exists at each transition point
4. Check that custom sanitization functions handle all encoding forms
5. Check for second-order flows: stored data retrieved and used in a later raw query

---

## Financial Platform Security Checklist

When the system handles payments, balances, betting, or e-commerce transactions, check these additional patterns.

### High-Value Targets

| Target | What to check |
|--------|--------------|
| Balance operations | Atomic updates with `decrement`/`increment`, not read-modify-write |
| Payment processing | Idempotency keys on all write endpoints, retry safety |
| Single-use tokens | Atomic consumption (coupon, bonus, referral, promo code) |
| Concurrent transactions | Row-level locking or SERIALIZABLE isolation for financial writes |
| Refund/chargeback | Cannot be triggered twice for the same transaction |
| Spending limits | Enforced atomically, not checked-then-decremented |
| Promotional systems | Bonus stacking prevention, referral abuse detection |

### Verification Approach

For each financial endpoint:

1. Identify the data flow: what reads, what writes, what conditions gate the write
2. Check for atomic operations: is the condition check and the write in the same atomic operation?
3. Check for idempotency: can a network retry or queue redeliver cause double execution?
4. Check for authorization: does the endpoint verify ownership of the financial resource?
5. Check for race conditions: can concurrent requests exploit a window between check and write?

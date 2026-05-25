# Interview Workflows Playbook

Reference for the Buoy Development live coding interview with Matt Salerno. Stack: Node/React + TypeScript. AI/codegen tooling is an explicit signal.

## What They Are Watching For

| Signal | How it shows in your work |
|--------|---------------------------|
| AI/codegen fluency | You drive Claude Code, not the other way around. Visible plans, visible verification |
| Design principles | Service layer, immutability, typed boundaries, fail fast |
| Architecture defaults | DDD aggregates and value objects when business rules exist. Ports and adapters when two or more infra dependencies exist. Idempotency keys on writes. Dedup keys on queue consumers and webhook receivers |
| Testing approach | TDD when feasible, real DB over mocks, AAA pattern, faker for data |
| Architecture fit | Read existing patterns first, match them, name trade-offs out loud |
| Refactoring | Identify smells, propose, execute incrementally, verify behavior unchanged |

## Pre-Session Setup (5 minutes before call)

1. Terminal open with at least three panes: code, tests, dev server
2. Browser tab with the company's GitHub if known
3. Verify `rtk --version` works
4. Verify `gh --version` works
5. Set working directory under `/tmp` or `~/work` for the clone
6. Notepad open for talking-point reminders
7. Close noisy apps. Disable notifications

## Quick Reference Table

| Phase | Skill | Use for |
|-------|-------|---------|
| Safety | `/audit trust` | Untrusted-project safety scan. Offered by `/onboard` Phase 0 via prompt. Verdict: SAFE / SUSPICIOUS / HIGH-RISK / MALICIOUS |
| Onboard | `/onboard` | Whole-repo map, Mermaid diagrams, entry points. Phase 0 prompts for trust decision; `--trust` skips scan, `--verify` runs scan |
| Onboard | `/explain <file>` | Single file with educational depth |
| Onboard | `/zoom-out <file>` | Place narrow code in system context |
| Onboard | `/setup` | Env vars, services, migrations, first boot |
| Plan | `/plan <feature>` | Spec folder, acceptance criteria, file list |
| Plan | `/plan adr <decision>` | Architecture decision with trade-offs |
| Implement | `/tdd <behavior>` | Red-green-refactor cycle for one behavior |
| Implement | `/plan scaffold` | Generate boilerplate from project patterns |
| Test | `/test` | Run suite, coverage, lint |
| Test | `/test perf` | HTTP load test |
| Refactor | `/refactor <area>` | Guided refactor with behavior preservation |
| Debug | `/investigate <bug>` | Hypothesis testing, bounded retries |
| Perf | `/profile <area>` | Find bottleneck, rank by impact |
| Perf | `/benchmark` | Compare against baseline |
| Review | `/review code` | Three-pass code review, 70-category checklist |
| Review | `/review qa` | Test coverage and gap analysis |
| Review | `/review design` | Frontend, a11y, perf, SEO |
| Security | `/audit` | Deps, secrets, OWASP, STRIDE |
| Completeness | `/assessment` | What am I missing audit |
| Ship | `/ship commit` | Semantic commit |
| Ship | `/ship pr` | PR with CI watch |
| After PR | `/respond` | Address reviewer comments. Intent classifier, threaded reply drafts |
| Save state | `/checkpoint save` | Resume across sessions if call breaks |

## Phase 1: Codebase Onboarding (first 5 to 10 minutes)

When the repo arrives:

```bash
git clone <url> ./project && cd project
```

Then in Claude:

1. Pick the right onboarding command:

   | Situation | Command | Behavior |
   |-----------|---------|----------|
   | Take-home or external repo | `/onboard --verify` | Runs trust scan directly. No prompt |
   | Your own repo or trusted source | `/onboard --trust` | Skips trust scan. No prompt |
   | Unsure | `/onboard` | The prompt asks. Default focus is "No, scan it first" |

   The trust scan looks for install-time hooks, credential-theft patterns, exfiltration endpoints, and CI/CD attack patterns. HIGH-RISK and MALICIOUS verdicts block onboarding. For interview take-homes, always pick `--verify`.

2. After the trust decision, `/onboard` produces architecture, entry points, tech stack, conventions, and a Start Here guide with a Safety verdict line near the top.
3. If a specific area is complex, `/explain <file>` for educational depth with diagrams.
4. If you need callers and callees for a function, `/zoom-out <file>`.
5. If the project needs env setup, `/setup` reads `.env.example`, prompts for missing values, detects services, runs migrations.

What to verbalize while AI works: "I'm mapping the codebase first. Claude produces a Mermaid diagram so I can see entry points before I touch anything. Meanwhile I'm reading package.json and the README."

## Phase 2: Planning

For anything beyond a single trivial change:

1. `/plan <feature description>` produces a spec folder with `plan.md`, acceptance criteria, file list, and test scenarios.
2. Review the plan with the interviewer. Adjust scope based on what was discussed.
3. For architecture choices, `/plan adr <decision>` documents the trade-offs.

What to verbalize: "Before I write code, I want acceptance criteria written down. This is how I keep scope honest. Let me show you what Claude proposed and check if it matches what we discussed."

## Phase 3: Implementation

Preferred order:

1. `/tdd <behavior>` for the core behavior. Test fails first, then minimum code, then refactor.
2. For supporting code, direct edits. Read every file before editing. Edit tool over Write.
3. Run formatter, lint, type check, and tests between changes. Not at the end.

Rules to demonstrate visibly:

- Service layer for data access, controllers stay thin
- Zod schemas for validation at boundaries
- `Result<T, E>` or typed errors over throws in domain logic
- `readonly` types on inputs, `as const` on literals
- No `any`, no raw SQL, no `.push()`, no `.sort()` on receiver, no `let` that could be `const`
- Faker for test data, never `"test@example.com"`

What to verbalize: "I want the test to fail first so I know it actually tests what I think it does. Then I implement the minimum that makes it green. Then I look at the implementation again and refactor with the test as a safety net."

## Phase 4: Testing

For every behavior:

| Test type | When |
|-----------|------|
| Integration with real DB | Default for anything that touches persistence |
| Unit | Pure functions only |
| E2E | Full user flow when interviewer asks |

AAA pattern, exact markers:

```typescript
// Arrange
const user = createTestUser();

// Act
const result = await userService.activate(user.id);

// Assert
expect(result.status).toBe('ACTIVE');
```

Specific assertions: `toBe(true)` not `toBeTruthy()`. `toHaveLength(3)` not `length > 0`.

Coverage target: 95%+ for changed and related files.

What to verbalize: "I avoid mocking my own modules. A test that mocks the service it depends on proves the mock works, not the service. Real DB in test container is cheap and catches the real bugs."

## Phase 5: Quality Gates

Before declaring any chunk done:

1. Read the full diff
2. Read every modified function from signature to closing brace
3. Run formatter, lint, type check, test suite, build
4. If any step required code fixes, re-read the diff

For a feature, run `/review code` to get a structured review back.
For a frontend slice, also run `/review design` for a11y, perf, SEO.
Before adding any new third-party dependency that you are unfamiliar with, run `/audit trust` against the package directory.
Before submission, `/assessment` to catch what is missing.

## Phase 6: Polish and Delivery

| Need | Skill |
|------|-------|
| Slow query or endpoint | `/profile <area>` then implement fix then `/benchmark` |
| Security concern | `/audit` |
| Generate commit | `/ship commit` |
| Generate PR with body | `/ship pr` |
| Summary of session work | `/session-log` |

## Common Scenarios With Command Sequences

### A. Add a new API endpoint

1. `/onboard` to map structure
2. `/plan add <verb> /<resource> endpoint with validation, auth, tests`
3. Read two existing endpoints. Match the pattern
4. Implement service first: Zod schema, business logic, ORM calls
5. For write endpoints, add an idempotency key:
   - Accept an `Idempotency-Key` header on POST, PUT, PATCH, DELETE
   - Persist the key with TTL matching the expected retry window
   - Same key with same payload returns the stored result
   - Same key with different payload returns 409
6. Implement controller as thin delegation
7. `/tdd` for each behavior: happy path, validation error, auth failure, not found, idempotency replay
8. `/review code` for self-review
9. `/test` to verify

### B. Fix a bug in unfamiliar code

1. `/investigate <bug description>` for systematic debugging
2. Reproduce the bug. Capture the exact error
3. Write a failing test that proves the bug exists
4. Fix root cause. No workarounds
5. Verify the reproduction now passes
6. Full test suite passes

### C. Add a React component

1. `/zoom-out` on a similar existing component
2. `/plan <component> with a11y, responsive, tests`
3. Implement with TypeScript, `readonly` props, discriminated unions for state
4. Test with React Testing Library, real user events
5. `/review design` for a11y, perf, mobile
6. Verify at 320px viewport minimum

### D. Refactor a complex piece

1. If tests are missing, write them first as a safety net
2. `/refactor <file or function>` for candidate list
3. Pick one smell. Extract or rename
4. Run tests
5. Repeat one step at a time
6. Verify behavior unchanged at every step

### E. Performance issue

1. `/profile <area>` to find the bottleneck
2. `/benchmark` to capture baseline
3. Implement specific optimization
4. `/benchmark` again to verify the win
5. `/test` full suite to verify no regression

## Talking Points While AI Works

Keep narrating. The interviewer cannot see your screen unless you share, and even then they want to hear your reasoning.

- "I'm using Claude to map the codebase first because I do not want to assume the structure"
- "Let me check existing endpoints before I design this one"
- "I want this test to fail first to prove it tests what I think"
- "Before I add this, let me verify the type matches the contract"
- "I chose option A over option B because the team is more likely to be familiar with A. The trade-off is slightly more code"
- "I am not done until lint, type check, tests, and build are all green"

When the interviewer suggests something problematic:

- "I would push back on that because the database mock would pass while the real query fails"
- "Let me show you why I do not use `any` here. The next person changing this loses a guarantee"

## Anti-Patterns to Avoid

| Avoid | Do instead |
|-------|------------|
| Skipping the plan to look fast | Plan visibly. It is the AI fluency signal |
| Mocking the database | Real DB in container, real queries |
| `"test@example.com"` static data | `faker.internet.email()` with seeded generator |
| Writing code without reading existing patterns | Grep first, read two examples, then write |
| Declaring done without running gates | Run formatter, lint, type check, test, build |
| Leaving TODO comments | Complete the implementation now |
| `any` type | `unknown` and narrow, or proper type |
| Raw SQL when ORM exists | ORM methods only. Migrations are the only SQL |
| `.push()`, `.sort()`, mutating Date setters | Spread, `.toSorted()`, Temporal or date-fns |
| `let` that is never reassigned | `const` with ternary or lookup map |
| Direct ORM use in controllers | Service layer between controller and ORM |
| Console.log debugging in final code | Project logger only |
| Onboarding a take-home with `--trust` | Use `--verify` so the scan runs. The scan is read-only and catches install-time exploits |

## When Things Go Wrong

| Problem | Move |
|---------|------|
| Test suite is flaky | Stop. Identify why. Determinism rule. Faker seed, fake clock, isolated ports |
| You cannot reproduce the bug | `/investigate` with explicit hypothesis testing |
| You realize you misread a file | Say so. Re-read. Adjust. Honest correction beats hidden guess |
| You hit a dead end on an approach | Verbalize. Switch. "This approach is creating more friction than I expected. Let me try X instead" |
| Time pressure | State the trade-off. "I am going to ship this with the integration test only. The unit test for the edge case is a follow-up I would write in a real PR" |

## After the Call

1. `/session-log` to capture what was done
2. `/checkpoint save` if work continues across calls
3. Write a brief reflection: what AI tools helped most, what slowed you down

## Hard Rules That Stay On

These apply even mid-interview:

- English only in commits, comments, PR descriptions
- No em dashes, no parentheses in prose, no emojis
- No AI attribution markers anywhere
- No references to plan paths or phases in commits
- Use the project logger, never `console.log` in production code
- Validate at boundaries with Zod, brand IDs, prefer parse over validate
- Idempotency on every write endpoint and queue consumer
- Deduplication keys on webhook receivers and event handlers
- DDD tactical patterns when the domain has invariants beyond CRUD. Hexagonal architecture when the project has two or more infra dependencies

## Final Reminder

Matt's email said the AI tooling is "a plus, not a minus". They want to see you drive the tools. Plans visible, verification visible, decisions named out loud. Speed comes from skipping rework, not from skipping process.

# Reply Templates

Reference library for `/respond`. Each intent-by-decision cell carries at least three good exemplars and three bad exemplars drawn from canonical sources. The templates are guidelines, not strict scripts. Always present the draft for editing before posting.

## Every exemplar here is written to a person, in an inline thread

There is no bot exemplar in this file, because a bot thread receives no reply. It is read, fixed when the finding holds, and resolved. There is also no exemplar for a review body, a conversation comment, or a commit comment, because those channels are answered by the code change and closed by minimizing. [`../../rules/pr-comment-discipline.md`](../../rules/pr-comment-discipline.md) is the rule.

The templates are built on moves only a person can receive: agreeing that someone was right, inviting a clarification, proposing a call, softening a refusal. Aimed anywhere else they address nobody, and a human scrolling the thread later sees a colleague talking to a tool as though it were staff.

## Style Constraints

Every reply must pass these gates before posting.

- Four sentences at most. Reasoning past the ceiling belongs in the code or the pull-request description.
- Lead with what changed or with the answer. The commit SHA in the first sentence when there is one.
- Courtesy in a clause, never a paragraph. No apology, no repeated thanks.
- No restatement of the comment you are answering. The reviewer wrote it and can see it.
- No closing offer of further help. It adds a sentence and no information.
- Vary the opening across replies in the same round.

- No `~/.claude/`, no [`rules/`](../../rules), no [`checklists/`](../../checklists), no [`standards/`](../../standards), no [`skills/`](..) paths.
- No checklist category numbers like "category 17" or "cat 17".
- No phrases that imply a codified internal source: "per our rules", "per our standards", "this violates rule X".
- No em dashes. Use periods, commas, colons, or restructure.
- No parentheses in prose. Use commas or separate sentences. Parens are allowed inside fenced code blocks and inline code spans because GitHub renders those as code.
- No AI-attribution markers. No co-author trailers naming AI tools.
- No banned phrases. See [`CLAUDE.md`](../../CLAUDE.md) "Banned Phrases" for the full list of fluff adjectives, openers, closers, hedges, and transitions.
- Plain ASCII. No emojis or decorative Unicode.

## Cell 1: issue:blocking-bug x implement

### Good

1. "You're right. Pushed `c8e2f1a`. The handler was missing the null check on `order.shippingAddress`. Added a regression test in `tests/orders.spec.ts:142`."
2. "Good catch on the race. The lock release was not atomic with the queue insert. Fix in `a3f2c1d` uses the queue's built-in dedup key. Added a test that replays two concurrent deliveries."
3. "Confirmed. The branch in `parseAmount` returned `undefined` for empty strings instead of zero. Fixed in `9af2b1c` with `it('treats empty amount as zero per PR #4521')`."

### Bad

1. "Done." No SHA, no description, reviewer has to hunt the fix.
2. "Fixed." Same problem as the bare "Done".
3. "It works as intended." The reviewer reported a bug; "intended" denies the report without engaging.

## Cell 2: issue:blocking-bug x push-back

### Good

1. "Looked at this again. The current code handles the empty-array case at `src/parser.ts:78` because `Array.isArray(input) && input.length === 0` falls through to the default branch and returns `[]`. The test `parser.spec.ts:42` covers that path. Did I miss something?"
2. "I think the current code is correct. Observation: `validateUser` returns `Result<User, ValidationError>` and the caller at `src/auth.ts:120` already unwraps with `.match`. Impact: adding a null check there would never trigger because the type forbids null. Want me to encode the invariant in the type so it cannot be missed?"
3. "Couldn't reproduce. Steps I tried: cloned fresh, ran `npm install`, ran `npm test`, all green. Tried with `NODE_ENV=production`, still green. Can you share the exact command or input you used?"

### Bad

1. "No, I'm not going to do that." Bare refusal, no engagement.
2. "You're wrong about the race condition." Attacks the person, not the code.
3. "That's how the parser works." Externalizes, denies the report.

## Cell 3: issue:blocking-security x implement

### Good

1. "You're right. Pushed `b412a09` with input validation at the API boundary. The WebSocket handler was missing the same check, so that path is in there too."
2. "Confirmed. The query was vulnerable to ordering attacks. Fix in `4ce0c3d` switches to parameterized binding via the ORM. Added a fuzz test that runs 1000 generated inputs through the endpoint."
3. "Good catch. The token leaked in the error response on the failure path. Fix in `7d8e2c1` scrubs the token before returning the error envelope. Added a redaction test that asserts the response body cannot contain a substring matching the token pattern."

### Bad

1. "Fixed." Security issue gets the same treatment as a typo.
2. "Patched." No commit, no test mention.
3. "We can fix this in a follow-up." Security fix punted is a hole left open.

## Cell 4: issue:blocking-correctness x clarify

### Good

1. "Want to make sure I am understanding. You are saying that `processBatch` should return early when `items.length === 0`, instead of returning the empty result envelope. Is that right? If yes, I plan to add a guard at line 42. If not, can you point me at the case I am missing?"
2. "I want to be specific. Two readings. First: the comparator is wrong because it returns negative for equal values. Second: the input should be sorted before reaching the comparator. Which is the concern?"
3. "Reading it again. Do you mean the cache should be invalidated on every update, or only on updates that change the indexed fields? The two paths have different cost shapes and I want to pick the right one."

### Bad

1. "What do you mean?" Forces the reviewer to restate without showing your reading.
2. "I do not understand." No attempt to engage with the substance.
3. "?" Lazy.

## Cell 5: issue:architectural x push-back

### Good

1. "Want to land this PR with the current approach. The redesign you are sketching is worth a separate thread because it touches the cache layer too. Happy to draft an ADR if you want to drive the larger change."
2. "I went with the synchronous variant because the cold-start budget is 50ms and the async path adds 15ms minimum on the test fixture. Open to revisiting if we relax the budget or change the runtime. ADR-0042 captures the constraint."
3. "Considered the event-sourced shape. Reason for the current state-based approach: the downstream consumer needs the latest value, not the event log, and a projection rebuild would take roughly 4 minutes against the current data volume. We can revisit when we add the second consumer."

### Bad

1. "Out of scope." Names no blocker, so it reads as a refusal.
2. "Too risky to change now." No specifics.
3. "Maybe later." No commitment, no timeline.

## Cell 6: suggestion x implement

### Good

1. "Good call. Applied in `c8e2f1a`."
2. "Yes, that reads better. Renamed in `a3f2c1d`. Suggested-by: Alice <alice@example.com>"
3. "Took the suggestion. The new helper at `utils/parseAmount.ts:12` deduplicates three call sites. Suggested-by: Bob <bob@example.com>"

### Bad

1. "Done." Too terse for a substantive suggestion.
2. "Will do." Followed by no action.
3. "Will think about it." Kicks the can.

## Cell 7: suggestion x accept-with-modification

### Good

1. "Took a variant in `9af2b1c`. The original suggestion would have eagerly evaluated the loader; I used a lazy `() => loader()` instead to keep the cold-path cost low."
2. "Applied a smaller version in `4ce0c3d`. Kept the extraction you suggested but skipped the rename because the broader codebase still uses the old name."
3. "Yes, with one change. Used `Map` instead of the suggested `Record<string, T>` because the keys are non-string. Fix in `b412a09`."

### Bad

1. "Sort of." Vague.
2. "Done." Does not describe the modification.
3. "Mostly." Forces the reviewer to compare and diff.

## Cell 8: suggestion x push-back

### Good

1. "Considered that. Went with the current approach because the suggested helper would add a dependency on `@aws-sdk/client-s3` to a module that otherwise has no AWS coupling. Open to changing if the boundary is acceptable to you."
2. "I think the current shape is right. Observation: the API surface exposes one method per entity. Impact: collapsing into a generic `query<T>(filter)` would lose the typed return values that callers rely on. Trade-off you may be optimizing for differently: ease of extension. WDYT?"
3. "Looked at the alternative. The suggested pattern works at lower scales but the cache lookup is on the hot path and the alternative adds a hash operation per request, around 0.4 microseconds in the benchmark. Sticking with the array scan because the keyset is bounded to under 20 entries."

### Bad

1. "I disagree." No reasoning.
2. "Not going to change this." Closes the conversation.
3. "Your suggestion is wrong." Attacks the person.

## Cell 9: question x ack

### Good

1. "The retry happens in the queue consumer, not in the handler. The handler enqueues and returns 202. The consumer retries with exponential backoff up to 5 attempts."
2. "It is intentional. The constraint comes from the third-party API, which returns a 429 on any concurrent request. We serialize at the consumer."
3. "No special reason. I copied the pattern from `src/services/orderService.ts`. Happy to align if that file should change too."

### Bad

1. "Yes." The question deserves substance.
2. "It is what it is." Dismissive.
3. "I do not remember." Acceptable as a starting point but should be followed by checking the history.

## Cell 10: clarification-request x ack

### Good

1. "The flag controls whether new orders default to the legacy pricing engine. It exists because the migration is partial: some merchants are on the new engine, some are not. We will remove it after the migration finishes in Q3."
2. "The middleware is there to canonicalize emails before they hit the lookup. Without it, `User@Example.com` and `user@example.com` would create two rows for the same person. The unique index alone does not catch the case because PostgreSQL treats those as distinct."
3. "It is the retry budget. We allow 3 retries per logical request across the chain. The variable tracks how many remain. When it hits zero, the consumer sends to DLQ."

### Bad

1. "It does what it says." No clarification at all.
2. "Long story." Avoids the explanation.
3. "Read the docs." Rude, especially if no docs exist.

## Cell 11: nitpick x implement

### Good

1. "Fixed in `c8e2f1a`."
2. "Renamed. `a3f2c1d`."
3. "Applied across the file in `9af2b1c`."

### Bad

1. Silent push without a reply. The reviewer cannot tell if the nit was seen.
2. "I had to think about this one." Overstates a trivial nit.
3. "Thanks for pointing this out!" Too effusive for a nit; reads as fake.

## Cell 12: nitpick x push-back

### Good

1. "Sticking with the current name for consistency with `OrderService.findById`. Happy to change both if we want the new convention."
2. "Project convention is camelCase for module-private helpers per the lint config. The suggested name would trigger the lint rule."
3. "Could go either way. Leaving as is to avoid blowing up the diff. Will pick up the rename in the next pass through this file."

### Bad

1. "Not going to change this." Too curt for a nit, escalates needlessly.
2. "Nit, but no." Passive-aggressive.
3. "Why does this matter?" Rhetorical, dismissive.

## Cell 13: chore:out-of-scope x implement

The default for this cell. A change a reviewer calls out of scope is usually small enough to make, and making it is cheaper than the round trip about whether to make it.

### Good

1. "Fixed in `c8e2f1a`. It was two lines next to the change anyway."
2. "Good catch, done in `a3f2c1d`. The same shape was wrong at `src/orders.ts:78`, so that one is in there too."
3. "Applied in `9af2b1c`."

### Bad

1. "Filed as `ENG-1234`. Out of scope for this PR." A ticket instead of a fix that was available.
2. "Will pick it up in the follow-up." The follow-up is this pull request.
3. "Out of scope." The reviewer now has to decide whether to argue.

## Cell 13b: chore:out-of-scope x push-back

Only when the fix is blocked outside this change. Name the blocker and create nothing.

### Good

1. "Cannot land here. The column is written by the billing service, so the change has to ship with their release."
2. "This one needs the auth middleware, which another team owns. Raising it with them rather than changing it under them."
3. "Blocked on the `v3` client release. Everything else in the thread is in `c8e2f1a`."

### Bad

1. "Filed `ENG-1235` to track it." A tracker item the reviewer cannot act on.
2. "Not now." No blocker named, so it reads as a refusal.
3. "Out of scope, will follow up." Two deferrals in one sentence.

## Cell 14: todo x implement

A reviewer asking for a marker is asking for the work. Do the work. Markers recording debt are banned by the comments policy in [`../../rules/code-style.md`](../../rules/code-style.md).

### Good

1. "Done in `c8e2f1a` rather than left as a note. The retry path was shorter than the comment would have been."
2. "Implemented in `a3f2c1d`. The fallback now retries twice before the direct upload."
3. "Fixed in `9af2b1c`."

### Bad

1. "Added a marker at `src/upload.ts:42` and filed `ENG-1237`." Two artifacts, no fix.
2. "Will remember to do this." Memory is not a plan.
3. "Left a note for later." Later does not arrive.

## Cell 15: praise x ack

### Good

1. No reply. Silent resolve. Optionally add a thumbs-up reaction on GitHub.
2. "Thanks for noticing the cleanup. The factoring took longer than expected because the call sites had subtle differences."
3. "Took me three tries to get the shape right. Glad it landed."

### Bad

1. "Thanks!" on every praise comment. Microsoft research shows praise replies add work without value; default to no reply.
2. "Thank you for the kind words, this was indeed a tricky refactor I spent considerable effort on." Overlong, reads as fishing for more praise.
3. "Glad you like it." Technically fine but adds noise when a silent resolve would do.

## Cells 16 and 17 are gone

There is no exemplar for a reply to a bot, because no reply is published to a bot. Read the thread, apply the failure-scenario gate, fix what survives, resolve the thread, move on. The commit is the record.

## Cell 18: conflict between two reviewers

### Good

1. "@alice and @bob: you are asking for opposite things on this line. Alice wants the helper extracted; Bob wants the inline form. I have a slight preference for the helper because the same shape appears at `src/orders.ts:78`. Can you two align? Happy with either."
2. "@alice: you flagged this as a blocking issue. @bob approved with the current shape. Want to make sure I understand the conflict. Is the disagreement on the API shape or on the implementation?"
3. "@tech-lead: alice and bob disagree on the migration approach. Both options are sketched in `docs/migration-options.md`. We have gone two rounds with no movement. Picking a direction?"

### Bad

1. Silently revert Bob's change to take Alice's side. Escalates without acknowledging the disagreement.
2. "I will let you two figure it out." Forces the reviewers to coordinate without your input.
3. Re-request review without addressing the conflict. Kicks the can to the next reviewer.

## Cell 19: synchronous-recommended

When a thread has cycled twice without convergence, propose a call.

### Good

1. "We have gone around twice on this. Want to grab 15 minutes to walk through the code together? The async thread is missing the context I need to explain the constraint."
2. "Two passes and we are not converging. Free for a call any time this afternoon? I will write up the agreed outcome here after."
3. "Suggesting we switch to sync. The thread is missing the architectural context that would make the trade-off obvious. Open to a Zoom or a quick Slack DM."

### Bad

1. "Let's discuss offline." Breaks the audit trail with no follow-up note.
2. Continue the thread with another 5-paragraph reply. Past two rounds, more async usually hurts.
3. Stop responding. Leaves the thread open and the reviewer guessing.

## Status Update on Stale PR

A pull request with no thread to reply in has no comment surface. After seven idle days the status goes in the description, or the pull request closes.

### Good

1. Edit the description: "Blocked on the schema review. Rebase lands once that does." Then re-request review.
2. Close it: "The approach did not survive the queue-design discussion." A fresh pull request carries the new shape.
3. Re-request review after confirming the old CI failure was a flake and the rerun is green.

### Bad

1. A conversation comment saying "Bump." No thread, no information, and a banned surface.
2. A conversation comment summarizing what changed. The description is where a reviewer looks.
3. Letting it rot. It sits in someone's queue.

## Re-Request Review

After a batch of fixes lands.

### Good

1. The re-request on its own. What changed since the last pass is already in the description and in each thread's reply.
2. The re-request plus one description line naming the two commits that answer the blocking threads.
3. The re-request after every thread is either replied to or resolved, so the reviewer opens a clean page.

### Bad

1. A conversation comment listing what changed. Banned surface, and the description already holds it.
2. A re-request while three threads are still unanswered. The reviewer re-reads the whole diff.
3. A re-request naming a ticket as the answer to an architectural thread. The thread wanted a decision, not a link.

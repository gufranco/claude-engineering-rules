# Reply Templates

Reference library for `/respond`. Each intent-by-decision cell carries at least three good exemplars and three bad exemplars drawn from canonical sources. The templates are guidelines, not strict scripts. Always present the draft for editing before posting.

## Style Constraints

Every reply must pass these gates before posting.

- No `~/.claude/`, no [`rules/`](rules), no [`checklists/`](checklists), no [`standards/`](standards), no [`skills/`](skills) paths.
- No checklist category numbers like "category 17" or "cat 17".
- No phrases that imply a codified internal source: "per our rules", "per our standards", "this violates rule X".
- No em dashes. Use periods, commas, colons, or restructure.
- No parentheses in prose. Use commas or separate sentences. Parens are allowed inside fenced code blocks and inline code spans because GitHub renders those as code.
- No AI-attribution markers. No co-author trailers naming AI tools.
- No banned phrases: `robust`, `comprehensive`, `seamless`, `elegant`, `powerful`, `streamlined`, "Great question!", "Hope this helps", "Let me know if".
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
2. "I think the current code is correct. Observation: `validateUser` returns `Result<User, ValidationError>` and the caller at `src/auth.ts:120` already unwraps with `.match`. Impact: adding a null check there would never trigger because the type forbids null. Want me to add a comment explaining the invariant?"
3. "Couldn't reproduce. Steps I tried: cloned fresh, ran `npm install`, ran `npm test`, all green. Tried with `NODE_ENV=production`, still green. Can you share the exact command or input you used?"

### Bad

1. "No, I'm not going to do that." Bare refusal, no engagement.
2. "You're wrong about the race condition." Attacks the person, not the code.
3. "That's how the parser works." Externalizes, denies the report.

## Cell 3: issue:blocking-security x implement

### Good

1. "You're right. Pushed `b412a09` with input validation at the API boundary. The same check is missing on the WebSocket handler; filed `ENG-1234` to close that path too."
2. "Confirmed. The query was vulnerable to ordering attacks. Fix in `4ce0c3d` switches to parameterized binding via the ORM. Added a fuzz test that runs 1000 generated inputs through the endpoint."
3. "Good catch. The token leaked in the error response on the failure path. Fix in `7d8e2c1` scrubs the token before returning the error envelope. Added a redaction test that asserts the response body cannot contain a substring matching the token pattern."

### Bad

1. "Fixed." Security issue gets the same treatment as a typo.
2. "Patched." No link, no follow-up, no test mention.
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

1. "Out of scope." Without a follow-up plan, this defers the conversation rather than addressing it.
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

## Cell 13: chore:out-of-scope x defer

### Good

1. "Filed as `ENG-1234`. Out of scope for this PR. The change touches the auth middleware which is owned by another team."
2. "Good observation. Filed `ENG-1235` and linked to this PR. Want to keep this PR focused on the migration."
3. "Tracked in `ENG-1236`. Will pick it up in the follow-up that touches the same module."

### Bad

1. "Will do later." No ticket, becomes permanent debt.
2. "Out of scope." Without a tracker link, the reader cannot follow up.
3. "Not now." No plan.

## Cell 14: todo x ack

### Good

1. "Added `TODO(debt): retry the upload twice before falling back to S3 direct upload` at `src/upload.ts:42`. Filed `ENG-1237` to track the proper fix."
2. "Added a `TODO(debt)` comment at the call site with a link to `ENG-1238`."
3. "Will leave a TODO and file the ticket. The TODO is in `9af2b1c`."

### Bad

1. "Sure." No concrete TODO added.
2. "Added a TODO." No ticket reference.
3. "Will remember to do this." Memory is not a ticket tracker.

## Cell 15: praise x ack

### Good

1. No reply. Silent resolve. Optionally add a thumbs-up reaction on GitHub.
2. "Thanks for noticing the cleanup. The factoring took longer than expected because the call sites had subtle differences."
3. "Took me three tries to get the shape right. Glad it landed."

### Bad

1. "Thanks!" on every praise comment. Microsoft research shows praise replies add work without value; default to no reply.
2. "Thank you for the kind words, this was indeed a tricky refactor I spent considerable effort on." Overlong, reads as fishing for more praise.
3. "Glad you like it." Technically fine but adds noise when a silent resolve would do.

## Cell 16: AI bot x dismiss

### Good

1. "Not applicable: project ban on `lodash`. See `CONTRIBUTING.md`. Resolving."
2. "Disagree: the try/catch would swallow the error we propagate to the DLQ. Resolving."
3. "Already validated upstream in `src/middleware/validate.ts:42`. Resolving."

### Bad

1. Resolve without a reply. Leaves the bot with no signal to learn from.
2. "Wrong." Too curt; the bot learns better from reasoning.
3. A long argument with the bot about why it is wrong. The bot is not the audience; the human reviewer scanning the PR is.

## Cell 17: AI bot x implement

### Good

1. "Good catch. Pushed `c8e2f1a`."
2. "Applied. The fix is in `a3f2c1d` along with a regression test."
3. "Right call. Renamed in `9af2b1c` for clarity."

### Bad

1. Apply the suggestion without verifying it makes sense. The drive-by accept anti-pattern.
2. "Thank you for this insight, your suggestion was extremely valuable and I have incorporated it into the latest revision after careful consideration." Fluff, reads as AI-generated.
3. Credit the bot in a commit author trailer. Prohibited by personal rules and by the runtime hook.

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

When a PR has been idle for more than 7 days, push a status update or close.

### Good

1. "Status: blocked on the schema review. Will push the rebase once that lands. Estimated unblock: Friday."
2. "Closing this. The approach didn't survive the queue-design discussion. Will open a fresh PR with the new shape next week."
3. "Bumping. The CI failure from last week was a flaky integration test, not a real issue. Retried, all green. PTAL @alice."

### Bad

1. "Bump." No information, reads as nagging.
2. Silently force-push and re-request review. Drops the prior context.
3. Let the PR rot. Wastes everyone's queue space.

## Re-Request Review

After a batch of fixes lands.

### Good

1. "PTAL @alice. Since your last pass: extracted the validator, added the missing test, renamed per the nit thread."
2. "PTAL. Addressed all 7 comments. SHAs in each thread."
3. "Ready for another look. The architectural concern is deferred to ENG-1234. Everything else is in the diff."

### Bad

1. "Done." No list of what changed.
2. "All fixed." No detail.
3. Re-request without comment. Forces the reviewer to re-read the entire diff.

## Source Notes

The good and bad exemplars draw on patterns documented in Google eng-practices "Handling reviewer comments", Tidyverse code review principles, GitLab handbook code review, Lara Hogan's Feedback Equation, the Conventional Comments specification, Greiler's "Respectful and constructive feedback", mtlynch on human code reviews, Pragmatic Engineer on PR cycle time, Tatham's antipatterns catalogue, and CodeRabbit best-practice docs. Phrasings are independently authored. Industry shorthand like `LGTM`, `PTAL`, `WDYT`, `NIT`, and `RFC` is used as is because those tokens are community standards.

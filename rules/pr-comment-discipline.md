# Pull Request Comment Discipline

The only comment published on a pull request is a reply inside a thread a person opened.

| Surface | Rule |
|---|---|
| Reply in a human's thread | Allowed. Four sentences max, lead with what changed |
| Review summary body | Never written; submit reviews with an empty body |
| Conversation or commit comment | Never written; fix the code and say it in the commit |
| Bot thread, any channel | Never replied to; fix a real finding, then resolve or minimize |
| New inline thread | Only on someone else's PR, to name a defect at its line |

- Every channel is still fetched, classified, and acted on; only the answer shape changed.
- Fix it now: never a ticket, follow-up PR, or code marker in place of a fix. A fix blocked outside the change gets one sentence naming the blocker.
- No restating the comment, no closing offer, no apology.

Full rule, examples, and rationale: [`standards/pr-comment-discipline.md`](../standards/pr-comment-discipline.md). Read it before posting, replying, or resolving anything on a pull request.

## Enforcement

Enforced by: [`../hooks/pr-comment-discipline.py`](../hooks/pr-comment-discipline.py).
Enforced by: [`../hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py).
Enforced by: [`../hooks/found-fix-rationalization-blocker.py`](../hooks/found-fix-rationalization-blocker.py).

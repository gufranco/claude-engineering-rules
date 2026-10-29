# AI Review Convergence

Applies when a PR carries automated review comments. Zero bot comments is unreachable; the goal is a round with no verified failure.

- Fix a bot comment only after writing a concrete failure scenario and checking it against the code; otherwise resolve with no change and no reply. Expect a 40 to 60 percent decline rate.
- A review-response commit touches only the flagged lines.
- When a round yields no verified fix, stop and recommend merge; never request another pass to confirm.
- Judge human reviewers on the merits, not by the gate. Verify the fix before replying and name the commit.

Full rule, examples, and rationale: [`standards/ai-review-convergence.md`](../standards/ai-review-convergence.md). Read it before working a batch of bot review comments.

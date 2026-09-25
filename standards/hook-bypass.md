# Hook Bypass Discipline

Full text of the Hook Bypass Discipline section of the global instructions. [`CLAUDE.md`](../CLAUDE.md) carries the always-loaded summary.

A blocking hook fires because a rule was violated. The default response is to change the code, never to silence the hook.

- **Engage a bypass at most once per session, per hook.** Reaching for the same bypass a second time means the rule is being fought rather than a false positive being cleared. Stop and ask the user instead.
- **A bypass covers one specific false positive, never a category.** Approval to bypass for one case does not carry to the next file, the next batch, or a related case. Re-derive the justification each time or do not bypass.
- **Narrow approval stays narrow.** When the user approves an exception, apply it to exactly what they approved. "Write JSDoc on public functions" is not permission to add inline body comments, schema comments, or commentary anywhere else.
- **Name the false positive out loud before bypassing.** State which specific pattern the hook misread and why the code is correct as written. If that sentence cannot be written honestly, the hook is right.
- **Clear bypasses when the task that justified them ends.** A TTL bypass left running silences the rule for unrelated work later in the session.

The failure mode this prevents: a bypass engaged once for a real reason, then re-engaged reflexively at the start of every subsequent batch until the rule is effectively off.

**When the check is right and the case is still an exception, the answer is a waiver, not a bypass.** These answer different questions. A bypass says the check is wrong about this input; a waiver says the rule is right and this case is the exception. A bypass silences everything in its window and is reviewed by nobody. A waiver is scoped to one named case, approved by a person, recorded where reviewers read it, and carries the condition that reopens it. Reaching for a bypass because a rule genuinely does not fit is the miscategorization that turns a design conversation into a silenced run. See [`rules/deviation-waivers.md`](../rules/deviation-waivers.md).

**A blocked call is also a signal about the payload, not only about the hook.** The block runs nothing, so the whole edit is unmade, including the parts before the offending one. And the first hook to block ends the chain, so hooks registered after it never saw the content: clearing one block can surface a second on the same payload. Re-read the target rather than re-running only the fragment that tripped. The same applies to shell state: when the blocked command was itself setting up what its later part consumed, such as staging an index before a commit, the retry repeats the whole command. Retrying only the tail runs it against whatever state an earlier call happened to leave behind.

**A checker that searches for banned content will block itself.** Hooks scan the raw command string before the shell runs it, so a grep whose pattern spells out an em dash, an attribution line, or any other banned literal is a violation by inspection, and the search never executes. Nothing partially ran; the whole call was refused. Build the literal from fragments instead, `"co-auth" + "ored-by"` or `chr(0x2014)`, and the audit runs while the rule stays enforced. This applies to every audit script, lint helper and one-off verification grep aimed at the very patterns the hooks defend.

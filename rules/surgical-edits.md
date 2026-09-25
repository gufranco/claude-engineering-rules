# Surgical Edits

Every changed line must trace directly to the user's request. If a line cannot be justified by the request, do not change it.

- Never improve, refactor, rename, reformat, or reorder adjacent code the request did not name. Report opportunities instead of acting on them.
- Match existing style unless a rule forbids it.
- Remove what your change orphaned: imports, variables, functions. Leave dead code, style violations, and adjacent bugs that predate your change, and surface them.
- Diff self-test per line: requested, or cleanup my change required? Otherwise revert.
- Rules govern lines you write or touch; never retrofit untouched code.
- Completeness sets depth inside the scope; this rule sets its width.
- A request too narrow to be safe gets a question, never a unilateral expansion.
- Exceptions: an explicit refactor or sweep request, a planned migration, a named anti-pattern removal, and any verification-surface finding, which is always in scope.

Full rule, examples, and rationale: [`standards/surgical-edits.md`](../standards/surgical-edits.md). Read it before a change that tempts you into neighbouring code.

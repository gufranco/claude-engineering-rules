# Normative Keywords

## Core Rule

Every normative statement in `~/.claude/` uses one of the keywords defined below. The keyword set is taken from BCP 14, which bundles RFC 2119 and RFC 8174. Lowercase is the default register. Uppercase is opt-in for genuinely critical rules where misreading the obligation would cause real harm.

This rule defines the keyword vocabulary. Sentence-level precision rules live in [`writing-precision.md`](writing-precision.md). The two rules compose: writing-precision governs how a sentence is built; this rule governs which obligation word goes in it.

## Glossary

| Keyword | Meaning | Equivalent forms |
|---------|---------|-----------------|
| must | Absolute requirement. Non-compliance is a violation | required, shall |
| must not | Absolute prohibition | shall not |
| should | Preferred default. Valid reasons to deviate exist, and a reader who deviates accepts the implications | recommended |
| should not | Behavior may be acceptable in particular cases. A reader who chooses it accepts the implications | not recommended |
| may | Truly optional. Include or omit without consequence | optional |
| never | Categorical prohibition on an action. Same force as `must not` for verbs | n/a |
| always | Categorical requirement on an action. Same force as `must` for verbs | n/a |

Pick exactly one keyword per statement. Phrases like "the handler must always validate" are redundant; pick `must` or `always`, not both.

## Lowercase Primary

Lowercase keywords are the default register for every rule, standard, skill, agent, hook docstring, and README in `~/.claude/`. A reader does not need to translate BCP 14 codes to understand the obligation. The keyword IS the obligation.

Lowercase also keeps the visual field clean. A file with 200 normative statements would overwhelm a reader if every keyword were uppercase. The reader stops scanning and starts skipping.

## Uppercase Opt-In

Uppercase is permitted for genuinely critical statements where misreading would cause real harm. Concrete criteria:

| Category | Example |
|----------|---------|
| Security boundary | "Required env vars MUST be documented in `.env.example`." [`security.md`](security.md):7 |
| Correctness invariant | "Every test MUST use these exact Arrange-Act-Assert comments." [`testing.md`](testing.md):26 |
| Data integrity | "Every mutating operation MUST be safe to run twice with the same input." Hypothetical illustration |
| Irreversibility | "Migrations MUST be safe to run more than once." Paraphrased from the migration idempotency rule |
| Verbatim citation | Quoting an RFC, standard, or external authority that already uses uppercase. [`../standards/identifiers.md`](../standards/identifiers.md):90 |

When in doubt, lowercase. A reader who finds uppercase in a rule file has a right to expect that the rule names a load-bearing requirement. Reaching for uppercase too often dilutes the signal.

## Boilerplate Citation

BCP 14 expects a boilerplate sentence in every document that adopts the keywords. This rule replaces that boilerplate with a single citation here:

> The keywords in this rule paraphrase the definitions in BCP 14, which bundles RFC 2119 and RFC 8174. The strict BCP 14 reading applies to uppercase forms. Lowercase carries the same semantics in `~/.claude/` files but does not invoke the formal BCP 14 framework. Files in `~/.claude/` do not include a per-file BCP 14 boilerplate.

This keeps the convention traceable to its source without turning every rule file into an RFC document.

## Examples

### Required

| Bad | Good |
|-----|------|
| You should validate inputs at the boundary. | You must validate inputs at the boundary. |
| Tests should cover edge cases. | Tests must cover null, empty string, zero, max length. |
| Should the migration be idempotent. | Every migration must be safe to run more than once. |

### Preferred Default

| Bad | Good |
|-----|------|
| You may want to consider using a transaction. | Use a transaction when writes touch multiple tables. Deviation is acceptable when the second write is purely informational. |
| It is recommended to use Zod. | Use Zod for validation at system boundaries. Other parsers are acceptable when Zod cannot express the schema. |

### Optional

| Bad | Good |
|-----|------|
| You can add a comment if you want. | A comment is optional. Add one when the WHY is non-obvious. |
| The helper is available if needed. | Use of the helper is optional. The default path stays the same. |

## Cross-References

| Rule | Why |
|------|-----|
| [`writing-precision.md`](writing-precision.md) "Eliminate weasel words" | Removes escape-hatch language so the keyword in this rule carries the full obligation |
| [`writing-precision.md`](writing-precision.md) "Tone Calibration" | Defines the friendly-direct register; this rule defines the obligation vocabulary used within that register |
| [`code-style.md`](code-style.md) "Comments Policy" | The lowercase normative-keyword principle extends to code comments |
| [`smart-questions.md`](smart-questions.md) | Question and report wording follows the same vocabulary |

## Source

- RFC 2119: <https://www.rfc-editor.org/rfc/rfc2119>
- RFC 8174: <https://www.rfc-editor.org/rfc/rfc8174>
- BCP 14 index: <https://www.rfc-editor.org/info/bcp14>

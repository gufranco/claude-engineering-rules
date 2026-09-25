# Anti-Slop

Every sentence must change what the reader knows, decides, or does. Slop is text whose shape was chosen before its content, and it is banned from every artifact.

## The Three Deciding Tests

| Test | Question |
|---|---|
| Substitution | Could this sentence appear verbatim in a document about a different subject? Then replace it with the specific claim |
| Deletion | Remove it. Does the reader's next action change? If not, it was filler |
| Shape | Did the content choose this structure, or did the structure get filled? |

## Banned Shapes

| Shape | Write instead |
|---|---|
| Negative parallelism and corrective reframe, `not just X, but Y` | The positive claim alone |
| Rule of three chosen for rhythm | Only the items that are true |
| Throat-clearing, false concession, lazy emphasis | The claim itself, made strong enough |
| Trailing recap, `In short` | End when the point lands |
| Compulsive qualification | Name the exception or drop the hedge |
| Significance inflation and evaluative participial tails, `, highlighting the...` | A fact with its mechanism, or end at the comma |
| Vague authority, `experts argue` | A named source |
| Stating a fact is unknown, then supplying it as likely | Say it is unknown and stop |
| Marketing verbs, `serves as`, `boasts` | `is`, `has` |
| Chat residue, `I hope this helps`, unfilled placeholders | Nothing |
| Curly quotes, repeated bolding, uniform section lengths | ASCII quotes, bold once, uneven structure |

Tables, headings, and correct grammar are never tells by themselves. Never cite an AI-detector score as evidence.

## A Published PR Reply

Four sentences at most. Lead with what changed or the answer, courtesy in a clause, no restatement of the comment, no closing offer, no headings, no bold labels.

Full rule, examples, and rationale: [`standards/anti-slop.md`](../standards/anti-slop.md). Read it before publishing prose another person reads, or when a passage reads as slop and no listed tell applies.

## Enforcement

Enforced by: [`../hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py).
Enforced by: [`../hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py).
Enforced by: [`../hooks/banned-prose-chars.py`](../hooks/banned-prose-chars.py).

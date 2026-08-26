# Anti-Slop

## Core Rule

Every sentence must carry information that changes what the reader knows, decides, or does. Text that fails this test is slop, and slop is banned from every artifact regardless of who or what produced it.

Slop is not a vocabulary problem. It is text whose shape was chosen before its content: a structure gets picked because it sounds finished, and then filler is poured in until the structure is full.

## Why This Rule Exists

[`../CLAUDE.md`](../CLAUDE.md) "Banned Phrases" already blocks a wordlist, and [`../hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py) enforces it. A wordlist is necessary and insufficient. It catches vocabulary; slop is mostly grammar, rhetoric, and layout. The shapes are productive, so a writer barred from "it's worth noting" reaches for "it bears mentioning" and the sentence stays exactly as empty. Blocking the word never touched the move.

The catalogue below comes from the field guide maintained by WikiProject AI Cleanup at <https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing>, which is derived from thousands of reviewed instances rather than from intuition, cross-checked against <https://arxiv.org/abs/2509.19163> and <https://tomyandell.dev/blog/llm-voice>. Two properties make it usable here: the tells are structural, so they survive paraphrase, and each one has a stated mechanism, so a novel variant is recognizable.

## The Three Deciding Tests

Apply these to any passage before publishing it. They are ordered by how often they fire.

| Test | Question | Failure means |
|---|---|---|
| Substitution | Could this sentence appear verbatim in a document about a different subject? | It says nothing about this subject. Delete or replace with the specific claim |
| Deletion | Remove the sentence. Does anything about the reader's next action change? | It was filler. This extends test 1 in [`writing-precision.md`](writing-precision.md) |
| Shape | Did the content choose this structure, or did the structure get filled? | Three items because three sounds complete is a shape defect. Keep the items that exist |

The substitution test is the load-bearing one. `This underscores the importance of careful design` passes a grammar check, passes a spell check, and fits equally well in a paper about bridges, a memo about hiring, and a pull request about a cache. That interchangeability is the definition of slop.

## Rhetorical Shapes

These are moves, not words. Rewriting the words leaves the move intact, so the fix is always to delete the move and state the claim.

| Shape | Example of the shape | Why it fails | Write instead |
|---|---|---|---|
| Negative parallelism | "not just a cache, but a contract"; "it's not about speed, it's about correctness" | Manufactures a misconception nobody held, so the reader is corrected on a position they never took | State the positive claim alone |
| Corrective reframe | "This isn't X. It's Y." | Same move, split across sentences. Builds a strawman to knock down | State Y |
| Rule of three | "fast, safe, and maintainable" | Three because three sounds complete. The third item is usually the weakest | Keep the items that are true. Two is a normal number |
| Throat-clearing | "Here's the thing"; "Let's be clear"; "The truth is" | Signals that something real is coming without saying it | Start with the real thing |
| False concession | "To be fair"; "credit where credit is due" | Concedes a point nobody raised, to perform balance | Address a counterargument that exists, or none |
| Lazy emphasis | "this cannot be overstated"; "the risk here is real" | Annotates a claim instead of making it strong enough to land | Strengthen the claim itself |
| Trailing recap | "In short"; "The key takeaway is"; "Bottom line" | Restates what was just said. In chat it reduces follow-ups; in prose it tells the reader they were not trusted | End when the point lands |
| Compulsive qualification | "while this isn't always the case"; "of course, there are exceptions" | Hedging lowers the chance of being wrong and the chance of being useful in equal measure | Name the specific exception, or drop the hedge |

## Significance Inflation

The most frequent content-level tell. A mundane fact gets a clause explaining that it matters, and the clause carries no evidence.

| Pattern | Examples |
|---|---|
| Testament and legacy | "stands as a testament to"; "leaves an indelible mark"; "marks a turning point" |
| Assigned importance | "plays a crucial role"; "underscores the importance of"; "highlights the need for" |
| Broader trends | "reflects a broader shift"; "in an ever-evolving landscape"; "setting the stage for" |
| Participial tails | ", highlighting the value of..."; ", underscoring its role in..."; ", reflecting the team's..." |

The participial tail is worth its own note. A comma followed by an "-ing" verb of significance is the single most reliable structural marker, because the clause is grammatically optional by construction: it attaches to a complete sentence and adds evaluation rather than fact. When the tail contains a real consequence, promote it to its own sentence with the mechanism stated. When it does not, the comma is where the sentence should have ended.

Legitimate uses of "ensuring", "enabling", and "allowing" exist in technical prose, since those name causal mechanisms rather than significance. They are deliberately excluded from enforcement.

## Evasive Attribution and Hedged Speculation

| Pattern | Examples | Why it fails |
|---|---|---|
| Vague authority | "experts argue"; "observers have noted"; "industry reports suggest"; "studies show" | Attributes a claim to nobody, so it cannot be checked or disputed |
| Manufactured consensus | "is widely considered"; "many believe" | Presents one source, or none, as agreement |
| Absence-plus-speculation | "while specific details are not documented, it likely..." | Asserts both that a fact is unavailable and what it probably is. Both halves are invented |
| Cutoff disclaimer | "as of my last update"; "maintains a low profile" | Chat-surface residue; in an artifact it reads as a fact about the subject |

The third row is the dangerous one, because it survives a plausibility review. It concedes uncertainty, which reads as honesty, and then fills the gap anyway. [`../CLAUDE.md`](../CLAUDE.md) "Anti-Hallucination" governs the fabricated fact; this rule governs the sentence shape that smuggles it in. When something is unknown, the sentence says it is unknown and stops, per [`verification.md`](verification.md).

## Marketing Verbs and Copulative Avoidance

Models systematically avoid "is" and "has". The replacements sound more considered and carry less information.

| Instead of | Write |
|---|---|
| "serves as the entry point"; "functions as a guard"; "operates as a cache" | "is the entry point"; "guards X"; "caches X" |
| "boasts three replicas"; "features retry logic"; "offers a fallback" | "has three replicas"; "retries on timeout"; "falls back to X" |
| "in connection with"; "associated with"; "in the context of" | The actual preposition: of, for, by, after |

Naming the relationship is the point. "Associated with" hides whether the thing causes, follows, contains, or merely accompanies the other.

## Structural Symmetry

Slop is recognizable at a glance, before any sentence is read, because generated structure is too regular to have come from real content.

| Tell | The honest version |
|---|---|
| Every section the same length | Sections are as long as their subject requires. Most subjects are uneven |
| Every list exactly three items | Lists are as long as the set of true items |
| Every bullet a bold label plus a colon plus one sentence | Used where the label is a real index into the content, not where it decorates a sentence |
| A concluding "Challenges" or "Future Outlook" section on a topic that has neither | Omit the section |
| An introduction that announces what the document will cover, followed by the document | Start with the content. Keep a lead only where [`../CLAUDE.md`](../CLAUDE.md) requires a TL;DR |

Bold-label bullets are the most recognizable machine format in circulation, and this repository uses them heavily and deliberately, so they are not mechanically blocked. The deciding test is whether the label is information. "Idempotency key" as a label is an index a reader scans for. "Key benefits" as a label is a category word standing where a claim belongs.

## Formatting and Markup Tells

| Tell | Rule |
|---|---|
| Curly quotation marks and apostrophes | Use ASCII `'` and `"`. Typographic quotes in a source file are auto-substitution residue |
| Boldface on every occurrence of a chosen term | Bold marks a definition once. Repeated bolding is decoration |
| Em dashes joining clauses | Already banned outright by [`../CLAUDE.md`](../CLAUDE.md) "Writing Style" |
| Emoji as structure, decorative Unicode | Already banned outright |
| Headings that contain only other headings | A heading introduces text. Merge or add the text |
| Skipped heading levels, multiple level-1 headings | One level-1 heading. No gaps in the ladder |
| Horizontal rules between every section | Headings already separate sections |

## Residue From the Chat Surface

Text written to a person mid-conversation must never survive into an artifact. This is the artifact-side companion to [`no-ai-process-leak.md`](no-ai-process-leak.md), which governs workflow vocabulary. This section covers assistant register.

Never publish `I hope this helps`, `here's a template you can customize`, `let me know if you'd like me to expand this`, `feel free to adjust`, `Note: replace the values below`, or any second-person address to a reader who is not there.

Never publish an unfilled placeholder: `[insert name]`, `[your company]`, `YYYY-XX-XX`, `Lorem ipsum`, or a code fence whose body is a description of the code that belongs there.

## What Human Technical Writing Looks Like

The tells above are negative. The positive signal is specificity that could only come from having done the thing.

| Signal | Example |
|---|---|
| A number that was measured | "209 files, two hits" rather than "very few cases" |
| A named coordinate | A file, a line, a command, a version |
| An admitted limit | "This was tested on arm64 only" |
| Uneven structure | One section that is four lines because that is all the subject has |
| A concrete failure | The error text, verbatim, per [`smart-questions.md`](smart-questions.md) |
| A decision with its cost stated | Per [`writing-precision.md`](writing-precision.md) section 7b |

When a passage reads as slop and no listed tell applies, the missing ingredient is almost always one of these six.

## What Is Not A Tell

Overcorrection is its own failure, and detection guidance is heavily contaminated by it. Avoiding these costs clarity and buys nothing.

- Correct grammar, complete sentences, and consistent formatting. Competence is not evidence of generation.
- Tables, headings, and lists where the content is genuinely tabular, sectioned, or enumerable. This repository is built on them.
- Any single word in isolation. Density and co-occurrence carry the signal, which is why enforcement targets structures rather than the vocabulary rows above.
- Restating a requirement in a spec, a rule, or a checklist, where repetition across documents is the point.
- Deliberate parallel structure in a table column, where parallelism is what makes the column scannable.

Third-party AI detectors are not evidence, and they misfire hardest on non-native English writers. Do not run one, cite one, or treat a score from one as a finding.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Negative parallelism or corrective reframe in any published text | Corrects a position the reader never held |
| A significance clause with no evidence attached | Fails the substitution test by construction |
| A participial tail that evaluates rather than explains | The sentence ended at the comma |
| Attribution to experts, observers, studies, or reports with no name | Unfalsifiable by design |
| Stating that information is unavailable and then supplying it as likely | Fabrication wearing a hedge |
| A marketing verb where "is" or "has" is accurate | Costs information, buys tone |
| Structure whose regularity was not produced by the content | The shape came first |
| Chat register or an unfilled placeholder in an artifact | The text was never finished |
| Citing an AI-detector score as evidence about a text | The tools are unreliable and biased against non-native writers |

## Mechanical Enforcement

[`../hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py) runs at PreToolUse on Write, Edit, MultiEdit for Markdown, and on Bash commands that publish text. Codes are `SLOP001` through `SLOP012`. Code spans and fenced blocks are excluded before matching, so quoted examples and sample output never trip it.

The detector set is deliberately narrower than this document. Every pattern was measured against the 209 Markdown files under the rules, standards, checklists, skills, agents and docs directories before inclusion, and only patterns at or below three corpus hits were wired up. Bold-label bullets measured 311 hits and are documented above rather than enforced. Rule of three and structural symmetry are not mechanically decidable and are review-time obligations.

Bypass: `AI_SLOP_DISABLE=1`, exported from a parent shell, under the once-per-session discipline in [`../CLAUDE.md`](../CLAUDE.md) "Hook Bypass Discipline". The legitimate case is quoting someone else's text, such as a review reply that cites the comment it answers.

## Interaction With Other Rules

[`writing-precision.md`](writing-precision.md) governs how a sentence is built. This rule governs the shapes a sentence must not take. The precision gate runs first; a passage that clears it can still be slop, because every sentence can be individually precise while the passage as a whole says nothing.

[`../CLAUDE.md`](../CLAUDE.md) "Banned Phrases" and "Natural Writing" remain in force. This rule is the structural layer beneath both.

[`no-ai-process-leak.md`](no-ai-process-leak.md) covers workflow vocabulary such as phase markers and plan references. The overlap is only the chat-residue row.

[`normative-keywords.md`](normative-keywords.md) supplies the obligation word that replaces a stripped hedge.

[`surgical-edits.md`](surgical-edits.md) still bounds the diff. Finding slop in a file this change already touches is in scope per [`found-fix.md`](found-fix.md); rewriting a neighbouring document is not.

## Provenance

Promoted 2026-08-26, `single-incident`, under the fails-without-an-error-signal condition. Slop passes every existing gate: it compiles, it lints, it reads as competent, and no check reports it, so the defect reaches the reader intact and is attributed to the author's judgment.

Origin: the phrase-blocklist layer already in place was measured against the structural tell catalogue maintained by WikiProject AI Cleanup and found to cover vocabulary only, leaving negative parallelism, significance inflation, participial tails, evasive attribution, copulative avoidance, and markup residue entirely unenforced. Corpus calibration across the 209 Markdown files under the rules, standards, checklists, skills, agents and docs directories returned zero hits on 31 of 35 candidate detectors, which establishes both that the existing voice is already disciplined and that the detectors carry a near-zero false-positive rate here. The wired detector set then reported five findings across that corpus plus the two root instruction documents, of which two were detector false positives, now excluded, and three were real and fixed.

## Enforcement

Enforced by: [`../hooks/ai-slop-blocker.py`](../hooks/ai-slop-blocker.py).
Enforced by: [`../hooks/banned-phrases-blocker.py`](../hooks/banned-phrases-blocker.py).
Enforced by: [`../hooks/banned-prose-chars.py`](../hooks/banned-prose-chars.py).

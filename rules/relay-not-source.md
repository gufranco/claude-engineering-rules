# Relay, Not Source

## Core Rule

A report from a subagent, a search tool, or any other intermediary is a **relay**. It is evidence that something was found. It is not the thing itself.

Before writing any claim that cites a specific the relay carried, a quotation, a name, a title, a line number, a file path, a timestamp, a ticket id, a pull request number, a version, or a numeric value, re-fetch the primary source and confirm that the exact coordinate carries the exact content.

## The Failure Nobody Catches

Relays garble the **coordinate**, not only the content.

This is the part that makes the failure invisible. A reviewer checking a relayed claim reads the quoted text, finds it plausible, finds it consistent with everything else known, and accepts it. The quoted text was often fine. What moved was the pointer.

| What the relay carried | What the source actually held |
|---|---|
| A line number for a real function | The function starts eleven lines lower, after an intervening edit |
| A message timestamp | A neighboring message in the same thread, still a valid timestamp, still precise-looking |
| A ticket id next to a correct summary | A different ticket, whose summary the relay merged with the right one |
| A file path under one package | The same filename under a sibling package |
| An expanded person or product name | A shorter name in the source; the relay completed it from context |
| A version number in a changelog entry | The adjacent entry |
| A pull request number | The referenced pull request, not the referencing one |

Every row produces a citation that is well-formed, specific, and wrong. Nothing in the shape of the claim signals the defect, which is why plausibility review cannot catch it and why this needs a mechanical rule.

The second failure mode compounds it: a relay appends context from elsewhere in its own run. It reports what the source says, plus what it inferred, in one voice with no seam. The inference then inherits the source's authority.

## Positive Control

Before the write, for every specific:

1. **Go to the named coordinate.** Open the file at that line, the thread at that timestamp, the ticket at that id. Do not search for the content and assume the coordinate matched.
2. **Confirm the coordinate carries the content.** Both directions. The content must be there, and the coordinate must be the one that holds it.
3. **Confirm nothing was added.** Anything in the relay's report absent from the source is the relay's inference, and it is labeled as such or dropped.
4. **Cite the source, never the relay.** The citation names the file, the thread, the ticket. It never names the subagent report, which is not durable and which the reader cannot open.

When the primary source is unreachable in this session, the claim is not written as fact. State what the relay reported, mark it unverified, and name the check that would settle it.

## Scope

Applies to every intermediary between you and a primary source:

| Relay | Primary source |
|---|---|
| A subagent's final report | The files it read |
| A search tool's excerpt or snippet | The file at that path |
| A summarized or truncated tool result | The full result |
| A prior session's summary or checkpoint | The artifacts it describes |
| A compaction summary | The conversation and files it compressed |
| A memory entry or vault note | The system where the fact lives now |
| Another model's answer | Whatever it cites |
| A web search result snippet | The page |

Two carve-outs, both narrow. A relay's **conclusion** may be acted on without re-fetching when nothing specific is being published: deciding where to look next, choosing between approaches, or scoping the work. And a relay reporting **absence** needs re-verification of the search, not of a coordinate, since there is no coordinate to check; re-run the search yourself with a method calibrated per [`verification.md`](verification.md).

## Delegating With This In Mind

The obligation is cheaper when the relay is briefed to support it. Per [`smart-questions.md`](smart-questions.md), a subagent prompt asks for coordinates in a re-checkable form:

- Require `file:line` for every finding, never a paraphrase of where something lives.
- Require verbatim quotation for anything that will be quoted, marked as verbatim.
- Require the agent to separate what it read from what it concluded.
- Require it to report a coordinate it could not confirm as unconfirmed, rather than approximating.

A relay that returns clean coordinates still gets checked. Briefing reduces the rate of garbling; it does not remove the obligation, because a garbled coordinate looks identical to a good one.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Publishing a quotation, name, or number a subagent reported, without opening the source | The coordinate may point somewhere else while the content reads correctly |
| Verifying that the quoted text exists somewhere, and treating that as confirming the citation | Confirms content, leaves the coordinate unchecked, which is the failure |
| Citing the subagent report as the source | Not durable, not openable by the reader, and one indirection away from the fact |
| Carrying a relay's inference forward as something the source stated | The inference inherits authority it never had |
| Expanding a name, title, or identifier past what the relay showed | Manufactures precision the chain never contained |
| Treating a relay that ran recently as fresher than the source | The source is the only thing that can be current |
| Re-verifying only the finding that looked suspicious | Suspicion does not correlate with coordinate drift, which is what makes it dangerous |

## Interaction With Other Rules

[`../CLAUDE.md`](../CLAUDE.md) "Confidence" already says that not having read something in this session means not knowing it. This rule names the case where a subagent read it and the knowledge feels first-hand because a report arrived.

[`verification.md`](verification.md) governs evidence generally, and lists the related trap of trusting an oracle that was never calibrated.

[`smart-questions.md`](smart-questions.md) governs the subagent brief that makes coordinates re-checkable.

[`ai-guardrails.md`](ai-guardrails.md) requires the orchestrator to review agent output with full rigor. This rule specifies the one check that review most often skips.

## Provenance

Promoted 2026-08-26, `single-incident`, under the fails-without-an-error-signal condition. Origin: an audit of an external multi-agent system whose operating rules included a positive-control gate on delegated sweeps, added after repeated observed drift where relayed timestamps pointed at neighboring messages and relayed identifiers named adjacent records, each producing a citation that was well-formed, specific, and wrong.

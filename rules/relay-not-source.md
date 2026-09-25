# Relay, Not Source

A report from a subagent, search tool, summary, memory, or other intermediary is a relay. Before publishing any specific it carried, re-fetch the primary source at the named coordinate.

- Specifics: quotations, names, titles, line numbers, file paths, timestamps, ticket ids, PR numbers, versions, numeric values.
- Relays garble coordinates as well as content. Open the named coordinate; never search for the content and assume the coordinate matched.
- Confirm both directions: the content is there, and that coordinate holds it.
- Anything in the relay absent from the source is inference: label it or drop it.
- Cite the source, never the relay.
- Source unreachable: mark the claim unverified and name the check that would settle it.
- Carve-outs: a relay's conclusion may steer where to look next; a reported absence needs the search re-run yourself.
- Brief subagents to return `file:line`, verbatim quotes marked as such, read versus concluded kept separate, and unconfirmed coordinates flagged.

Full rule, examples, and rationale: [`standards/relay-not-source.md`](../standards/relay-not-source.md). Read it before publishing findings a subagent or search tool reported.

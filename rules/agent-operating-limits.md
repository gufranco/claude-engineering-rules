# Agent Operating Limits

Every limit on an agent run states the measurement that set it, or states that none was taken.

- Backstop: turn ceiling, timeout, hard iteration cap. Tripping it loses the whole run, so set it above the observed maximum with headroom, never at the expected value.
- Budget: per-run change cap. Set it where marginal value stops. Overflow is reported as a list for the next pass, never silently dropped.
- Before setting a backstop: sample the distribution, subtract known waste such as denied calls, record the measurement beside the number, and budget for queue or outage wait.
- A denied tool call costs a full turn. Change the request shape; never retry the same shape. Three denials means the capability is absent.
- Project API and query results to the needed fields at the call.
- Unconditional injections: prefer a condition, and never instruct toward a capability that may be absent.
- Fail closed: a check that errored, would not parse, or could not run is a failed check. A missing state file means nothing is granted.
- Gate on exit codes, never on grepping output. Confirm whether stdout or stderr carries the payload.
- Know which identity you act as, supersede your own prior output instead of stacking, and write each summary fresh.
- Write only inside this session's own tree. Before a write lands in a directory another live session works in, listed in `~/.claude/sessions/`, the user confirms it; that session reports the change as its own.

Full rule, examples, and rationale: [`standards/agent-operating-limits.md`](../standards/agent-operating-limits.md). Read it before setting a turn ceiling, timeout, or per-run cap, or before adding an always-on injection.

## Enforcement

Enforced by: [`hooks/foreign-session-guard.py`](../hooks/foreign-session-guard.py).

## Provenance

Promoted 2026-08-26, `single-incident`, under the fails-without-an-error-signal condition. Origin: an audit of an external agent review pipeline whose turn ceiling carried its sampled distribution inline, and whose prompt hook instructed toward an absent capability and cost a denied turn on every run. Full account in [`standards/agent-operating-limits.md`](../standards/agent-operating-limits.md). Amended 2026-10-29, `single-incident`, by direct user instruction: a session working in `~/.claude` wrote `~/.dotfiles/.releaserc.json` while a dotfiles session was running a command, and that session showed the file as its own change, which read as instructions leaking between sessions.

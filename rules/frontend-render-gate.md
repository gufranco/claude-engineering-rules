# Frontend Render Gate

## Core Rule

A change to rendered output is not verified until something has rendered it. Reading the diff, passing a jsdom unit test, and a clean type check are all necessary and none of them is sufficient.

The gate applies to any diff that touches markup, styles, theme tokens, or the component tree: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.dart`, `.css`, `.scss`, and any file whose name or path marks it as a theme or design token source.

## Why This Rule Exists

Four defects shipped past a careful static review of an accessibility change, and a reviewer found all four in a real browser within one session. Each one is invisible in source by construction:

| Defect | Why source review cannot see it |
|---|---|
| A payment field had no focus indicator | The field is a cross-origin iframe. Parent CSS cannot reach into it, so the rule that appears to cover "every focusable element" provably does not |
| Every nav item was two tab stops | A button nested inside an anchor. Both elements are legitimate in isolation; the defect exists in the accessibility tree |
| The focus ring was described with the wrong colour, and pointer behavior was described as unchanged | Requires reading computed style off the focused element. The token names in the file say nothing about what paints |
| A focus ring was hidden behind a card image | Inset shadows paint under child content. This is paint order, observable only once rendered |

The common thread is that each defect lives in a layer the source does not describe: iframe boundaries, the accessibility tree, computed style, and paint order.

## The Blind Class

These categories are unreachable by static analysis and by jsdom. A change touching any of them requires a real engine.

| Category | What only a browser answers |
|---|---|
| Cascade outcome | Which rule wins at the element, after specificity, order, and inherited state |
| Paint order | Whether a shadow, outline, or overlay is drawn above or below sibling and child content |
| Accessibility tree | Accessible name, role, and state as computed, plus duplicate and nested interactives |
| Focus order | The actual tab sequence, including stops the markup does not imply |
| Third-party frames | Anything inside an iframe the page does not own, such as a hosted payment field |
| Viewport behavior | Overflow, clipping, and reflow at a real width |
| Async render | What a visitor sees after hydration settles, rather than what the first paint contains |

jsdom does not implement layout, paint, or a full accessibility tree. A jsdom test asserting a class name or an attribute is a structural test, and it is worth having, but it is not evidence about any row above.

## What Counts As Evidence

Ranked. Prefer the highest rung the project already supports.

1. **An automated check in the project's own harness.** When the repository has a browser-driven suite, the evidence is a new or extended case in that suite. This is the only rung that keeps holding after the change ships.
2. **A scripted one-off against a real engine**, capturing computed style or the accessibility tree on the specific element in question. Appropriate when the harness cannot reach the surface, such as a flow requiring third-party credentials.
3. **A rendered screenshot at a stated viewport**, when the claim is purely visual and no assertion can express it.

A description of what the author expects to happen is not evidence at any rung.

## Obligations

- **Extend the harness the project already has.** When a browser-driven suite exists, a UI change that ships without touching it is incomplete. Building a parallel one-off path when a harness exists is worse than useless, because the one-off does not run again.
- **Assert the computed result, never the input.** `expect(el).toHaveClass('focus-ring')` restates the source. Reading `outline` and `boxShadow` off the focused element tests the cascade. Prefer the latter whenever the claim is about what a visitor perceives.
- **Assert on the accessibility tree for any semantics change.** Accessible name, role, and the absence of nested interactives. A snapshot of the tree catches the duplicate-node class that markup review misses.
- **Name the viewport.** A layout claim without a width is untestable. State the width the assertion holds at, and include the smallest supported width when the change affects layout.
- **A regression test outranks a fix.** When a browser surfaces a defect, the deliverable is the fix plus a case that fails without it. Confirm the case fails against the previous revision; a test that passes both ways asserts nothing.
- **Record known findings rather than waiving the check.** When a pre-existing violation cannot be fixed in scope, record it in a per-route or per-screen allowlist so new findings still fail while the old ones stay visible. Suppressing the whole check hides the next regression.

## Mobile

The same rule, with a simulator or emulator in place of the browser. A widget test is the jsdom tier: it proves structure, not paint, and not the platform accessibility tree.

When the toolchain for a mobile target is not installed, that is a gap to close rather than a reason to fall back to source review. State plainly that the change is unverified, rather than reporting it as done.

## Forbidden Patterns

| Pattern | Reason |
|---|---|
| Declaring a UI change done with only a diff read | The blind class above is entirely unexamined |
| Treating a passing jsdom test as render evidence | jsdom implements no layout and no paint |
| Asserting a class name or token import as proof of appearance | Restates the source instead of testing the outcome |
| Claiming a focus, contrast, or layout property without reading it off a rendered element | The claim is a guess with the shape of a fact |
| Describing a visual change in a pull request without having seen it rendered | Ships an unverified claim to a reviewer who will trust it |
| Waiving a whole accessibility check to get past a known finding | Hides every future regression along with the known one |
| Reporting a mobile change as verified with no simulator run | There is no evidence at any rung |

## The Tooling Is Installed

There is no "no engine available" excuse on this machine. `agent-browser` is provisioned globally through mise, so a real Chromium is one command away, and Playwright browsers are cached for projects that drive their own suite.

The three checks that answer most of the blind class:

```bash
agent-browser open http://localhost:4502/some/route

agent-browser eval "document.getElementById('pay').focus();
  const s = getComputedStyle(document.activeElement);
  JSON.stringify({ outline: s.outlineWidth + ' ' + s.outlineStyle, shadow: s.boxShadow })"

agent-browser snapshot -i
```

The first reads the cascade outcome rather than the declared rule. The second is the only way to learn whether a focus indicator actually paints. The third prints the accessibility tree, where a control nested inside another shows as two nodes carrying one visible label, which is the defect markup review cannot see.

Then `agent-browser set device "iPhone 12"` for viewport behavior, and `agent-browser close` when finished.

Run `agent-browser skills get core --full` before composing a longer flow; the CLI ships version-matched usage guidance, which beats guessing flags.

A one-off probe is the second evidence tier. When the project has its own browser suite, extending that suite still outranks it, because the probe does not run again.

## Mobile Has No Free Pass

A widget test is the jsdom tier. It proves structure and says nothing about paint, platform accessibility semantics, or focus traversal on a device.

The device-level tier is an `integration_test` suite driven by a simulator or emulator, with `xcrun simctl` and `adb` both present here. When a mobile project has no `integration_test` directory, that absence is the finding: the platform surface has never been verified, and saying so is more useful than reporting a widget test as if it covered the same ground.

## Where The How Lives

This rule is the gate. It says a render check is required and what counts as one. It deliberately does not restate technique.

[`../standards/browser-testing.md`](../standards/browser-testing.md) carries the technique: Playwright architecture, page objects, visual regression, accessibility tree testing, responsive testing. Read it when writing the check.

The split matters because that standard is loaded on demand, so it reaches the session only when a trigger matches. A gate that fires at commit time does not depend on a trigger having matched earlier, which is why the obligation lives here and the method lives there.

## Interaction With Other Rules

[`verification.md`](verification.md) governs evidence generally, and this rule names what evidence means for rendered output. [`accessibility-defaults.md`](accessibility-defaults.md) sets the conformance target this gate measures against. [`surgical-edits.md`](surgical-edits.md) still bounds the diff: the gate widens what must be verified, never what may be changed.

When a render check surfaces a pre-existing defect outside the current scope, [`found-fix.md`](found-fix.md) applies to what the change touches, and the rest is reported rather than silently absorbed.

## Enforcement

Enforced by: [`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py).

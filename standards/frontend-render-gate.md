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
3. **A before and after pair of rendered screenshots at a stated viewport**, when the claim is purely visual and no assertion can express it. A final screenshot alone shows an end state, never the change the action caused.

A description of what the author expects to happen is not evidence at any rung.

## Obligations

- **Extend the harness the project already has.** When a browser-driven suite exists, a UI change that ships without touching it is incomplete. Building a parallel one-off path when a harness exists is worse than useless, because the one-off does not run again.
- **Assert the computed result, never the input.** `expect(el).toHaveClass('focus-ring')` restates the source. Reading `outline` and `boxShadow` off the focused element tests the cascade. Prefer the latter whenever the claim is about what a visitor perceives.
- **Assert on the accessibility tree for any semantics change.** Accessible name, role, and the absence of nested interactives. A snapshot of the tree catches the duplicate-node class that markup review misses.
- **Name the viewport.** A layout claim without a width is untestable. State the width the assertion holds at, and include the smallest supported width when the change affects layout.
- **A regression test outranks a fix.** When a browser surfaces a defect, the deliverable is the fix plus a case that fails without it. Confirm the case fails against the previous revision; a test that passes both ways asserts nothing.
- **Record known findings rather than waiving the check.** When a pre-existing violation cannot be fixed in scope, record it in a per-route or per-screen allowlist so new findings still fail while the old ones stay visible. Suppressing the whole check hides the next regression.

## Driving The Check

A render check drives the behavior the way a user reaches it and reads every surface where a failure can hide.

- **Drive every entry point.** When a route, a dialog, a menu item, and a keyboard shortcut all reach the same behavior, the check drives each of them. A proof through one convenient page is incomplete while another entry point stays unexercised.
- **Read the persisted side effect back.** A page that renders the expected state over a row that never changed is a failure. After the action, read the stored state where the change was meant to land, through the service, the API, or a read-only query against a disposable database. List every table or store the action wrote. An unexpected extra write is a finding: a button that writes three tables when it should write one is a defect the check found.
- **Read the page errors, the console, and the body text.** Run `agent-browser errors` and `agent-browser console` after each step, and both must be empty. A hydration failure renders straight through a screenshot. An empty errors list is still not a clean page, because a broken render can surface only as page text such as "Something went wrong", so read `agent-browser get text body` when a page looks blank or wrong.
- **Reload once before reporting a dev-server failure.** A dev server's first visit to a route can optimise dependencies mid-render and crash the page. Wait a few seconds, run `agent-browser reload` once, and report the failure only when it survives the reload.
- **Confirm the engine is yours.** Before trusting a snapshot, confirm the port is held by the pid you launched or a direct child of it. A server that announced a different port than the one requested is refused, never driven. A snapshot taken against someone else's server proves nothing.
- **Re-snapshot after any DOM change.** Snapshot refs such as `@e12` are invalidated when the page changes, so take a fresh snapshot before the next interaction. Scope a large page with `-s "<selector>"`, cap it with `-d <n>`, or compact it with `-c`, so the tree stays readable.
- **One browser session per parallel run.** Each concurrent check passes its own `--session <name>`. Sessions isolate cookies, storage, and tabs, and two runs sharing the default session overwrite each other's state.

```bash
agent-browser --session cart-a open http://localhost:4502/cart
agent-browser --session cart-a snapshot -i -s "main"
agent-browser --session cart-a click @e4
agent-browser --session cart-a snapshot -i -s "main"
agent-browser --session cart-a errors
agent-browser --session cart-a console
agent-browser --session cart-a get text body
```

### Assertion Hygiene

- **Record every display setting that shapes the numbers on screen.** A filter, a toggle, or a checkbox that changes a count is part of the evidence, or the counts cannot be read back.
- **A disabled control is an assertion.** Reading `[disabled]` on a gated button verifies the gate without opening it.
- **A legitimate empty state is a correct render.** A list that reads "No items" because there are none is passing output, never a load failure. Verify list behavior on a view that has rows.

### What The Pull Request States

The pull request body states what was clicked and what was seen, with screenshots or the path to the evidence files. A change with no rendered effect says `No UI change` in one line instead.

Provenance: 2026-10-12, owner request. Adopted from the course-video-manager verify-cvm skill, its feature notes and launch scripts, its CLAUDE.md, and the agent-browser skill references on snapshot refs and sessions.

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

[`../standards/browser-testing.md`](browser-testing.md) carries the technique: Playwright architecture, page objects, visual regression, accessibility tree testing, responsive testing. Read it when writing the check.

The split matters because that standard is loaded on demand, so it reaches the session only when a trigger matches. A gate that fires at commit time does not depend on a trigger having matched earlier, which is why the obligation lives here and the method lives there.

## Interaction With Other Rules

[`verification.md`](../rules/verification.md) governs evidence generally, and this rule names what evidence means for rendered output. [`accessibility-defaults.md`](../rules/accessibility-defaults.md) sets the conformance target this gate measures against. [`surgical-edits.md`](../rules/surgical-edits.md) still bounds the diff: the gate widens what must be verified, never what may be changed.

When a render check surfaces a pre-existing defect outside the current scope, [`found-fix.md`](../rules/found-fix.md) applies to what the change touches, and the rest is reported rather than silently absorbed.

## Enforcement

Enforced by: [`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py).

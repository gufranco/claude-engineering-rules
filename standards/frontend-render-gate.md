# Frontend Render Gate

## Core Rule

A change to rendered output is not verified until something has rendered it. Reading the diff, passing a jsdom unit test, and a clean type check are all necessary and none of them is sufficient.

The gate applies to any diff that touches markup, styles, theme tokens, the component tree, a desktop layout, or a terminal UI: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.dart`, `.css`, `.scss`, native view sources, `.qml`, `.ui`, `.xaml`, `.storyboard`, `.xib`, any file whose name or path marks it as a theme or design token source, and any shipped source that imports a terminal UI library. A terminal UI's render-level check is a snapshot of the rendered screen, such as textual's `snap_compare`, bubbletea's teatest golden files, or an insta snapshot of ratatui's `TestBackend`.

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
- **Record blocked findings rather than waiving the check.** A pre-existing violation the check finds is fixed in this change per [`found-fix.md`](../rules/found-fix.md). Only one whose fix is blocked outside the change, such as a third-party frame the page does not own, goes in a per-route or per-screen allowlist that names the blocker, so new findings still fail while the old ones stay visible. Suppressing the whole check hides the next regression.

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

The pull request body states what was clicked and what was seen, with the screenshots [Visual Evidence In Published Text](#visual-evidence-in-published-text) requires. A change with no rendered effect says `No UI change` in one line instead.

Provenance: 2026-10-12, owner request. Adopted from the course-video-manager verify-cvm skill, its feature notes and launch scripts, its CLAUDE.md, and the agent-browser skill references on snapshot refs and sessions.

## Visual Evidence In Published Text

A reviewer judges an interface change mostly by looking at it. Every text that publishes or answers a visible change carries high-resolution screenshots: Before, unless the surface is new, and After.

### Where It Applies

| Channel | Carries |
|---|---|
| A new or edited pull request or merge request | Before and After in the body |
| A review-thread reply after a visible fix | After, plus Before when the reply explains what changed |
| A new issue proposing a visible change | Before of the current state, and After when a mockup or prototype exists |
| An issue answer that ships a fix | Before and After of the fix |
| A tracker issue or comment, such as Linear | The same as its GitHub equivalent |

It applies to every surface a person looks at: web, mobile, desktop GUI, and terminal UI.

### What A Valid Screenshot Is

- **Present.** A pull request with a visible change carries image files. A text-only `Before / After` section is not evidence.
- **High resolution.** Capture at a device scale of 2 or more. The longer side must reach 1600 px. A 1x capture of a 1440x900 laptop fails; a 3x phone capture passes.
- **Full page.** Capture the whole page, never only the viewport. A capture exactly one viewport tall, such as 1800 px from a 900 px viewport at scale 2, shows that the page scrolled inside an inner container and the rest was cut off.
- **One width per set.** Every image published together has the same pixel width, so each renders at the same width on screen whatever its orientation.
- **Scaled, never padded.** Equalize widths by proportional scaling. A 640x7798 mobile capture becomes 2880x35091 with `sips --resampleWidth 2880` or `sips -z 35091 2880`. Never pad a narrow capture onto a wider canvas.
- **Grouped and labeled.** Desktop and mobile go in separate groups, each under its own heading, such as `Desktop, 1440 px viewport` and `Mobile, 320 px viewport`. The alt text starts with `Before:` or `After:`, names the device and viewport, and names the screen, as in `After: Mobile 320 px, default queue`. A new page has no Before; say so in one line.
- **Comparable.** Before comes from the base commit with the same data, viewport, theme, locale, and window size as After. A difference the change did not cause hides the one it did.
- **Complete.** Every state the change touches gets its pair: each theme, each breakpoint the layout changes at, and each error or empty state the diff alters.
- **Clean.** Seeded or fake data only, never a real customer's name, email, or balance, per [`privacy-defaults.md`](../rules/privacy-defaults.md).

### Capturing Before

Run the base commit beside the branch, never by stashing work:

```bash
git worktree add ../before "$(git merge-base origin/main HEAD)"
```

Start it on its own port, capture the same screen, then `git worktree remove ../before`.

### Capture Recipes

Each recipe was run on 2026-10-28 on macOS, and the size it produced is listed.

| Surface | Command | Measured output |
|---|---|---|
| Web | `agent-browser set viewport 1440 900 2`, then `agent-browser open <url>` and `agent-browser screenshot --full after.png` | 2880 wide, as tall as the page |
| iOS | `xcrun simctl io booted screenshot after.png` | 1206x2622 on an iPhone simulator |
| Android | `adb exec-out screencap -p > after.png` | 1080x2400 on a Pixel 6 emulator |
| macOS desktop | `screencapture -o -l <window-id> after.png` on a Retina display | Not run; it needs Screen Recording permission |
| Terminal UI | `asciinema rec --headless --window-size 100x30 -c '<command>' run.cast`, then `agg --font-size 32 run.cast run.gif` and `magick 'run.gif[-1]' after.png` | 1958x1388 |

An 80x24 terminal at font size 32 renders narrower than 1600 px, so the terminal recipe pins 100x30. For a mobile layout on the web, `agent-browser set viewport 320 800 2` before the same full-page capture. A simulator or emulator started only for a capture runs headless: `xcrun simctl boot <udid>` without opening Simulator.app, and `emulator -avd <name> -no-window -no-audio`.

### When The Page Scrolls Inside A Container

A full-page capture stops at the viewport edge when the layout pins its root to the viewport and scrolls an inner element, which is what an `h-screen` shell with a `flex-1` column and a scrolling `main` does. Playwright's `fullPage` and `agent-browser screenshot --full` both measure the document, and the document is one viewport tall.

Before capturing, inject CSS that lets each clipping ancestor grow to its content:

```bash
agent-browser eval "const s = document.createElement('style');
  s.textContent = '.h-screen, .flex-1, main { height: auto !important } main { flex: none !important }';
  document.head.appendChild(s)"
agent-browser screenshot --full after.png
```

Measured on 2026-10-29 with a 40-row page in that shell at 1440x900 scale 2: 2880x1800 before the injection, 2880x8080 after. Name the project's own clipping classes in the selector. Never set `overflow: visible`: on admin a 75-column table then stretched the capture to 18,438 px wide.

### Publishing The Images

`gh` uploads local files with `--attach '<file>#<alt text>'` on `pr create`, `pr edit`, `issue create`, `issue edit`, and `issue comment`. An uploaded image inherits the repository's visibility, so a private repository's screenshots stay private. Never commit screenshots to the repository or host them anywhere else.

```bash
gh pr create --title "..." --body-file body.md \
  --attach 'before.png#Before: Desktop 1440 px, checkout button' \
  --attach 'after.png#After: Desktop 1440 px, checkout button'
```

The body groups the images by device, one heading each:

```markdown
### Desktop, 1440 px viewport

![After: Desktop 1440 px, default queue](<url>)

### Mobile, 320 px viewport

![After: Mobile 320 px, default queue](<url>)

New page, so there is no Before.
```

A review-thread reply cannot attach. Upload through the pull request first, read the URL back, and embed it:

```bash
gh pr edit 42 --attach 'after.png#After: focus ring'
gh pr view 42 --json body --jq .body
```

Then reply with `![After: focus ring](<url>)` in the body. The upload also keeps the pull request's Evidence section current, which the description needs anyway.

GitLab uploads through `glab api projects/:id/uploads -F file=@after.png`, and Linear through its `prepare_file_upload` tool. Each returns the Markdown to embed.

### How The Hook Decides

[`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py) reads the branch diff against its base before any channel above publishes.

- When the diff touches a web, mobile, desktop, or terminal surface, it blocks until the text carries an `After:` image, plus a `Before:` image when an existing surface changed or was deleted.
- It reads each attached file's header and blocks an image whose longer side is under 1600 px, or a file that is missing or not an image.
- It blocks a set whose images differ in pixel width, naming each width and the `sips --resampleWidth` command that fixes it.
- When one label names a device or a viewport width, it blocks every label in the set that names neither.
- It asks for a full-page capture when an image is exactly one common viewport tall at scale 1, 2 or 3, such as 1800 px for 900 at scale 2.
- It expands `$VAR` and `${VAR}` assigned earlier in the same command or present in the environment, and resolves relative `--attach` and `--body-file` paths against the directory a `cd` moved into. A variable it cannot expand is named in the block.
- A tracker issue or comment is judged by its own text, never by the checked-out branch, so a schema-only ticket filed from a branch with UI changes passes.
- A terminal surface is a source file that imports a terminal UI library, such as textual, curses, ink, bubbletea, or ratatui.
- An issue, reply, or tracker text that describes an interface with no visible change behind it and no image raises a confirmation instead of a block.
- When the diff cannot be read, opening or editing a pull request raises the same confirmation.

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
| Publishing a visible change, or a reply about one, without Before and After screenshots | The reviewer's main criterion for an interface goes unseen |
| Attaching a 1x capture, or a Before taken with other data, theme, or viewport than After | The pair cannot be compared, so the difference the change made stays hidden |
| Committing screenshots to the repository or hosting them outside the platform | History grows forever, and a private repository's images leak |
| A text-only `Before / After` section in place of images | The reviewer reads a claim instead of seeing the change |
| A viewport-only capture of a page that scrolls | Everything below the fold goes unreviewed |
| Setting `overflow: visible` to unclip a page | Wide content such as a 75-column table stretches the capture sideways |
| Padding a narrow capture onto a wider canvas | The phone screenshot renders tiny inside empty space; scale it instead |
| Mixing desktop and mobile images under one heading | The reader cannot tell which device each image shows |

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

[`verification.md`](../rules/verification.md) governs evidence generally, and this rule names what evidence means for rendered output. [`accessibility-defaults.md`](../rules/accessibility-defaults.md) sets the conformance target this gate measures against. [`surgical-edits.md`](../rules/surgical-edits.md) still bounds the diff: the gate widens what must be verified, and only its findings widen what may be changed.

When a render check surfaces a pre-existing defect, [`found-fix.md`](../rules/found-fix.md) puts it in scope: fix it in this change and name it in one line of the PR body. Only a fix blocked outside the change waits, with the blocker stated in one sentence.

## Enforcement

Enforced by: [`hooks/frontend-render-gate.py`](../hooks/frontend-render-gate.py).

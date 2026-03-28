# Accessibility Testing

## WCAG Compliance Levels

WCAG AA is the baseline for all projects. AAA is optional unless the project serves users with disabilities as a primary audience.

| Level | When it applies | What constitutes a pass |
|-------|----------------|------------------------|
| AA | Every project, no exceptions | All Level A and AA success criteria pass with zero violations in automated scans, plus manual testing confirms keyboard and screen reader functionality |
| AAA | Government, healthcare, education, assistive technology products | All Level A, AA, and AAA success criteria pass. Enhanced contrast (7:1 body, 4.5:1 large), sign language for video, multiple navigation paths |

AA pass criteria:

- Zero axe-core violations at the "critical", "serious", and "moderate" levels
- All interactive elements reachable and operable via keyboard
- Screen reader announces all content in a logical order
- Color contrast meets 4.5:1 for body text, 3:1 for large text and UI components
- No content depends solely on color, shape, or position to convey meaning

## Automated Testing Tools

### axe-core

axe-core is the primary accessibility engine. Use framework-specific wrappers for each testing layer.

#### jest-axe (Unit/Component Tests)

```typescript
// setup: pnpm add -D jest-axe @types/jest-axe
import { render } from "@testing-library/react";
import { axe, toHaveNoViolations } from "jest-axe";

expect.extend(toHaveNoViolations);

test("LoginForm has no accessibility violations", async () => {
  // Arrange
  const { container } = render(<LoginForm />);

  // Act
  const results = await axe(container);

  // Assert
  expect(results).toHaveNoViolations();
});
```

#### @axe-core/playwright (E2E Tests)

```typescript
// setup: pnpm add -D @axe-core/playwright
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("dashboard page passes axe audit", async ({ page }) => {
  // Arrange
  await page.goto("/dashboard");

  // Act
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  // Assert
  expect(results.violations).toEqual([]);
});
```

#### cypress-axe (E2E Tests)

```typescript
// setup: pnpm add -D cypress-axe axe-core
// In cypress/support/e2e.ts:
import "cypress-axe";

describe("checkout flow", () => {
  it("passes axe audit at each step", () => {
    cy.visit("/checkout/cart");
    cy.injectAxe();
    cy.checkA11y(undefined, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
      },
    });

    cy.get("[data-testid=proceed-button]").click();
    cy.checkA11y();
  });
});
```

### Lighthouse CI

Run Lighthouse in CI to enforce a minimum accessibility score.

```yaml
# .lighthouserc.json
{
  "ci": {
    "collect": {
      "url": ["http://localhost:3000", "http://localhost:3000/dashboard"],
      "startServerCommand": "pnpm start",
      "numberOfRuns": 3
    },
    "assert": {
      "assertions": {
        "categories:accessibility": ["error", { "minScore": 0.9 }]
      }
    }
  }
}
```

The threshold is 0.9 (90%). A score below 90 fails the CI step. Teams targeting AAA compliance must raise this to 0.95.

### Pa11y

Pa11y runs HTML CodeSniffer against rendered pages. Use it as a CI gate for multi-page audits.

```javascript
// pa11y.config.js
module.exports = {
  defaults: {
    standard: "WCAG2AA",
    runners: ["axe", "htmlcs"],
    timeout: 30000,
    wait: 1000,
    chromeLaunchConfig: {
      args: ["--no-sandbox"],
    },
  },
  urls: [
    "http://localhost:3000",
    "http://localhost:3000/login",
    "http://localhost:3000/dashboard",
    "http://localhost:3000/settings",
  ],
};
```

```bash
pa11y-ci --config pa11y.config.js
```

Zero errors for a pass. Pa11y returns a non-zero exit code on any violation, so it blocks the pipeline by default.

## Manual Testing Checklist

Automated tools catch approximately 30-50% of accessibility issues. Manual testing is mandatory for every feature that changes UI.

### Keyboard Navigation

| Key | Expected behavior | Verify |
|-----|-------------------|--------|
| Tab | Move focus to next interactive element in DOM order | Focus indicator is visible, order matches visual layout |
| Shift+Tab | Move focus to previous interactive element | Same as Tab, reversed |
| Enter | Activate buttons, links, submit forms | Every clickable element responds to Enter |
| Space | Activate buttons, toggle checkboxes, open selects | Buttons respond to both Enter and Space |
| Escape | Close modals, popovers, dropdowns, dismiss notifications | Focus returns to the element that triggered the overlay |
| Arrow keys | Navigate within composite widgets: tabs, menus, radio groups, listboxes | Only one item in the group is in the tab order, arrows move within |
| Home/End | Jump to first/last item in lists, menus, tabs | Wrapping behavior matches ARIA pattern spec |

Every page must be fully operable without a mouse. Test the complete user flow, not just individual components.

### Screen Reader Testing

| Platform | Screen reader | Browser | How to test |
|----------|--------------|---------|-------------|
| macOS | VoiceOver | Safari | Cmd+F5 to toggle, use rotor (VO+U) to browse landmarks, headings, links |
| Windows | NVDA | Firefox or Chrome | Download from nvaccess.org, use Elements List (NVDA+F7) |
| Android | TalkBack | Chrome | Settings > Accessibility > TalkBack, swipe to navigate |
| iOS | VoiceOver | Safari | Settings > Accessibility > VoiceOver, swipe to navigate |

Test at minimum on one desktop and one mobile screen reader per release. Verify:

- All content is announced in a logical reading order
- Interactive elements announce their role, name, and state
- Form errors are announced when they appear
- Dynamic content changes are announced via live regions
- Images have descriptive alt text or are marked decorative

### Color Contrast Verification

- Use the OKLCH contrast calculation from `standards/frontend.md` for programmatic checks
- Test every foreground/background pair that appears together
- Muted text, placeholder text, and disabled states are the most common failure points
- Dark mode requires a separate contrast audit

### Reduced Motion

- Enable "Reduce motion" in OS accessibility settings
- Verify all animations are suppressed or replaced with instant transitions
- Content that animated in must still be visible in the reduced-motion state
- Parallax, auto-playing carousels, and background video must stop

## ARIA Patterns

### Landmarks

Every page must have these landmarks at minimum:

```tsx
<header role="banner">
  <nav aria-label="Main">...</nav>
</header>

<main>
  <h1>Page Title</h1>
  ...
</main>

<footer role="contentinfo">
  <nav aria-label="Footer">...</nav>
</footer>
```

Multiple `<nav>` elements on the same page must each have a unique `aria-label`. Duplicate landmark labels break screen reader navigation.

### Live Regions

Use live regions to announce dynamic content changes: toast notifications, form validation summaries, loading states, search result counts.

```tsx
// Polite: announces after current speech finishes (default for non-urgent)
<div role="status" aria-live="polite">
  {searchResults.length} results found
</div>

// Assertive: interrupts current speech (errors and urgent alerts only)
<div role="alert" aria-live="assertive">
  {errorMessage}
</div>
```

| Urgency | Attribute | Use for |
|---------|-----------|---------|
| Low | `aria-live="polite"` | Search results count, save confirmation, status updates |
| High | `aria-live="assertive"` or `role="alert"` | Form validation errors, session expiration, destructive action warnings |

Rules:

- The live region element must exist in the DOM before content changes. Dynamically inserting an element with `aria-live` does not trigger announcement
- Never put an entire page section inside a live region. Only the changing text
- Avoid `aria-live="assertive"` for non-critical updates. It interrupts the user mid-sentence

### Dialog and Modal Focus Management

```tsx
function AccessibleDialog({ isOpen, onClose, title, children }: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      dialogRef.current?.focus();
    }
    return () => {
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
      tabIndex={-1}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          onClose();
        }
      }}
    >
      <h2 id="dialog-title">{title}</h2>
      {children}
    </div>
  );
}
```

Focus management rules for dialogs:

1. On open: move focus to the dialog container or its first focusable element
2. While open: trap focus inside the dialog. Tab from the last element wraps to the first
3. On close: return focus to the element that triggered the dialog
4. Escape key must close the dialog

### Form Validation Announcements

```tsx
// Error summary at the top of the form, linked to invalid fields
<div role="alert" aria-live="assertive">
  <h2>2 errors found</h2>
  <ul>
    <li><a href="#email">Email address is required</a></li>
    <li><a href="#password">Password must be at least 8 characters</a></li>
  </ul>
</div>

// Individual field error, associated via aria-describedby
<label htmlFor="email">Email</label>
<input
  id="email"
  type="email"
  aria-invalid={!!errors.email}
  aria-describedby={errors.email ? "email-error" : undefined}
/>
{errors.email && (
  <p id="email-error" role="alert">
    {errors.email}
  </p>
)}
```

Rules:

- Every invalid field must have `aria-invalid="true"`
- Every error message must be linked to its field via `aria-describedby`
- On form submission failure, move focus to the error summary or the first invalid field
- Never rely on color alone to indicate an error. Add an icon, text, or border change

### Tabs Pattern

```tsx
<div role="tablist" aria-label="Account settings">
  <button
    role="tab"
    id="tab-profile"
    aria-selected={activeTab === "profile"}
    aria-controls="panel-profile"
    tabIndex={activeTab === "profile" ? 0 : -1}
    onClick={() => setActiveTab("profile")}
    onKeyDown={handleTabKeyDown}
  >
    Profile
  </button>
  <button
    role="tab"
    id="tab-security"
    aria-selected={activeTab === "security"}
    aria-controls="panel-security"
    tabIndex={activeTab === "security" ? 0 : -1}
    onClick={() => setActiveTab("security")}
    onKeyDown={handleTabKeyDown}
  >
    Security
  </button>
</div>

<div
  role="tabpanel"
  id="panel-profile"
  aria-labelledby="tab-profile"
  hidden={activeTab !== "profile"}
>
  ...
</div>
```

Keyboard behavior: arrow keys move between tabs, Tab moves into the panel. Only the active tab has `tabIndex={0}`. All others have `tabIndex={-1}`.

### Common ARIA Mistakes

| Mistake | Why it fails | Fix |
|---------|-------------|-----|
| `<div role="button">` without keyboard handler | Divs do not respond to Enter/Space by default | Use `<button>`. If impossible, add `onKeyDown`, `tabIndex={0}` |
| `aria-label` on a non-interactive `<div>` | Screen readers ignore labels on generic elements | Use a semantic element or add a `role` |
| `aria-hidden="true"` on a focusable element | Focus lands on invisible content | Remove from tab order first, then hide |
| Redundant `role="button"` on `<button>` | Native semantics already provide the role | Remove the redundant role |
| `aria-live` on a container that existed at page load | Every content change in the container triggers announcement | Scope live regions to the smallest changing element |
| Using `aria-label` to override visible text | Screen reader users hear a different label than sighted users | Use `aria-labelledby` pointing to the visible text |

## CI Integration

### GitHub Actions Workflow

```yaml
name: Accessibility

on:
  pull_request:
    branches: [main, develop]

jobs:
  axe-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: ".node-version"
          cache: "pnpm"
      - run: pnpm install --frozen-lockfile
      - run: pnpm test -- --testPathPattern="a11y|accessibility"
        name: Run axe-core component tests

  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: ".node-version"
          cache: "pnpm"
      - run: pnpm install --frozen-lockfile
      - run: pnpm build
      - run: pnpm dlx @lhci/cli autorun
        name: Lighthouse CI (accessibility >= 90)

  pa11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: ".node-version"
          cache: "pnpm"
      - run: pnpm install --frozen-lockfile
      - run: pnpm build && pnpm start &
      - run: npx wait-on http://localhost:3000 --timeout 30000
      - run: pnpm dlx pa11y-ci --config pa11y.config.js
        name: Pa11y CI (WCAG 2 AA)
```

All three jobs must pass. A PR with any accessibility failure is blocked from merging.

### Threshold Summary

| Tool | Gate | Threshold |
|------|------|-----------|
| axe-core (jest-axe, playwright-axe, cypress-axe) | Zero violations | 0 critical, 0 serious, 0 moderate |
| Lighthouse CI | Accessibility score | >= 0.9 (90%) |
| Pa11y | WCAG 2 AA | 0 errors |

## Component-Level Testing

### Individual Components

Every component that renders interactive or semantic HTML must have an axe-core test.

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe, toHaveNoViolations } from "jest-axe";

expect.extend(toHaveNoViolations);

describe("Dropdown", () => {
  test("has no accessibility violations when closed", async () => {
    // Arrange
    const { container } = render(<Dropdown options={options} />);

    // Act
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });

  test("has no accessibility violations when open", async () => {
    // Arrange
    const user = userEvent.setup();
    const { container } = render(<Dropdown options={options} />);

    // Act
    await user.click(screen.getByRole("combobox"));
    const results = await axe(container);

    // Assert
    expect(results).toHaveNoViolations();
  });

  test("supports keyboard navigation", async () => {
    // Arrange
    const user = userEvent.setup();
    render(<Dropdown options={options} />);

    // Act
    await user.tab();
    await user.keyboard("{Enter}");

    // Assert
    expect(screen.getByRole("listbox")).toBeVisible();
  });
});
```

### Composed Pages

Page-level tests verify that components integrate correctly: heading hierarchy is valid, landmarks are unique, tab order is logical across composed sections.

```typescript
test("dashboard page has valid heading hierarchy", async () => {
  // Arrange
  const { container } = render(<DashboardPage />);

  // Act
  const headings = container.querySelectorAll("h1, h2, h3, h4, h5, h6");
  const levels = Array.from(headings).map((h) =>
    parseInt(h.tagName.substring(1), 10)
  );

  // Assert — no skipped heading levels
  for (let i = 1; i < levels.length; i++) {
    expect(levels[i]).toBeLessThanOrEqual(levels[i - 1] + 1);
  }
});
```

### Dynamic Content

Modals, toasts, dropdowns, and other dynamic UI must be tested in both their hidden and visible states.

| Dynamic element | What to verify |
|-----------------|---------------|
| Modal/Dialog | Focus moves into dialog on open, traps inside, returns on close. `aria-modal="true"` present. Escape closes |
| Toast/Notification | Announced via `role="status"` or `role="alert"`. Auto-dismiss does not remove content before screen reader finishes reading. Minimum 5 seconds visible |
| Dropdown/Popover | Opens on Enter/Space, closes on Escape, arrow keys navigate options, selection announced |
| Accordion | `aria-expanded` toggles on the trigger, panel `id` linked via `aria-controls`, Enter/Space toggles |
| Loading skeleton | `aria-busy="true"` on the container while loading, removed when content arrives. Live region announces completion |

## Color and Contrast

### OKLCH-Aware Contrast Calculation

OKLCH provides perceptually uniform lightness, making contrast adjustments predictable. Use the contrast calculation from `standards/frontend.md` for programmatic verification.

Key rules:

- Body text on background: 4.5:1 minimum
- Large text (>= 18px bold or >= 24px): 3:1 minimum
- UI components, borders, focus rings: 3:1 against adjacent colors
- Disabled elements are exempt from contrast requirements, but must still be distinguishable from enabled elements

### Automated Contrast CI Checks

Integrate contrast checking into the build pipeline. Define color tokens centrally and validate all pairs at build time.

```typescript
// scripts/check-contrast.ts
import { oklchContrast } from "./oklch-contrast";

interface ColorPair {
  readonly name: string;
  readonly foreground: readonly [number, number, number]; // [L, C, H]
  readonly background: readonly [number, number, number];
  readonly minRatio: number;
}

const pairs: readonly ColorPair[] = [
  {
    name: "body text on background",
    foreground: [0.25, 0.01, 260],
    background: [0.99, 0.005, 260],
    minRatio: 4.5,
  },
  {
    name: "muted text on background",
    foreground: [0.55, 0.01, 260],
    background: [0.99, 0.005, 260],
    minRatio: 4.5,
  },
  {
    name: "primary on background",
    foreground: [0.45, 0.15, 260],
    background: [0.99, 0.005, 260],
    minRatio: 3.0,
  },
] as const;

let failures = 0;

for (const pair of pairs) {
  const ratio = oklchContrast(pair.foreground, pair.background);
  const pass = ratio >= pair.minRatio;

  if (!pass) {
    console.error(
      `FAIL: "${pair.name}" contrast ${ratio.toFixed(2)}:1 < ${pair.minRatio}:1`
    );
    failures++;
  }
}

if (failures > 0) {
  process.exit(1);
}
```

Add this as a build step: `pnpm check-contrast`. Zero failures to pass.

### Tool Recommendations

| Tool | Purpose | Integration point |
|------|---------|-------------------|
| axe-core color contrast rules | Catches contrast violations in rendered DOM | Automated tests via jest-axe, playwright-axe |
| Lighthouse accessibility audit | Flags contrast issues with affected elements | CI via @lhci/cli |
| Colour Contrast Analyser (desktop) | Manual spot-checks with eyedropper | Designer and developer workstations |
| OKLCH contrast script (from standards/frontend.md) | Validate design tokens at build time | CI build step |
| Chrome DevTools CSS Overview | Audit all colors used on a page and their contrast | Manual QA during development |

### Common Contrast Failures

| Element | Why it fails | Fix |
|---------|-------------|-----|
| Placeholder text | Often set to a light gray that fails 4.5:1 | Darken placeholder or use a visible label instead |
| Muted/secondary text | Decorative intent leads to insufficient contrast | Enforce 4.5:1 even for secondary text |
| Primary color as text | Brand blue/purple on white often fails | Use a darker shade for text, reserve the bright shade for large UI elements |
| Text on gradients or images | Contrast varies across the background | Add a semi-transparent overlay or text shadow to guarantee minimum contrast |
| Dark mode inversions | Swapping foreground and background without rechecking | Audit every color pair separately for dark mode |
| Disabled states | Gray-on-gray with no other visual distinction | Add a pattern, border, or opacity change alongside reduced contrast |

# Browser Testing

Standards for browser-based testing with Playwright, visual regression, and Core Web Vitals measurement.

## Test Architecture

### Page Object Pattern

Encapsulate page interactions behind a typed interface. Tests read as user stories, not DOM queries.

```typescript
// pages/login.page.ts
export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto(): Promise<void> {
    await this.page.goto('/login');
  }

  async login(email: string, password: string): Promise<void> {
    await this.page.getByLabel('Email').fill(email);
    await this.page.getByLabel('Password').fill(password);
    await this.page.getByRole('button', { name: 'Sign in' }).click();
  }

  async getErrorMessage(): Promise<string> {
    return this.page.getByRole('alert').textContent() ?? '';
  }
}
```

Rules:
- One page object per page or major component.
- Methods return `Promise<void>` for actions, `Promise<T>` for queries.
- Never expose Playwright locators directly. The page object is the API.
- Use role-based selectors (`getByRole`, `getByLabel`, `getByText`) over CSS selectors. They match how users and assistive technology interact with the page.

### Test Fixtures

Use Playwright's fixture system to share setup across tests. Never duplicate authentication, database seeding, or navigation.

```typescript
// fixtures.ts
import { test as base } from '@playwright/test';
import { LoginPage } from './pages/login.page';

export const test = base.extend<{ loginPage: LoginPage }>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
});
```

### Authentication State

Save and reuse authentication state to avoid logging in before every test.

```typescript
// global-setup.ts
async function globalSetup(config: FullConfig): Promise<void> {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.TEST_EMAIL);
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.context().storageState({ path: '.auth/state.json' });
  await browser.close();
}
```

Reference the saved state in `playwright.config.ts`:

```typescript
use: {
  storageState: '.auth/state.json',
}
```

## Selector Strategy

Prefer selectors in this order:

| Priority | Selector type | Example | Why |
|----------|--------------|---------|-----|
| 1 | Role | `getByRole('button', { name: 'Submit' })` | Mirrors accessibility tree. Catches a11y regressions |
| 2 | Label | `getByLabel('Email address')` | Tied to user-visible labels |
| 3 | Text | `getByText('Welcome back')` | Tied to user-visible content |
| 4 | Test ID | `getByTestId('checkout-total')` | Stable when content changes |
| 5 | CSS | `page.locator('.btn-primary')` | Last resort. Brittle against refactors |

Never use XPath. Never use `#id` selectors that depend on implementation details.

## Accessibility Tree Testing

Use the accessibility tree snapshot to verify semantic structure. This catches issues that visual inspection misses: missing labels, broken ARIA, wrong roles.

```typescript
const snapshot = await page.accessibility.snapshot();
expect(snapshot).toBeTruthy();

// Verify specific elements have correct roles
const submitButton = await page.getByRole('button', { name: 'Submit' });
await expect(submitButton).toBeVisible();
await expect(submitButton).toBeEnabled();
```

Combine with axe-core for automated WCAG compliance:

```typescript
import AxeBuilder from '@axe-core/playwright';

test('page passes WCAG AA', async ({ page }) => {
  await page.goto('/dashboard');
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
```

## Visual Regression Testing

### Screenshot Comparison

Use Playwright's built-in screenshot comparison for pixel-level regression detection.

```typescript
await expect(page).toHaveScreenshot('dashboard.png', {
  maxDiffPixelRatio: 0.01,
  animations: 'disabled',
});
```

Rules:
- Disable animations before capturing (`animations: 'disabled'`). Animations cause flaky diffs.
- Set a consistent viewport size. Different sizes produce different screenshots.
- Mask dynamic content (timestamps, avatars, random data) with `mask` option.
- Store baselines in version control. Review screenshot diffs in PRs.
- Run visual tests on a single OS in CI. Font rendering differs across platforms.

### Component-Level Screenshots

Capture individual components, not full pages, for targeted regression detection.

```typescript
const card = page.getByTestId('user-profile-card');
await expect(card).toHaveScreenshot('profile-card.png');
```

## Responsive Testing

Test all critical breakpoints. Define breakpoints from the project's Tailwind config or CSS custom properties.

```typescript
const breakpoints = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
];

for (const bp of breakpoints) {
  test(`renders correctly at ${bp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: bp.width, height: bp.height });
    await page.goto('/');
    await expect(page).toHaveScreenshot(`home-${bp.name}.png`);
  });
}
```

Verify:
- Navigation collapses to mobile menu at the right breakpoint.
- Grid columns adjust (1 on mobile, 2 on tablet, 3+ on desktop).
- Touch targets are at least 44x44px on mobile viewports.
- No horizontal overflow at any breakpoint.

## Core Web Vitals Measurement

### Largest Contentful Paint (LCP)

Target: under 2.5 seconds.

```typescript
const lcp = await page.evaluate((): Promise<number> =>
  new Promise((resolve) => {
    new PerformanceObserver((list) => {
      const entries = list.getEntries();
      resolve(entries.at(-1)?.startTime ?? 0);
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  })
);
expect(lcp).toBeLessThan(2500);
```

### Cumulative Layout Shift (CLS)

Target: under 0.1.

```typescript
const cls = await page.evaluate((): Promise<number> =>
  new Promise((resolve) => {
    let clsValue = 0;
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries() as PerformanceEntry[]) {
        if (!(entry as LayoutShiftAttribution).hadRecentInput) {
          clsValue += (entry as LayoutShiftAttribution).value;
        }
      }
    }).observe({ type: 'layout-shift', buffered: true });
    setTimeout(() => resolve(clsValue), 3000);
  })
);
expect(cls).toBeLessThan(0.1);
```

### Interaction to Next Paint (INP)

Target: under 200ms. Measure with Lighthouse CI or Web Vitals library in E2E tests.

### Lighthouse CI Integration

For comprehensive CWV measurement in CI:

```yaml
# lighthouserc.json
{
  "ci": {
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.9 }],
        "categories:accessibility": ["error", { "minScore": 0.9 }],
        "largest-contentful-paint": ["error", { "maxNumericValue": 2500 }],
        "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }]
      }
    }
  }
}
```

## Cookie and Session Management

For authenticated testing without re-logging in:

1. **Global setup approach:** log in once, save storage state, reuse across tests (see Authentication State above).
2. **Cookie injection:** for testing with specific user roles or states, set cookies directly.

```typescript
await context.addCookies([{
  name: 'session',
  value: 'test-session-token',
  domain: 'localhost',
  path: '/',
}]);
```

Never use real production cookies in tests. Generate test-specific tokens from a seed database.

## Test Isolation

- Each test gets a fresh browser context. No shared state between tests.
- Use `test.describe.configure({ mode: 'parallel' })` for independent tests.
- Use `test.describe.configure({ mode: 'serial' })` only when tests depend on prior state (multi-step workflows).
- Clean up created data in `afterEach` or use transactional rollback.
- Use unique test data per test to prevent collision in parallel runs.

## CI Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

- Retry flaky tests in CI but never locally. Flaky tests must be fixed, not retried indefinitely.
- Capture traces on failure for debugging. Traces include DOM snapshots, network requests, and console logs.
- Run with a single worker in CI if tests share external resources (database, API). Parallel locally.

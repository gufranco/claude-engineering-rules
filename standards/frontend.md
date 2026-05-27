# Frontend Design

## Typography

| Property | Value | Why |
|----------|-------|-----|
| Body text | 16px minimum (1rem) | Below 16px causes readability issues and triggers iOS zoom on inputs |
| Line height | 1.5 for body, 1.2 for headings | Tighter headings look intentional, looser body aids scanning |
| Line length | 45-75 characters (max-w-prose or max-w-2xl) | Beyond 75 chars, the eye loses its place when returning to the next line |
| Heading scale | Use a consistent ratio (1.25x or 1.333x) | Arbitrary sizes look amateur. Tailwind's text-sm/base/lg/xl/2xl/3xl follows a ratio |
| Font weight | max 2-3 weights per page | More weights slow load and create visual noise |
| text-balance | Apply to headings (text-balance) | Prevents orphaned words on short final lines |
| text-pretty | Apply to body paragraphs (text-pretty) | Improves word spacing and prevents awkward breaks |

Prefer system font stacks or self-hosted fonts via `next/font`. Never load fonts from external CDNs: it adds a blocking request and leaks user data.

### Avoiding Distributional Convergence

When generating new frontend code, Claude defaults to statistically average design choices from training data: Inter, Roboto, system fonts, purple gradients on white backgrounds, flat solid-color layouts. This produces generic interfaces that look indistinguishable from other AI-generated output.

To counter this when building new frontends:

- Choose distinctive fonts, not defaults. Avoid Inter, Roboto, Open Sans, Lato, and Arial for display text. Prefer fonts with character: editorial serifs like Playfair Display and Crimson Pro, technical sans like IBM Plex and Source Sans 3, distinctive choices like Bricolage Grotesque and Newsreader, or code-aesthetic monospace like JetBrains Mono and Fira Code for technical interfaces.
- Use extreme weight contrasts: 100/200 vs 800/900, not 400 vs 600. Size jumps of 3x or more for hierarchy, not 1.5x.
- Commit to a bold color direction. Dominant colors with sharp accents produce stronger designs than timid, evenly-distributed palettes.
- Create background depth. Layer CSS gradients, geometric patterns, noise textures, or contextual effects instead of flat solid colors.
- Vary across generations. Each new project gets a different aesthetic direction. If the previous output used Space Grotesk with a dark theme, the next one should not.

This guidance applies when creating new UIs, not when working within an existing design system that specifies its own fonts and colors.

## Spacing

Use Tailwind's spacing scale consistently. Pick one vertical rhythm and stick with it.

- **Section padding**: `py-20 sm:py-24`, 80 to 96 pixels, for major sections
- **Between section title and content**: `mt-12`, 48 pixels
- **Between cards in a grid**: `gap-6` at 24 pixels or `gap-8` at 32 pixels
- **Inside cards**: `p-6`, 24 pixels
- **Between text elements**: mt-2 or mt-4, never arbitrary values

Never mix spacing scales. If cards use gap-6, all card grids use gap-6. Consistency is more important than any individual spacing choice.

## Color and Contrast

WCAG AA is the minimum. Not optional, not a stretch goal.

| Pair | Minimum ratio |
|------|--------------|
| Body text on background | 4.5:1 |
| Large text on background (>= 18px bold or >= 24px) | 3:1 |
| UI components and focus indicators | 3:1 against adjacent colors |
| Decorative elements | No requirement |

When defining a color system:

- Test every foreground/background pair that will actually appear together
- Muted text for secondary copy, captions, and placeholders is the most common failure point
- Primary/accent colors used as text almost always fail on light backgrounds. Darken them
- OKLCH lightness, L is perceptually uniform. To increase contrast, decrease L for dark-on-light, increase L for light-on-dark
- Dark mode needs its own contrast check. Light mode passing does not guarantee dark mode passes

Use this Node.js snippet to verify OKLCH contrast ratios:

```javascript
// oklch-contrast.js, run with: node oklch-contrast.js
function oklchToOklab(L,C,H){const h=H*Math.PI/180;return{L,a:C*Math.cos(h),b:C*Math.sin(h)}}
function oklabToLinSrgb(L,a,b){const l=L+.3963377774*a+.2158037573*b,m=L-.1055613458*a-.0638541728*b,s=L-.0894841775*a-1.291485548*b;return{r:4.0767416621*l**3-3.3077115913*m**3+.2309699292*s**3,g:-1.2684380046*l**3+2.6097574011*m**3-.3413193965*s**3,b:-.0041960863*l**3-.7034186147*m**3+1.707614701*s**3}}
function linToSrgb(c){return c<=.0031308?12.92*c:1.055*c**(1/2.4)-.055}
function srgbToLin(c){return c<=.04045?c/12.92:((c+.055)/1.055)**2.4}
function relLum(r,g,b){return .2126*srgbToLin(Math.max(0,Math.min(1,r)))+.7152*srgbToLin(Math.max(0,Math.min(1,g)))+.0722*srgbToLin(Math.max(0,Math.min(1,b)))}
function oklchY(L,C,H){const lab=oklchToOklab(L,C,H),rgb=oklabToLinSrgb(lab.L,lab.a,lab.b);return relLum(linToSrgb(Math.max(0,rgb.r)),linToSrgb(Math.max(0,rgb.g)),linToSrgb(Math.max(0,rgb.b)))}
function cr(a,b){const x=Math.max(a,b),y=Math.min(a,b);return(x+.05)/(y+.05)}
// Usage: cr(oklchY(fgL,fgC,fgH), oklchY(bgL,bgC,bgH))
```

## Responsive Design

Mobile-first. Always. Write the mobile layout first, then add breakpoints for larger screens. Every page and component must be designed, built, and tested starting from the smallest screen.

### Device Validation (mandatory)

Every UI change must be verified on the smallest screens available on both platforms before shipping. These are the minimum validation targets:

| Platform | Device | Viewport | Density |
|:---------|:-------|:---------|:--------|
| Android | Galaxy S24 | 360x780 | 3x |
| Android | Galaxy A14 (budget) | 360x800 | 2x |
| iOS | iPhone SE (3rd gen) | 375x667 | 2x |
| iOS | iPhone 16 Pro | 393x852 | 3x |

Validation means: no horizontal scrolling, no overlapping elements, no truncated text that loses meaning, all touch targets at least 44x44px, all interactive elements reachable with one thumb. Use browser DevTools device mode, Playwright's device emulation, or real devices. DevTools is the minimum; real device testing is required for production releases.

If a layout does not work at 360px wide, it does not ship. This is blocking, not advisory.

### Breakpoints

| Breakpoint | Tailwind | Use for |
|------------|----------|---------|
| Default | (none) | Mobile: single column, stacked layout |
| sm (640px) | sm: | Large phones in landscape, minor adjustments |
| md (768px) | md: | Tablets: 2-column grids, side-by-side layouts |
| lg (1024px) | lg: | Desktop: 3+ column grids, horizontal nav |
| xl (1280px) | xl: | Wide desktop: max-width containers, extra whitespace |

### Common patterns

- **Grids**: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`. Never jump from 1 to 3
- **Navigation**: mobile hamburger/sheet below md, horizontal nav at md+
- **Hero height**: use `100dvh` instead of `100vh`. The `dvh` unit accounts for mobile browser chrome
- **Container**: `max-w-6xl mx-auto px-4 sm:px-6 lg:px-8`
- **Images**: always set width and height attributes, use `next/image` for photos
- **Text scaling**: `text-3xl sm:text-4xl lg:text-5xl` for headings, not arbitrary values
- **Overflow**: use `overflow-x: clip` not `overflow-x: hidden` on html/body to avoid breaking sticky positioning

### Touch targets

Minimum 44x44px or 2.75rem for all interactive elements on mobile. This includes buttons, links, icon buttons, and form controls. Add padding to small elements: `min-h-[2.75rem] min-w-[2.75rem]`.

## Accessibility

### Semantic HTML

Use the right element, not a styled div.

| Need | Use | Not |
|------|-----|-----|
| Navigation links | `<nav>` with `<a>` | `<div>` with `onClick` |
| Page sections | `<section>` with aria-labelledby | `<div>` |
| Cards with actions | `<article>` or semantic `<div>` | `<a>` wrapping everything |
| Lists of items | `<ul>` / `<ol>` | `<div>` with manual bullets |
| Form fields | `<label>` with `htmlFor` | `<span>` above an input |

### ARIA guidelines

- Every `<section>` needs `aria-labelledby` pointing to its heading's `id`
- Navigation landmarks need `aria-label`: "Main", "Footer", "Mobile"
- Decorative elements get `aria-hidden="true"`
- Icon-only buttons need `aria-label`
- SVG icons inside text get `aria-hidden="true"` because the text provides context
- Never use ARIA when a native HTML element does the job

### Focus management

- All interactive elements must have visible focus indicators
- Focus ring must have 3:1 contrast against adjacent colors
- Tab order must follow visual order. No positive `tabindex` values
- Skip-to-content link as first focusable element on the page

### Motion

- Wrap all animations in `@media (prefers-reduced-motion: no-preference)`
- Provide CSS fallback with `prefers-reduced-motion: reduce` that shows content without animation
- Never animate opacity from 0 in a way that hides content from users who disable motion. Use opacity: 1 and transform: none as the reduced-motion state

## Component Library

Use a headless or pre-built component library for all interactive UI elements. Never build custom implementations of components that the library already provides. Never use native HTML elements for complex interactions when a library component exists.

### Preferred stack

| Layer | Library | Why |
|:------|:--------|:----|
| Primitives | Radix UI | Headless, accessible, composable. Handles ARIA, keyboard navigation, focus management |
| Styled components | shadcn/ui | Radix + Tailwind. Copy-paste ownership, full control, consistent design tokens |
| Form handling | React Hook Form + Zod | Uncontrolled by default (performance), schema validation, typed errors |
| Data tables | TanStack Table | Headless, virtualized, sortable, filterable, framework-agnostic |
| Date picker | shadcn/ui date-picker (uses react-day-picker) | Accessible, locale-aware, range support |

### Native elements to avoid

| Instead of | Use | Why |
|:-----------|:----|:----|
| `<select>` | `Select` from shadcn/ui | Native select cannot be styled, has inconsistent behavior across browsers and mobile OS versions, and cannot support search, multi-select, or grouped options |
| `<input type="date">` | `DatePicker` from shadcn/ui | Native date input renders differently on every browser, cannot be styled, and has poor mobile UX on some Android devices |
| `<dialog>` | `Dialog` or `AlertDialog` from shadcn/ui | Native dialog has limited animation support, inconsistent backdrop behavior, and no built-in focus trap on older browsers |
| `window.confirm()` | `AlertDialog` from shadcn/ui | Blocks the main thread, cannot be styled, and shows different text on different browsers |
| `<input type="file">` | `Dropzone` component with drag-and-drop | Native file input cannot be styled and offers no drag-and-drop, preview, or validation UX |
| `<details>` / `<summary>` | `Accordion` from shadcn/ui | Native implementation cannot animate open/close and has limited ARIA support |
| `<input type="color">` | Custom color picker or OKLCH palette component | Native color picker varies wildly across browsers and does not support OKLCH or design tokens |

### When native is acceptable

- `<button>`: native button is correct for simple actions. Use the `Button` component from shadcn/ui for styled buttons, but `<button>` with custom styles is fine for icon buttons or minimal UI
- `<input type="text">`, `<textarea>`: native text inputs are acceptable when paired with the `Input` component from shadcn/ui for consistent styling. The native element is the base; the library wraps it
- `<a>`: native links are correct. Use `Link` from Next.js for client-side navigation
- `<form>`: native form element is the correct semantic choice. The library handles field rendering, not the form itself

### Rules

- Every interactive component must handle keyboard navigation across Tab, Enter, Escape, and arrow keys without custom code. This is why library components exist: they implement the WAI-ARIA patterns
- Never reimplement a component that the library provides. The library has been tested across browsers, screen readers, and devices. A custom implementation has not
- When the project uses shadcn/ui, use its components for all UI elements before considering alternatives. Only reach for a different library when shadcn/ui genuinely does not cover the use case
- When building a new project, install shadcn/ui as the first UI dependency. Configure it before writing any components

## Component Patterns

### Cards

- Consistent padding, `p-6`
- Hover state with subtle border color change (`hover:border-primary/30`), not shadow jumps
- If the card is clickable, the entire card should be the click target
- Card content order: icon/image, title, description, action

### Buttons

- Primary: filled background, high contrast text
- Secondary/outline: border, muted background on hover
- Full-width on mobile (`w-full sm:w-auto`), auto-width on desktop
- Loading state: disable button, show spinner + "Loading..." text
- Never rely on color alone to distinguish button variants. Add text or icons

### Forms

- Labels above inputs, not placeholder-only
- Error messages below the field, in destructive color
- Group related fields visually
- Submit button at the bottom, full-width on mobile
- Disable submit during pending state with visual feedback like a spinner
- All inputs need `name`, `id`, and matching `<label htmlFor>`

### Navigation

- Sticky header: `sticky top-0 z-50` with `backdrop-blur-lg` and semi-transparent background
- Scroll progress bar at the bottom of the header for long pages
- Mobile menu: use Sheet/drawer pattern, not a dropdown
- Active section highlighting with `IntersectionObserver` is optional and adds JS
- Language/theme controls in the header bar, not buried in a menu

## Images and Icons

- Small icons under 48 pixels: inline SVG, never image files. This eliminates HTTP requests
- Large illustrations: SVG if vector, WebP/AVIF with next/image if raster
- Decorative backgrounds: CSS gradients and blurs (`bg-primary/5 blur-3xl`), not images
- Logo: inline SVG with `currentColor` for theme compatibility
- Always add `aria-hidden="true"` to decorative SVGs
- Icon components accept `className` prop for sizing: `h-5 w-5`

## Animation

- Prefer CSS transitions over JS animation libraries
- Use `transition-colors` for hover states, `transition-opacity` for reveals
- Scroll-triggered animations: IntersectionObserver + CSS classes, not scroll event listeners with JS animations
- Keep durations short: 150ms for micro-interactions, 300-600ms for reveals
- Use `ease-out` for enters, `ease-in` for exits
- Always respect `prefers-reduced-motion`

## Performance Checklist

| Check | How |
|-------|-----|
| No external font requests | Self-host via next/font or system stack |
| No external script tags | No analytics, chat widgets, or trackers in initial load |
| Images optimized | next/image with width/height, lazy loading by default |
| Client JS minimized | Server Components by default, "use client" only when needed |
| No layout shift | Set explicit dimensions on images, fonts, and dynamic content |
| CSS-only where possible | Prefer Tailwind utilities over runtime CSS-in-JS |
| Tree-shakeable imports | Import specific components, not entire libraries |

## Web Performance

### Budgets

| Resource | Limit | Rationale |
|----------|-------|-----------|
| Total page weight | < 1.5 MB | Loads in ~4s on 3G |
| JavaScript (compressed) | < 300 KB | Main thread blocking above this threshold degrades INP |
| CSS (compressed) | < 100 KB | Render-blocking; keep critical CSS < 14 KB inlined |
| Above-fold images | < 500 KB total | Directly impacts LCP |
| Fonts | < 100 KB total | Avoid FOUT/FOIT; use variable fonts for multiple weights |
| Third-party scripts | < 200 KB total | Each script competes for main thread time |

### Metric Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| TTFB | < 800ms | CDN, edge caching, optimized backend |
| LCP | < 2.5s | 75th percentile, field data |
| FCP | < 1.8s | Critical CSS inlined, fonts non-blocking |
| INP | < 200ms | 75th percentile, field data |
| CLS | < 0.1 | 75th percentile, field data |
| TBT | < 200ms | Lab measurement |
| TTI | < 3.8s | Lab measurement |

### Resource Loading

- Preconnect to required origins: `<link rel="preconnect" href="https://domain.com">`
- Preload LCP image: `<link rel="preload" href="/hero.avif" as="image" fetchpriority="high">`
- Preload critical fonts: `<link rel="preload" href="/font.woff2" as="font" type="font/woff2" crossorigin>`
- Inline critical CSS under 14 KB for above-fold content
- Defer non-critical CSS with preload + onload pattern
- `defer` on non-essential scripts, `async` for independent scripts
- `type="module"` for ES modules, deferred by default

### Image Optimization

| Format | Use for | Browser support |
|--------|---------|----------------|
| AVIF | Photos, best compression | 92%+ |
| WebP | Photos, fallback for AVIF | 97%+ |
| PNG | Graphics with transparency | Universal |
| SVG | Icons, logos, illustrations | Universal |

LCP image attributes: `fetchpriority="high"`, `loading="eager"`, `decoding="sync"`, explicit `width`/`height` or `aspect-ratio`.

Below-fold images: `loading="lazy"`, `decoding="async"`.

Responsive images use a `<picture>` with an AVIF, then WebP, then JPEG fallback chain and multiple `srcset` breakpoints, 400w, 800w, 1200w typical.

### Font Loading

| Strategy | When to use |
|----------|------------|
| `font-display: swap` | Primary fonts. Show content immediately, swap when loaded |
| `font-display: optional` | Non-critical fonts. Skip if slow, prevents layout shift |
| `size-adjust` + `ascent-override` + `descent-override` | Match fallback metrics to web font to prevent CLS during swap |
| Variable fonts | When multiple weights are needed. Single file for weight range 100-900 |

System font stack as fallback: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`.

### JavaScript Optimization

- Route-based code splitting: `lazy(() => import('./Dashboard'))`
- Component-based splitting for heavy UI: `lazy(() => import('./HeavyChart'))`
- Tree shaking: import specific functions, not entire libraries
- Virtualize lists > 100 items with `content-visibility: auto` and `contain-intrinsic-size`

### Runtime Performance

- Batch DOM reads before writes. Never interleave reads and writes in a loop
- Debounce scroll and resize handlers. 100ms is typical
- `requestAnimationFrame` for visual updates synced with display refresh
- `requestIdleCallback` for non-critical work like analytics or prefetch
- Break long tasks over 50ms with yielding: `await new Promise(r => setTimeout(r, 0))`

### Third-Party Scripts

- Load with `async`: `<script async src="..."></script>`
- Delay until interaction using `IntersectionObserver` or a facade pattern with a static placeholder until user engages)
- Delay until DOMContentLoaded for non-critical integrations

### Core Web Vitals Debugging

```javascript
import { onLCP, onINP, onCLS } from "web-vitals";
onLCP(console.log);
onINP(console.log);
onCLS(console.log);
```

**LCP debugging**: identify the LCP element with `PerformanceObserver` for `largest-contentful-paint` entries. Common causes: slow TTFB, render-blocking CSS, unoptimized LCP image, client-side rendering delay.

**INP debugging**: observe `event` entries with `durationThreshold: 16`. Break down into input delay, < 50ms, processing time, < 100ms, presentation delay, < 50ms.

**CLS debugging**: observe `layout-shift` entries. Common causes: images without dimensions, web font FOUT, dynamically injected content above viewport, animations using `height`/`width`/`margin` instead of `transform`.

### Framework-Specific Optimizations

| Framework | LCP | INP | CLS |
|-----------|-----|-----|-----|
| Next.js | `<Image priority fill>` from `next/image` | `dynamic(() => import('./Heavy'), { ssr: false })` | `<Image>` handles dimensions automatically |
| React | `<link rel="preload" fetchpriority="high">` | `useTransition` for expensive state updates, `React.memo` for stable subtrees | Always specify `width`/`height` on `<img>` |
| Vue/Nuxt | `<NuxtImg preload loading="eager">` | Async components: `defineAsyncComponent(() => import('./Heavy.vue'))` | Bind `style="aspect-ratio: 16/9"` |

### Caching

| Resource | Cache-Control |
|----------|--------------|
| HTML | `no-cache, must-revalidate` |
| Static assets (JS, CSS, images) | `public, max-age=31536000, immutable` |
| API responses | `private, max-age=0, must-revalidate` |

Use a CDN for global distribution. Enable Brotli compression for 15 to 20 percent smaller payloads than Gzip.

### Measurement

- Lab: Chrome DevTools Performance panel, Lighthouse CLI, WebPageTest
- Field: Chrome User Experience Report or CrUX, Google Search Console, `web-vitals` library sent to analytics
- Lighthouse CLI: `npx lighthouse https://example.com --output html --output-path report.html`

## SEO

Skip this section if the project is not a public-facing web application.

### Title Tags

- 50-60 characters. Google truncates at ~60
- Primary keyword near the beginning
- Unique for every page
- Brand name at end unless homepage

### Meta Descriptions

- 150-160 characters
- Include primary keyword naturally
- Compelling call-to-action
- Unique for every page

### Heading Structure

- Single `<h1>` per page representing the main topic
- Logical hierarchy: never skip levels. H1 then H2 then H3, not H1 then H3
- Include keywords naturally

### Canonical URLs

Prevent duplicate content: `<link rel="canonical" href="https://example.com/page">`. Self-referencing canonical on the canonical URL itself.

### Structured Data (JSON-LD)

Add JSON-LD for the content type. Common schemas:

| Content type | Schema |
|-------------|--------|
| Business/app | `Organization` with `name`, `url`, `logo`, `contactPoint` |
| Blog post | `Article` with `headline`, `author`, `datePublished`, `dateModified` |
| Product page | `Product` with `name`, `offers`, `aggregateRating` |
| FAQ page | `FAQPage` with `mainEntity` array of `Question`/`Answer` |
| Navigation | `BreadcrumbList` with `itemListElement` |

Validate with Google Rich Results Test.

### robots.txt

```
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /private/
Sitemap: https://example.com/sitemap.xml
```

### XML Sitemap

- Maximum 50,000 URLs or 50 MB per sitemap file
- Use sitemap index for larger sites
- Include only canonical, indexable URLs
- Update `lastmod` when content changes
- Submit to Google Search Console

### International SEO

Use `hreflang` tags when serving content in multiple languages:

```html
<link rel="alternate" hreflang="en" href="https://example.com/page">
<link rel="alternate" hreflang="pt-BR" href="https://example.com/pt-br/page">
<link rel="alternate" hreflang="x-default" href="https://example.com/page">
```

Declare page language: `<html lang="en">`. Mark language changes inline: `<span lang="pt">texto</span>`.

### Mobile SEO

- Viewport: `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Body font size: 16px minimum
- Tap targets: 48x48px minimum with 12px padding

## Core Web Vitals Performance Budget

| Metric | Target | Buffer below threshold |
|--------|--------|----------------------|
| LCP | Under 2.0s | 2.5s threshold |
| INP | Under 150ms | 200ms threshold |
| CLS | Under 0.05 | 0.1 threshold |

Resource budgets:

| Resource | Limit |
|----------|-------|
| JavaScript | Under 300KB compressed |
| CSS | Under 80KB compressed |
| Hero image | Under 200KB |
| Total page weight | Under 1.5MB |
| Third-party scripts | Maximum 5 |

Rules:

- Set `width` and `height` on all images, videos, and iframes. Missing dimensions are the primary CLS cause globally
- Use `fetchpriority="high"` on LCP images. Preload LCP resources
- Break long tasks using `scheduler.yield()`. Never perform synchronous DOM manipulation in event handlers
- Set CI alerts at 80% of thresholds: INP >160ms, LCP >2.0s, CLS >0.08
- Optimize for CrUX real user data, not Lighthouse synthetic scores

## AI Slop Detection

When reviewing AI-generated frontend code, check for these telltale patterns:

- Purple/blue gradient backgrounds with no design rationale
- 3-column feature grids with icons in colored circles
- Centered-everything layout with no visual hierarchy
- Uniform bubbly border-radius on all elements
- Generic hero section with stock copy like "Transform Your Workflow"
- Identical card components repeated without variation

Flag these patterns during `/review design`. They signal template-generated UI that lacks intentional design decisions.

## Anti-Template Policy

The AI Slop list above is the diagnostic. This section is the policy. Every meaningful surface must pass two checks: it does not match a banned pattern, and it carries at least four of the ten qualities listed below. A surface that fails either check is sent back to design before it ships.

### Banned patterns

| Pattern | Why it is banned |
|---------|------------------|
| Default card grid | A 3 or 4-column grid of equal-height cards is the visual signature of "I needed to fill a screen". Real information has hierarchy. |
| Stock hero | Centered headline + sub-headline + one button + a vague background image. The reader does not know what the product does after reading it. |
| Unmodified library defaults | shadcn out of the box, MUI out of the box, Bootstrap out of the box. The components are fine; using zero customization on every surface is the tell. |
| Dashboard by numbers | KPI tile row across the top, line chart middle, table bottom. No question is being answered; the surface is a metric warehouse. |
| Gradient bath | Linear gradient on every container. Color carries no meaning. |
| Icon-circle row | Each feature gets a colored circle with a generic icon. The icons are interchangeable; the reader cannot tell features apart. |
| Lorem ipsum content | Including "Lorem ipsum"-adjacent prose like "Lorem ipsum dolor", "Sample text here", "Your content here". Ship empty states, not fake content. |
| Toy testimonials | Three stock photos of smiling people with first-name-only quotes praising the product in superlatives. |
| Trust-badge wall | Logos of "trusted by" companies you do not actually serve. |
| Animation parade | Every element fades, slides, or scales on scroll. Motion is decoration, not communication. |

### Required qualities (at least four per meaningful surface)

| Quality | Definition |
|---------|------------|
| Specific copy | Headlines and labels name a concrete benefit, action, or value. No "transform", "elevate", "unlock". |
| Information hierarchy | A first-time reader can name the most important element on the surface in under two seconds. |
| Density discipline | Whitespace correlates with importance, not with "modern look". Dense areas convey lots; airy areas convey one thing. |
| Color with meaning | Color is used to encode state, severity, or category. Not for decoration. Each hue maps to a documented purpose. |
| Typographic contrast | At least three distinct text styles in the visual hierarchy. Headings, body, captions are visibly different on weight, size, and color. |
| Custom illustration or imagery | Photography or illustration produced for the product, not pulled from a stock library. |
| Realistic empty state | The empty state shows what the user can do, not "no data". |
| Functional motion | Motion is used to clarify a transition or guide attention to a change, not to decorate idle state. |
| Edge-case fidelity | Long names, missing fields, zero state, error state, loading state all rendered correctly with intent. |
| Accessibility above the bar | Visible focus rings, perceivable contrast in light AND dark mode, real keyboard navigation, real screen-reader labels. |

A meaningful surface is one a user spends real time on or makes a decision in. Landing pages, dashboards, editors, forms, app shells, settings panels are meaningful. Modal confirmations, toast notifications, and decorative chrome are not.

### Operational use

- During `/review design`, score the surface against banned patterns and required qualities. Report banned patterns as blockers, missing qualities as required-fix.
- During `/plan` for a new UI feature, name the four qualities the surface will carry **before** any code is written.
- During design system work, the system itself must offer first-class support for at least six of the ten qualities so individual surfaces have a low cost to comply.

## React Compiler

React Compiler is stable as of React 19 and ships as part of React 19. It analyzes components at build time and inserts memoization automatically. Manual `useMemo`, `useCallback`, and `React.memo` calls become unnecessary in the common case.

| Old pattern | New pattern under the compiler |
|------------|--------------------------------|
| `useMemo(() => expensive(x), [x])` | Plain expression: `const result = expensive(x);` |
| `useCallback((e) => onChange(e), [onChange])` | Plain inline function: `(e) => onChange(e)` |
| `React.memo(Component)` | Wrap only when profiling shows a real win |
| Reducer composition to avoid re-renders | Use plain state; the compiler skips unaffected branches |

Rules that the compiler depends on, and which must be enforced even more strictly when it is on:

- Components and hooks must be pure. No side effects during render
- Props, state, and JSX are immutable values, never mutated in place
- Hooks run only in component or hook bodies, never inside loops or conditionals
- Refs read or write only inside effects or event handlers
- The compiler skips files or components it cannot prove are pure. A silent skip means the optimization did not happen

Configuration:

- Enable via `babel-plugin-react-compiler` for Babel-based pipelines, or the equivalent Vite, Next.js, or Metro plugin
- Add the `eslint-plugin-react-compiler` rules to catch Rules-of-React violations at lint time. Treat the rules as errors, not warnings
- The `React Compiler Health Check` page in React DevTools shows which components were optimized and which were skipped

When NOT to keep manual memoization:

- Code that runs without the compiler enabled, like older bundles or library code shipped to consumers
- Performance-critical paths where profiling has demonstrated a measurable improvement from manual memoization
- Server Components: the compiler does not optimize them because they render once and stream

Remove manual `useMemo` and `useCallback` calls in the same PR that enables the compiler. Leaving them creates noise and double-work that the compiler must reason around.

## Tailwind Conventions

- Use semantic color tokens like `bg-background`, `text-foreground`, and `text-muted-foreground`, not raw colors
- Dark mode via CSS class strategy with `@custom-variant dark (&:is(.dark *))`
- Consistent radius: define `--radius` once, use `rounded-lg`, `rounded-md`, `rounded-sm`
- Consistent shadow scale: `shadow-sm` for subtle, `shadow-md` for cards, `shadow-lg` for modals
- Avoid `@apply` in CSS files. Write utilities in JSX. Exception: base styles in `@layer base`
- Group responsive variants left-to-right: `text-sm md:text-base lg:text-lg`

## Related Standards

- [`standards/accessibility-testing.md`](accessibility-testing.md): Accessibility Testing
- [`standards/performance-budgets.md`](performance-budgets.md): Performance Budgets
- [`standards/browser-testing.md`](browser-testing.md): Browser Testing

# View route

For questions about presentation, layout, or visual style.

## Goal

Place several radically different visual approaches side by side on one route so the user can flip between them and pick. Variations must differ in concept, not in detail. Three font sizes is not three variations.

## Shape

Judge variants inside the app they will live in. A variant on an empty route looks fine in isolation; the real header, sidebar, data, and density expose the problems.

- **Existing page, the default.** Render the variants on the route that already exists, or inside the page that would host the new section, card, or step. The page keeps its data fetching, params, and auth; only the rendered subtree swaps per variant.
- **New route, the last resort.** Only when nothing in the app could host the variants, create a route named `spike-<short-slug>` under the project's existing routing convention. Confirm first that no existing page fits.

In both shapes:

- A query string parameter selects the variant: `?v=1`, `?v=2`, `?v=3`. Default to three variants and cap at five.
- Each variant lives in its own component file and receives the page's real data.
- A small floating selector switches the variant and updates the query string through the framework router, so a variant is shareable and survives a reload. Arrow keys also cycle, except while focus is in an input, a textarea, or a contenteditable element.
- The selector is dev-only: gate it on the build-time flag or config value the project already uses for development tooling, so a stray merge cannot ship it.
- A banner at the top names the question and lists the variant ideas.

## What "radically different" means

- Variant 1 and variant 2 differ in information hierarchy, not in color.
- Variant 1 and variant 2 differ in interaction pattern, not in icon style.
- Variant 1 and variant 2 differ in spatial layout, not in spacing.

If the user cannot tell which variant they prefer at a glance, the variants are not different enough. Throw them away and pick more divergent directions.

## What to skip

- Pixel-perfect spacing, accessibility polish, internationalization. Those land in the real implementation.
- Mock data. Variants read the page's real data; mock data hides the density and edge cases the question is about.
- Real writes. When a variant needs to mutate, point it at a stub, since the question is how it looks, not whether the backend works.
- State management beyond what each variant needs.

## Verdict capture

When the user has picked, record the verdict where the work continues:

```
Question: how should the dispatch board surface overdue jobs?
Variants tried: V1 ribbon at top; V2 inline badge on each row; V3 filter chip.
Verdict: V2 inline badge. V1 was missed when the user scrolled; V3 hid the badge behind a click.
Evidence: branch spike/dispatch-overdue
```

Then rebuild the winner properly in the real code, with tests, since the variant was written without them. Commit every variant and the selector to `spike/<slug>` as [`SKILL.md`](SKILL.md) describes, and remove them from the working branch. If the verdict is hard to reverse, call the Skill tool with `plan` and the arguments `adr new <title>` first, and link the ADR.

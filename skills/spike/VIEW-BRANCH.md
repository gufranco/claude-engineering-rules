# View route

For questions about presentation, layout, or visual style.

## Goal

Place several radically different visual approaches side by side on one route so the user can flip between them and pick. Variations must differ in concept, not in detail. Three font sizes is not three variations.

## Shape

A single route under the project's existing routing convention, named `spike-<short-slug>`. Inside the route:

- A query string parameter selects the variant: `?v=1`, `?v=2`, `?v=3`.
- A small floating selector (corner of the viewport) switches the variant without reloading.
- Each variant lives in its own component file.
- A banner at the top names the question and lists the variant ideas.

## What "radically different" means

- Variant 1 and variant 2 differ in information hierarchy, not in color.
- Variant 1 and variant 2 differ in interaction pattern, not in icon style.
- Variant 1 and variant 2 differ in spatial layout, not in spacing.

If the user cannot tell which variant they prefer at a glance, the variants are not different enough. Throw them away and pick more divergent directions.

## What to skip

- Pixel-perfect spacing, accessibility polish, internationalization. Those land in the real implementation.
- Real data. Use mock data inline so the spike survives offline.
- State management beyond what each variant needs.

## Verdict capture

When the user has picked, write a `NOTES.md` next to the spike:

```
Question: how should the dispatch board surface overdue jobs?
Variants tried: V1 ribbon at top; V2 inline badge on each row; V3 filter chip.
Verdict: V2 inline badge. V1 was missed when the user scrolled; V3 hid the badge behind a click.
```

Then delete the spike directory. If the verdict is hard to reverse, run `/plan adr new` first and link the ADR.

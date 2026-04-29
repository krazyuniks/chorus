# design-system

Wholesale, in-tree copy of the Dense family plus tokens and contracts from a sibling design-system project. The frontend is intentionally self-contained: there is no workspace linkage, no published package, no upstream tracking.

## What is here

```
design-system/
  tokens/
    foundation.css        Immutable design scale (spacing, radii, shadows, easings, durations, z-index).
    preset.css            Tailwind v4 @theme inline mapping from CSS custom properties to utilities.
    themes/
      neutral.css         Default brand palette and light/dark mode CSS variables.
  contracts/              TypeScript prop interfaces grouped by category.
    surfaces/             Card.
    navigation/           TopBar.
    content/              Hero (kept available, not used in the Lighthouse views).
    forms/                Input.
    actions/              Button.
    feedback/             Alert.
    data/                 Reserved for future table/timeline contracts.
    layout/               Reserved for future container contracts.
  designs/
    dense/                Dense-family component implementations. The other families (minimal, glass, editorial) are out of scope for Chorus.
      actions/Button.tsx
      content/Hero.tsx
      feedback/Alert.tsx
      forms/Input.tsx
      navigation/TopBar.tsx
      surfaces/Card.tsx
  index.ts                Barrel re-exports for the dense components and contract types.
```

## Boundary rules

- Dense components import contract types via relative paths only. No external package references exist anywhere under this directory.
- Routes and shared components depend on `@/design-system` (the barrel) or directly on a specific dense component path. They never reach into a contract file.
- Adding a new component means: write the contract under `contracts/<category>/`, write the dense implementation under `designs/dense/<category>/`, and re-export from `index.ts`.

## Chorus design constraints

The Lighthouse UI is a dense, data-first inspection surface. `Card` and `Hero` are present for completeness, but the Phase 1 routes deliberately do not use them — Chorus uses tables, timelines, and plain detail views instead.

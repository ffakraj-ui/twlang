# Dead Code Detection

TW Framework can detect unused files in your project.

## Running Detection

```bash
tw dead
```

Or during build:

```bash
tw build --prod
```

Dead code warnings appear in the build output.

## What Is Detected

| Category | Description |
|---|---|
| Orphaned pages | `.tw` files in `pages/` not linked from any other page |
| Unused components | `.tw` files in `components/` never imported |
| Unused layouts | `.tw` files in `layouts/` never referenced in `page { layout "..." }` |
| Unused API routes | `.twm` files never called |
| Unused middleware rules | Rules in `middleware.tw` that don't match any route |

## Output Example

```
Dead Code Report:
  Unused components:
    - [home]/components/OldButton.tw
    - [home]/components/DeprecatedCard.tw
  Unused layouts:
    - [home]/layouts/legacy.tw
  Orphaned pages:
    - [home]/old-promo.tw
```

## Removing Dead Code

Simply delete the files listed in the report. Then rebuild to confirm:

```bash
rm [home]/components/OldButton.tw
tw build --prod
```

## False Positives

If a page is linked dynamically (e.g., via JavaScript redirect), TW may flag it as orphaned. To suppress:

- Add a comment: `// @tw-keep` at the top of the file
- Or reference it in another page's `load` directive

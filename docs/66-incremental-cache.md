# Incremental Cache

## How It Works

TW caches compiled pages in `.tw/` directory.

## Cache Validation

On rebuild, TW checks:
1. Has the .tw file changed? (hash comparison)
2. Have any imported components changed?
3. Have any loaded stylesheets changed?
4. Have any layouts changed?

If nothing changed -> cache hit -> skip compilation.

## Dependency Graph

TW tracks dependencies:

```
pages/index.tw depends on:
  - components/Hero.tw
  - components/Button.tw
  - layouts/main.tw
  - style/site.tss
```

If `components/Button.tw` changes, only pages that import Button are recompiled.

## Forcing a Full Rebuild

```bash
tw build --force
# or
tw clean && tw build
```

## Cache and Version Upgrades

After upgrading TW Framework, clean cache:

```bash
tw clean
tw build --prod
```

## Cache Hit Rate

Monitor cache effectiveness:

```bash
tw build --report
```

A high hit rate (>80%) means fast incremental builds.

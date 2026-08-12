# Build Report

## Generating a Report

```bash
tw build --prod --report
```

## Report Contents

### Build Summary
- Pages compiled
- Components resolved
- Layouts applied
- API routes
- Build duration
- Cache hit rate

### Output Sizes
- Total size
- HTML size (per file)
- CSS size
- JS size
- Other assets

### Per-Page Breakdown
- Route path
- HTML size
- JS chunk size (0 for static pages)

### Chunk Analysis
- Shared runtime chunk size (~2KB)
- Page-specific chunk sizes

### Performance Metrics
- Average page weight
- Pages with JS vs without
- Gzip/Brotli savings

## Build Analyze

```bash
tw build --prod --analyze
```

Provides dependency graph showing which components are used where.

## Compiler Statistics

```bash
tw build --prod
```

Output includes:
- build_duration_seconds
- pages_compiled
- components_compiled
- files_reused_from_cache
- cache_hit_rate

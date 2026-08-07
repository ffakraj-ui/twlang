# Debugging Guide

## tw check

```bash
tw check [home]/pages/index.tw
```

Prints diagnostics: errors, warnings, suggestions.

## tw tokens

```bash
tw tokens [home]/pages/index.tw
```

Shows all lexer tokens with line/col.

## tw ast

```bash
tw ast [home]/pages/index.tw
```

Shows the AST as JSON.

## tw ir

```bash
tw ir [home]/pages/index.tw
```

Shows the IR (Intermediate Representation).

## tw doctor

```bash
tw doctor
```

Runs health checks: config validation, env schema, port availability, file structure, WebSocket routes, .gitignore hygiene.

## Build Debug

```bash
tw build --prod --debug
```

Verbose output showing every step of the build pipeline.

## Build Report

```bash
tw build --prod --report
```

Generates a build report with sizes, timing, and cache stats.

## Common Debug Scenarios

### Page renders blank

1. Check `tw check [home]/pages/index.tw`
2. Check `page { render static }` is set
3. Check `body {}` block exists
4. Check layout exists if `layout "main"` is set

### Styles not loading

1. Check `load "@./style.tss"` exists
2. Run `tw check [home]/style.tss`
3. Check class names match between .tw and .tss

### Component not rendering

1. Check `import "Component"` exists
2. Check file at `[home]/components/Component.tw`
3. Check component has content in its body

### API returns 404

1. Check `.twm` file at correct path
2. Check file name: `route.twm` for directory routes
3. Check `tw info` shows the API route

### Clear cache and rebuild

```bash
tw clean
tw build --prod --force
```

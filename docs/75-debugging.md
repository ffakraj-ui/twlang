# Debugging

## tw check

```bash
tw check [home]/pages/index.tw
tw check [home]/pages/index.tw --diagnostics
tw check [home]/style.tss
```

## tw doctor

```bash
tw doctor
```

Checks: project structure, config, env schema, port, WebSocket routes, .gitignore.

## tw info

```bash
tw info
```

Shows: pages, components, layouts, API routes, middleware rules.

## tw tokens / tw ast / tw ir

```bash
tw tokens [home]/pages/index.tw
tw ast [home]/pages/index.tw
tw ir [home]/pages/index.tw
```

## Build Debug Mode

```bash
tw build --prod --debug
```

## Console Logging

```js
export function GET(request) {
    console.log('Request:', request.method, request.url)
    console.log('Headers:', request.headers)
    return { status: 200, json: { ok: true } }
}
```

## Common Debugging Scenarios

### Page renders blank
1. Check `tw check [home]/pages/index.tw`
2. Verify `page {}` block exists
3. Verify `body {}` block exists
4. Check for unclosed braces

### Styles not applying
1. Check `.tss` file loaded
2. Run `tw check [home]/style.tss`
3. Check selector matches element class

### API route 404
1. Verify file is in `[home]/api/`
2. Check file extension is `.twm`
3. For nested: `users/route.twm`

### Component not rendering
1. Check `import "ComponentName"` exists
2. Verify file at `[home]/components/ComponentName.tw`
3. Check spelling

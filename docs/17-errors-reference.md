# Error Reference

## Lexer Errors

### Unterminated string literal

```
Error: Unterminated string literal
Location: line 5, col 9
```

**Cause:** Missing closing quote in a string.

**Fix:**
```tw
// Wrong
h1 "Hello

// Right
h1 "Hello"
```

### Unterminated `script { ... }` block

```
Error: Unterminated `script { ... }` block
```

**Cause:** `script {` opened but never closed with `}`.

**Fix:** Add matching `}`.

## Parser Errors

### Expected `{` after `page`

```
Error: Expected `{` after `page`
```

**Cause:** Missing opening brace after `page` keyword.

**Fix:**
```tw
page {        // Don't forget the {
    title "Home"
}
```

### Unknown key inside `page`: `rendre`

```
Error: Unknown key inside `page`: `rendre`
Suggestion: Use `title`, `layout`, `render`, `revalidate`, `cache_by`, `cache_size`, `redirect`, or `rewrite`.
```

**Cause:** Typo in page block key.

**Fix:** Use one of the valid keys: `title`, `layout`, `render`, `revalidate`, `cache_by`, `cache_size`, `redirect`, `rewrite`.

### Unsupported render mode: `dynamic`

```
Error: Unsupported render mode: `dynamic`
Suggestion: Use `static`, `server`, or `edge`.
```

**Fix:** Use `static`, `server`, or `edge`.

### Missing closing `}` for `page` block

```
Error: Missing closing `}` for `page` block
Suggestion: The closing `}` for `page { ... }` appears to be missing.
```

**Fix:** Add `}` at the end of the page block.

## Component Errors

### Component `Hero` not found

```
Error: Component `Hero` not found
```

**Cause:** `import "Hero"` used but no `Hero.tw` in `components/`.

**Fix:**
- Create `[home]/components/Hero.tw`
- Check spelling (case-insensitive but must match)

### Component name cannot be empty

```
Error: Component name cannot be empty
```

**Cause:** `import ""` or empty component reference.

### Expected component name after `import`

```
Error: Expected component name after `import`
```

**Cause:** `import` keyword with no component name.

**Fix:** `import "Hero"`

## Layout Errors

### Layout `main` not found

```
Error: Layout `main` not found
```

**Fix:** Create `[home]/layouts/main.tw` or use correct name.

## Load Errors

### load: file not found for `@./style/site.tss`

```
Error: load: file not found for `@./style/site.tss`
```

**Cause:** The `load` path doesn't resolve.

**Fix:**
- Check path is relative to `[home]/`
- `@./` means relative to `[home]/` directory
- Check file extension is correct

### Expected path after `load`

```
Error: Expected path after `load`
```

**Cause:** `load` without a path.

**Fix:** `load "@./style.tss"`

## Control Flow Errors

### Missing condition in `if` block

```
Error: Missing condition in `if` block
```

**Fix:** `if isLoggedIn { ... }`

### Expected `{` after `if` condition

```
Error: Expected `{` after `if` condition
```

**Fix:** `if condition { ... }`

### Expected loop variable after `for`

```
Error: Expected loop variable after `for`
```

**Fix:** `for item in items { ... }`

### Expected `in` inside `for` loop

```
Error: Expected `in` inside `for` loop
```

**Fix:** `for item in items { ... }`

### Expected `as <var>` inside `each`

```
Error: Expected `as <var>` inside `each`
```

**Fix:** `each items as item { ... }`

## Build Errors

### TW project root not found

```
RuntimeError: TW project root not found.
```

**Cause:** `[home]` directory missing or named incorrectly.

**Fix:** Rename source directory to `[home]` (with literal square brackets).

### No config file found

```
Error: No config file found
```

**Fix:** Create `tw.config` at project root with at least `name: My Site`.

## Type Safety Errors

### Unknown type `integer`

```
Error: Unknown type `integer`. Valid types: any, array, boolean, null, number, object, string
```

**Cause:** A type annotation used an unrecognized type name.

**Fix:** Use one of the valid types — `string`, `number`, `boolean`, `array`, `object`, `null`, `any`.

```tw
// Wrong
let x: integer = 5

// Right
let x: number = 5
```

### Type error: `count` is annotated as `number` but got `string`

```
Error: Type error: `count` is annotated as `number` but got `string`.
```

**Cause:** The value assigned to a `let` (or `state`) variable does not match its declared type annotation.

**Fix:** Change the value to match the annotation, or update the annotation.

```tw
// Wrong
let count: number = "hello"

// Right
let count: number = 5
let count: string = "hello"
```

## Vercel Deployment Errors

### externally-managed-environment

```
error: externally-managed-environment × This environment is externally managed
```

**Fix:** Add `--break-system-packages` to pip install in `vercel.json`.

### tw: command not found

```
sh: line 1: tw: command not found
```

**Fix:** Use `python -m tw_framework.cli` instead of `tw` in build command.

## TSS Errors

### Property value `true`

If you see `true` appearing as a CSS value, this is the multi-line value bug (pre-v0.4.3).

**Fix:** Upgrade to v0.4.3+ or keep CSS values on a single line.

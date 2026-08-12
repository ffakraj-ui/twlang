# Build and Compilation Errors

Comprehensive guide to every build error, compilation failure, and diagnostic in TW Framework.

## Understanding Diagnostics

TW Framework uses a diagnostic system with error codes, messages, suggestions, and locations.

### Diagnostic Format

```
[ERROR] TW1000: Unexpected token '}' at line 5, col 12
    File: [home]/index.tw
    Suggestion: Check for matching braces.

    4 |     body {
    5 |         h1 "Hello"
    6 |     }
```

### Severity Levels

| Level | Color | Meaning |
|-------|-------|---------|
| ERROR | Red | Build fails, no output |
| WARNING | Yellow | Build succeeds, issues |
| INFO | Blue | Informational |
| HINT | Gray | Suggestion |

## Lexer Errors (TW1000-TW1099)

### TW1000: Unexpected Token

**Cause:** Lexer encountered unexpected character.

```tw
// WRONG
body {
    h1 "Hello" @
}
```

**Error:**
```
[ERROR] TW1000: Unexpected token '@' at line 3, col 16
    Suggestion: Remove unexpected character.
```

**Fix:** Remove the unexpected character.

### TW1001: Unterminated String

**Cause:** String missing closing quote.

```tw
// WRONG
page {
    title "Home
}
```

**Error:**
```
[ERROR] TW1001: Unterminated string at line 2, col 11
    Suggestion: Add closing double quote.
```

**Fix:** Close the string.

```tw
// CORRECT
page {
    title "Home"
}
```

### TW1002: Invalid Indentation

**Cause:** Mixed tabs and spaces or wrong level.

```tw
// WRONG
page {
    title "Home"
	render static
}
```

**Error:**
```
[ERROR] TW1002: Invalid indentation at line 3, col 1
    Suggestion: Use 4 spaces. Do not mix tabs and spaces.
```

**Fix:** Use consistent 4-space indentation.

## Parser Errors (TW2000-TW2099)

### TW2000: Missing Required Block

**Cause:** Missing `page` or `body` block.

```tw
// WRONG
h1 "Hello"
```

**Error:**
```
[ERROR] TW2000: Missing 'page' block at line 1, col 1
    Suggestion: Add 'page { title "..." }'.
```

**Fix:** Add required block.

```tw
// CORRECT
page {
    title "Home"
}

body {
    h1 "Hello"
}
```

### TW2001: Invalid Page Property

**Cause:** Unknown property in `page` block.

```tw
// WRONG
page {
    title "Home"
    theme "dark"
}
```

**Error:**
```
[ERROR] TW2001: Invalid property 'theme' at line 3, col 5
    Valid: title, layout, render, revalidate
```

**Fix:** Use valid properties.

```tw
// CORRECT
page {
    title "Home"
    layout "main"
}
```

### TW2002: Import Not Found

**Cause:** Component doesn't exist.

```tw
// WRONG
import "NonExistent"
```

**Error:**
```
[ERROR] TW2405: Component 'NonExistent' not found
    Searched: [home]/components/NonExistent.tw
```

**Fix:** Create file or fix path.

### TW2003: Invalid Block Nesting

**Cause:** Block in wrong location.

```tw
// WRONG
body {
    head {
        seo { description "Test" }
    }
}
```

**Error:**
```
[ERROR] TW2003: 'head' cannot appear inside 'body'
    Suggestion: Move 'head' before 'body'.
```

**Fix:** Place blocks in correct order.

## Semantic Errors (TW3000-TW3099)

### TW3001: Undefined Variable

**Cause:** Using undeclared variable.

```tw
// WRONG
body {
    h1 "{title}"
}
```

**Error:**
```
[ERROR] TW3001: Variable 'title' not defined at line 2, col 9
    Suggestion: Add 'let title = "..."' before body.
```

**Fix:** Declare the variable.

```tw
// CORRECT
let title = "Home"

body {
    h1 "{title}"
}
```

### TW3002: Type Mismatch

**Cause:** Wrong value type.

```tw
// WRONG
let count = "five"

body {
    if count > 0 {
        p "Positive"
    }
}
```

**Warning:**
```
[WARNING] TW3002: Type mismatch at line 4, col 8
    Expected: number, Found: string
```

**Fix:** Use correct type.

```tw
// CORRECT
let count = 5

body {
    if count > 0 {
        p "Positive"
    }
}
```

### TW3003: Invalid Condition

**Cause:** `if` without condition.

```tw
// WRONG
body {
    if {
        p "Always true"
    }
}
```

**Error:**
```
[ERROR] TW3003: 'if' missing condition at line 2, col 5
```

**Fix:** Add condition.

```tw
// CORRECT
let show = true

body {
    if show {
        p "Shown"
    }
}
```

### TW3004: Non-Iterable Loop

**Cause:** Iterating non-array/object.

```tw
// WRONG
let count = 5

body {
    each count as num {
        p "{num}"
    }
}
```

**Error:**
```
[ERROR] TW3004: Cannot iterate 'number' at line 4, col 5
    Suggestion: Use an array.
```

**Fix:** Use iterable.

```tw
// CORRECT
let numbers = [1, 2, 3, 4, 5]

body {
    each numbers as num {
        p "{num}"
    }
}
```

### TW3005: Invalid Event Handler

**Cause:** Wrong event syntax.

```tw
// WRONG
body {
    button {
        on:click handleClick()
    }
}
```

**Error:**
```
[ERROR] TW3005: Event handler must be string at line 3, col 9
    Suggestion: on:click "handleClick()"
```

**Fix:** Quote the handler.

```tw
// CORRECT
body {
    button {
        on:click "handleClick()"
    }
}
```

## Build Errors (TW4000-TW4099)

### TW4000: Build Failure

**Cause:** General build error.

```bash
tw build
```

**Error:**
```
[ERROR] TW4000: Build failed for [home]/index.tw
    Phase: Code Generation
    Cause: TW3101: Failed to generate HTML
```

**Fix:** Check specific error and fix source.

### TW4001: Circular Dependency

**Cause:** Components importing each other.

```tw
// A.tw imports B, B.tw imports A
```

**Error:**
```
[ERROR] TW4001: Circular dependency: A.tw → B.tw → A.tw
    Suggestion: Extract shared logic into third component.
```

**Fix:** Remove circular references.

### TW4002: Asset Not Found

**Cause:** Missing asset file.

```tw
body {
    img { src "/assets/missing.jpg" }
}
```

**Warning:**
```
[WARNING] TW4002: Asset not found: [home]/assets/missing.jpg
```

**Fix:** Add asset or correct path.

## Runtime Errors

### JavaScript Errors

```
Uncaught ReferenceError: count is not defined
```

**Cause:** Variable used but not declared.

**Fix:** Declare with `let`.

```tw
// WRONG
body {
    button "+" { on:click "count++" }
}
```

```tw
// CORRECT
let count = 0

body {
    p "{count}"
    button "+" { on:click "count++" }
}
```

## Diagnostic Commands

### tw check

```bash
tw check [home]/index.tw
tw check --verbose
tw check --fix
```

### tw info

```bash
tw info
tw info --pages
tw info --deps
```

## Error Prevention Checklist

Before building:

- [ ] All `{` have matching `}`
- [ ] All strings in `"double quotes"`
- [ ] `page` block first (if used)
- [ ] `title` in `page` block
- [ ] All variables declared with `let`
- [ ] `if` statements have conditions
- [ ] `each` loops use `as` keyword
- [ ] Event handlers quoted
- [ ] All imports point to existing files
- [ ] All assets exist
- [ ] No circular dependencies
- [ ] `fetch` only in server/edge mode

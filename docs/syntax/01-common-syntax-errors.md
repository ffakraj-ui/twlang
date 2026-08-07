# Common Syntax Errors and Fixes

This guide covers every syntax mistake you can make in `.tw` files and exactly how to fix them.

## Error Category 1: Brace Mismatch

### Missing Closing Brace

```tw
// WRONG
page {
    title "Home"
    render static

body {
    h1 "Hello"
}
```

**Compiler Error:** `TW1000: Unexpected token at line 6, col 1. Expected '}' but found 'body'.`

**Fix:** Every opening brace `{` must have a matching closing brace `}`.

```tw
// CORRECT
page {
    title "Home"
    render static
}

body {
    h1 "Hello"
}
```

### Extra Closing Brace

```tw
// WRONG
body {
    h1 "Hello"
    }
}
```

**Compiler Error:** `TW1000: Unexpected token '}' at line 4, col 5.`

**Fix:** Remove the extra brace.

```tw
// CORRECT
body {
    h1 "Hello"
}
```

## Error Category 2: String Quoting

### Missing Quotes Around Values

```tw
// WRONG
page {
    title Home
    render static
}
```

**Compiler Error:** `TW1001: Expected STRING but found WORD 'Home' at line 2, col 11.`

**Fix:** All string values must be in double quotes.

```tw
// CORRECT
page {
    title "Home"
    render static
}
```

### Using Single Quotes

```tw
// WRONG
page {
    title 'Home'
}
```

**Compiler Error:** `TW1001: Unexpected character ''' at line 2, col 11.`

**Fix:** TW only supports double quotes `"` for strings.

```tw
// CORRECT
page {
    title "Home"
}
```

### Unclosed String

```tw
// WRONG
page {
    title "Home
}
```

**Compiler Error:** `TW1001: Unterminated string starting at line 2, col 11.`

**Fix:** Close the string with a matching `"`.

```tw
// CORRECT
page {
    title "Home"
}
```

## Error Category 3: Attribute Syntax

### Missing Space Between Attributes

```tw
// WRONG
img {
    src "/img.jpg"alt "Photo"
}
```

**Compiler Error:** `TW1002: Invalid attribute syntax at line 3, col 18.`

**Fix:** Each attribute must be separated by whitespace.

```tw
// CORRECT
img {
    src "/img.jpg"
    alt "Photo"
}
```

### Attribute Without Value

```tw
// WRONG
input {
    type
}
```

**Compiler Error:** `TW1002: Attribute 'type' missing value at line 3, col 5.`

**Fix:** Provide a value for every attribute.

```tw
// CORRECT
input {
    type "text"
}
```

### Boolean Attributes

```tw
// WRONG
input {
    required
}
```

**Compiler Error:** `TW1002: Attribute 'required' missing value at line 3, col 5.`

**Fix:** Boolean attributes in TW require explicit string values.

```tw
// CORRECT
input {
    required "true"
}
```

## Error Category 4: Page Block Placement

### Page Block After Body

```tw
// WRONG
body {
    h1 "Hello"
}

page {
    title "Home"
}
```

**Compiler Error:** `TW2001: 'page' block must appear before 'body' block at line 5, col 1.`

**Fix:** `page` block must always be the first block in the file.

```tw
// CORRECT
page {
    title "Home"
    render static
}

body {
    h1 "Hello"
}
```

### Multiple Page Blocks

```tw
// WRONG
page {
    title "Home"
}

page {
    title "About"
}
```

**Compiler Error:** `TW2001: Duplicate 'page' block at line 5, col 1. Only one page block allowed per file.`

**Fix:** Use only one `page` block per file.

```tw
// CORRECT
page {
    title "Home"
}
```

## Error Category 5: Component Import

### Import After Body

```tw
// WRONG
body {
    Hero {}
}

import "Hero"
```

**Compiler Error:** `TW2002: 'import' must appear before 'body' block at line 6, col 1.`

**Fix:** All `import` and `load` directives must appear before `body`.

```tw
// CORRECT
import "Hero"

page {
    title "Home"
}

body {
    Hero {}
}
```

### Importing Non-Existent Component

```tw
// WRONG
import "NonExistent"

body {
    NonExistent {}
}
```

**Compiler Error:** `TW2405: Component 'NonExistent' not found. Searched in: [home]/components/, [home]/pages/.`

**Fix:** Ensure the component file exists in the components directory.

```tw
// CORRECT
// File: [home]/components/Hero.tw exists
import "Hero"

body {
    Hero {}
}
```

## Error Category 6: Variable Declaration

### Using Undeclared Variables

```tw
// WRONG
body {
    h1 "{title}"
}
```

**Compiler Error:** `TW3001: Variable 'title' used but not declared at line 2, col 9.`

**Fix:** Declare variables with `let` before use.

```tw
// CORRECT
let title = "Welcome"

body {
    h1 "{title}"
}
```

### Declaring Variables After Body

```tw
// WRONG
body {
    h1 "{title}"
}

let title = "Welcome"
```

**Compiler Error:** `TW3001: Variable declarations must appear before 'body' block at line 6, col 1.`

**Fix:** Move `let` declarations before `body`.

```tw
// CORRECT
let title = "Welcome"

body {
    h1 "{title}"
}
```

### Reassigning Constants

```tw
// WRONG
let API_URL = "https://api.example.com"

script {
    API_URL = "https://other.com"
}
```

**Compiler Error:** `TW3002: Cannot reassign constant 'API_URL' at line 5, col 5.`

**Fix:** Use lowercase for mutable variables, UPPER_SNAKE_CASE for true constants.

```tw
// CORRECT
let api_url = "https://api.example.com"

script {
    api_url = "https://other.com"
}
```

## Error Category 7: Conditional Syntax

### Missing Condition in If

```tw
// WRONG
body {
    if {
        p "Shown"
    }
}
```

**Compiler Error:** `TW3003: 'if' statement missing condition at line 2, col 5.`

**Fix:** Provide a condition expression.

```tw
// CORRECT
let show_message = true

body {
    if show_message {
        p "Shown"
    }
}
```

### Using Else Without If

```tw
// WRONG
body {
    else {
        p "Fallback"
    }
}
```

**Compiler Error:** `TW3003: 'else' without matching 'if' at line 2, col 5.`

**Fix:** `else` must follow an `if` block.

```tw
// CORRECT
let logged_in = false

body {
    if logged_in {
        p "Welcome back"
    } else {
        p "Please log in"
    }
}
```

## Error Category 8: Loop Syntax

### Missing `as` in Each

```tw
// WRONG
body {
    each items item {
        p "{item}"
    }
}
```

**Compiler Error:** `TW3004: 'each' loop missing 'as' keyword at line 2, col 15.`

**Fix:** Use `each collection as item` syntax.

```tw
// CORRECT
let items = ["a", "b", "c"]

body {
    each items as item {
        p "{item}"
    }
}
```

### Iterating Over Non-Iterable

```tw
// WRONG
let count = 5

body {
    each count as num {
        p "{num}"
    }
}
```

**Compiler Error:** `TW3004: Cannot iterate over non-iterable value of type 'number' at line 4, col 5.`

**Fix:** Only iterate over arrays or objects.

```tw
// CORRECT
let numbers = [1, 2, 3, 4, 5]

body {
    each numbers as num {
        p "{num}"
    }
}
```

## Error Category 9: Event Handler Syntax

### Missing Quotes in on:click

```tw
// WRONG
button {
    on:click handleClick()
}
```

**Compiler Error:** `TW3005: Event handler value must be a string at line 2, col 15.`

**Fix:** Wrap handler in quotes.

```tw
// CORRECT
button {
    on:click "handleClick()"
}
```

### Invalid Event Name

```tw
// WRONG
button {
    on:tap "handleTap()"
}
```

**Compiler Error:** `TW3005: Unknown event 'tap'. Supported events: click, submit, input, change, keydown, keyup, focus, blur.`

**Fix:** Use valid DOM event names.

```tw
// CORRECT
button {
    on:click "handleClick()"
}
```

## Error Category 10: Head Block Errors

### Head Block After Body

```tw
// WRONG
body {
    h1 "Hello"
}

head {
    seo { description "My page" }
}
```

**Compiler Error:** `TW2003: 'head' block must appear before 'body' block at line 6, col 1.`

**Fix:** Place `head` before `body`.

```tw
// CORRECT
page {
    title "Home"
}

head {
    seo { description "My page" }
}

body {
    h1 "Hello"
}
```

### SEO Block Outside Head

```tw
// WRONG
body {
    seo { description "My page" }
}
```

**Compiler Error:** `TW2003: 'seo' block can only appear inside 'head' block at line 2, col 5.`

**Fix:** Move `seo` inside `head`.

```tw
// CORRECT
head {
    seo { description "My page" }
}
```

## Quick Reference: Error Code Table

| Code | Meaning | Common Cause |
|------|---------|--------------|
| TW1000 | Unexpected token | Brace mismatch, extra/missing braces |
| TW1001 | String error | Missing quotes, unclosed string |
| TW1002 | Attribute error | Missing value, bad syntax |
| TW2001 | Page block error | Wrong placement, duplicates |
| TW2002 | Import error | Wrong placement, missing file |
| TW2003 | Head block error | Wrong placement, invalid nesting |
| TW2404 | Layout not found | Missing layout file |
| TW2405 | Component not found | Missing component file |
| TW3001 | Variable error | Undeclared, wrong placement |
| TW3002 | Assignment error | Reassigning constant |
| TW3003 | Conditional error | Missing condition, orphan else |
| TW3004 | Loop error | Bad syntax, non-iterable |
| TW3005 | Event error | Missing quotes, invalid event |
| TW3101 | Code generation | Internal compiler error |

## Prevention Checklist

Before saving any `.tw` file, verify:

- [ ] Every `{` has a matching `}`
- [ ] All string values are in `"double quotes"`
- [ ] `page` block is first (if present)
- [ ] `import` and `load` come before `body`
- [ ] `head` comes before `body`
- [ ] All variables are declared with `let` before use
- [ ] `if` has a condition expression
- [ ] `each` uses `as` keyword
- [ ] Event handlers are quoted strings
- [ ] Component names match filenames exactly

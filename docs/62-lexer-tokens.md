# Lexer Token Reference

## Token Types

### WORD
Identifiers, keywords, tag names: `page`, `title`, `div`, `class`, `on:click`

### STRING
Quoted string values: `"Hello"`, `'Click me'`

### BRACE
Curly braces: `{`, `}`

### NL
Newline - acts as statement separator.

## Tokenization Rules

### Whitespace
Spaces and tabs are skipped. Newlines produce NL tokens.

### Comments
```tw
// Line comment - skipped by lexer
/* Block comment - skipped by lexer */
```

### Strings
Escape sequences inside strings:
- `\"` -> `"`
- `\'` -> `'`
- `\\` -> `\`
- `\n` -> newline

### Operators
Two-character: `==`, `!=`, `>=`, `<=`, `&&`, `||`
One-character: `[](),:=+-*/.%<>!`

### Inline Scripts
`script { ... }` blocks are tokenized as a single placeholder token.

## View Tokens

```bash
tw tokens [home]/index.tw
```

Output:
```json
[
    { "type": "WORD", "value": "page", "line": 1, "col": 1 },
    { "type": "BRACE", "value": "{", "line": 1, "col": 6 },
    { "type": "NL", "value": "\n", "line": 1, "col": 7 },
    { "type": "WORD", "value": "title", "line": 2, "col": 3 },
    { "type": "STRING", "value": "Home", "line": 2, "col": 9 }
]
```

## Token Structure

| Field | Type | Description |
|---|---|---|
| type | string | WORD, STRING, BRACE, NL |
| value | string | The actual text |
| line | int | Line number (1-based) |
| col | int | Column number (1-based) |

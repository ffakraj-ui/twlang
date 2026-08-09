# Compiler Internals

## Pipeline Overview

```
.tw file
    |
    v
[Lexer] -> Tokens
    |
    v
[Parser] -> AST
    |
    v
[Semantic Analysis] -> Validated AST
    |
    v
[IR] -> Intermediate Representation
    |
    v
[Code Generator] -> HTML / CSS / JS
    |
    v
[Optimizer] -> Minified, compressed output
    |
    v
dist/
```

## Lexer (tokenizer)

Converts source text into tokens:

```
Source: page { title "Home" }
Tokens:
  WORD   "page"     line=1 col=1
  BRACE  "{"        line=1 col=6
  WORD   "title"    line=1 col=8
  STRING "Home"     line=1 col=14
  BRACE  "}"        line=1 col=20
```

### Token Types

| Type | Description |
|---|---|
| WORD | Identifiers, keywords, tag names |
| STRING | Quoted string values |
| BRACE | { or } |
| NL | Newline (statement separator) |

### View Tokens

```bash
tw tokens [home]/index.tw
```

## Parser

Builds an AST from tokens. View it:

```bash
tw ast [home]/index.tw
```

### AST Node Types

| Node | Description |
|---|---|
| PageNode | Page configuration |
| ElementNode | HTML element |
| TextNode | Plain text |
| ComponentNode | Component reference |
| IfNode | Conditional block |
| ForNode | Loop |
| LetNode | Variable declaration |
| ScriptNode | Inline JavaScript |

## IR (Intermediate Representation)

```bash
tw ir [home]/index.tw
```

## Semantic Analysis

Validates the AST, checks for undefined variables, validates components:

```bash
tw check [home]/index.tw --diagnostics
```

## Error Codes

| Code | Category |
|---|---|
| TW0000 | Generic |
| TW1000 | Parser error |
| TW3101 | Code generation error |

# Compiler Internals

## Pipeline Stages

```
.tw source -> Lexer -> Parser -> AST -> IR -> Code Generator -> HTML/CSS/JS
```

## 1. Lexer (Tokenizer)

Converts source text into tokens.

Token types: `WORD`, `STRING`, `BRACE`, `NL` (newline)

### Lexer features

- Handles `//` and `/* */` comments
- Parses single and double quoted strings with escape sequences
- Detects `script { ... }` blocks as single placeholder tokens
- Tracks line and column for error reporting

## 2. Parser

Converts tokens into an Abstract Syntax Tree (AST).

### AST Node Types

| Node | Description |
|---|---|
| `PageNode` | Root node with page metadata |
| `ElementNode` | HTML element (div, h1, etc.) |
| `TextNode` | Plain text content |
| `ComponentNode` | Component reference |
| `IfNode` | Conditional block |
| `ForNode` | Loop block |
| `LetNode` | Variable declaration |
| `ScriptNode` | Inline JavaScript |

## 3. Intermediate Representation (IR)

Lowered form of the AST, closer to final output.

- `IRComponent` - lowered component
- `IRPage` - lowered page with metadata resolved
- `IRRoute` - route information

## 4. Code Generator

Converts IR to final output:

- **HTML** - generated from element nodes
- **CSS** - generated from `.tss` files via `render_css()`
- **JS** - generated from `.twm` modules and reactive directives

## Key Files

| File | Role |
|---|---|
| `compiler.py` | Lexer + parser + code generator |
| `lexer.py` | Token definitions and tokenizer |
| `ast_nodes.py` | AST node class definitions |
| `ir.py` | IR node definitions |
| `render_html.py` | HTML rendering |
| `render_css.py` | CSS rendering |
| `lowering.py` | AST to IR lowering |
| `semantic.py` | Semantic analysis and diagnostics |

## Token Inspection

```bash
tw tokens [home]/pages/index.tw
```

## AST Inspection

```bash
tw ast [home]/pages/index.tw
```

## IR Inspection

```bash
tw ir [home]/pages/index.tw
```

## Semantic Analysis

Checks for undefined variables, type mismatches, missing components/layouts, invalid attribute values.

```bash
tw check [home]/pages/index.tw --include-ast --include-ir
```

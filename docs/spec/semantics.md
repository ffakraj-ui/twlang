# Semantics

The semantic phase performs validation after parsing (syntax).

## Current checks

- Page-level expression symbol analysis
- Detect unknown names in interpolated text
- Validate interpolation in component props and element attributes
- Warning when the page title is empty

## Scope rules

- Top-level `let` names are available in the page scope
- `state` values are added to the runtime scope
- `for` and `each` inject the current loop variable into the child scope
- `if` is evaluated within the parent scope

## Pipeline

```text
source -> tokens -> AST -> semantic diagnostics -> IR -> interpreter / HTML
```

## Expected outcome

- The parser produces a valid AST
- The semantic phase produces meaningful diagnostics
- The IR lowerer consumes only validated AST

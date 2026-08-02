# TSS Grammar

TSS is a lightweight stylesheet syntax based on selectors and declaration pairs.

## Structure

```text
stylesheet := rule*
rule       := selector "{" declaration* "}"
declaration := property value
```

## Example

```text
body {
    margin 0
    font-family system-ui, sans-serif
}

.button {
    background #38bdf8
    color #082f49
}
```

## Rules

- Property names are normalized to kebab-case.
- Values are preserved as raw text until the CSS render phase stringifies them.
- Comments can be stripped before parsing.

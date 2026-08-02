# Contributing

## AST model overview

This repo currently has two AST representations:

- the legacy compiler AST in `tw_framework/compiler.py`, centered around classes such as `PageNode` and the legacy `ElementNode`
- the newer structured AST in `tw_framework/ast_nodes.py`, centered around `Program`, `PageMeta`, and the newer node dataclasses

Both exist because the compiler/runtime still depend on the legacy parser output in several places, while the newer pipeline powers `tw ast`, semantic analysis, lowering, IR generation, and JSON serialization.

## The bridge

The bridge between both worlds lives in `tw_framework/parser.py`.

- `parse_text()` and `parse_file()` still call the legacy tokenizer/parser from `compiler.py`
- `from_legacy_page()` converts the resulting `PageNode` into a modern `Program`
- `_convert_node()` recursively maps legacy node shapes into `ast_nodes.py` dataclasses

If you add a new node/property to the legacy parser, update `_convert_node()` and `from_legacy_page()` at the same time. If you only update one side, the modular pipeline and CLI JSON outputs will drift apart.

## Practical guidance

- when debugging parser/compiler disagreements, inspect both the legacy object and the `Program` output
- if a feature is only wired in `compiler.py`, do not assume it automatically appears in `tw ast` or the lowering pipeline
- if a feature is only added to `ast_nodes.py`, do not assume the runtime builder can consume it yet

## Safe workflow

- add or update tests in `tests/` with every parser/compiler change
- prefer small compatibility shims over broad rewrites unless you are intentionally removing the legacy path
- document new directives or filename conventions in `docs/spec/tw-grammar.md`

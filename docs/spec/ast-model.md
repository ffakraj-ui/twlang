# AST Model

The compiler stores the parsed representation in a `Program` object.

## Program

- `meta`: title, layout, render mode, revalidate, redirects
- `head`: meta tags, icon, seo map
- `lets`: top-level let bindings
- `state`: reactive initial state
- `body`: AST nodes list
- `loaded_sheets`: loaded stylesheet paths
- `loaded_json`: loaded JSON resources

## Node types

- `ElementNode`
- `ComponentNode`
- `LetNode`
- `IfNode`
- `ForNode`
- `ScriptNode`
- `TextNode`

## Design intent

- The legacy parser output is converted into the new AST.
- The new AST is serializable, so `tw ast` can output JSON directly.
- The lowering phase translates this AST into IR.
- The conversion bridge lives in `tw_framework/parser.py`, mainly through `from_legacy_page()` and `_convert_node()`.
- Legacy compiler nodes in `tw_framework/compiler.py` still exist for runtime/build compatibility, so contributors should treat the two representations as intentionally parallel until the legacy path is retired.

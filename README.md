# twlang

TW is a custom language + framework repo that parses, analyzes, lowers, and renders:

- `.tw` (pages + components)
- `.tss` (stylesheets)
- `.twm` (script modules; compiled into JS and registered, never auto-executed)

## New compiler layers

- `tw_framework/lexer.py`
- `tw_framework/parser.py`
- `tw_framework/ast_nodes.py`
- `tw_framework/semantic.py`
- `tw_framework/ir.py`
- `tw_framework/lowering.py`
- `tw_framework/interpreter.py`
- `tw_framework/render_html.py`
- `tw_framework/render_css.py`
- `tw_framework/runtime_values.py`

## CLI

- `tw ast file.tw`
- `tw ir file.tw`
- `tw run file.tw`
- `tw run file.tw --diagnostics`
- `tw check file.tw --include-ast --include-ir`
- `tw tokens file.tw`
- existing `tw dev`, `tw build`, `tw preview`, `tw deploy`

## Testing

- `python3 -m unittest discover -s tests -q`
- `python3 run_tests.py`
- If you prefer `pytest`, install it first and then run `pytest -q`

## Modular pipeline

- If `modular_pipeline: true` is enabled in `tw.config`, the build/runtime path uses modular compiler artifacts.
- After a build, route metadata is available at `dist/_tw/route-manifest.json`.
- Cache + dependency metadata is persisted in `.tw/manifest/build-manifest.json` and `.tw/cache/dependency-graph.json`.

## Runtime knobs

- `tw.config` now accepts nested blocks for framework capabilities, for example:

```yaml
security:
  headers:
    X-Frame-Options: DENY
cookies:
  secure: auto
ssr:
  cache_max: 512
```

- `middleware.tw` supports opt-in rate limiting primitives:

```tw
use {
  match "/api/**"
  rate_limit {
    requests 100
    window 60
  }
}
```

- `page { ... }` supports cache controls such as `cache_by cookie:session_id` and `cache_size 100`.
- Server APIs are organized as `[home]/api/**/route.twm`.
- Path aliases for `load` now follow this rule:
  - `@lib/file.tw` = project root se
  - `@./lib/file.tw` = `[home]` se
  - `@../file.tw` = current file folder ke relative

## Specs

Language docs are available in `docs/spec/`.

## API trust model

- `.twm` route handlers run as trusted server code.
- Treat `[home]/api/**/route.twm` the same way you would treat any server-side application code in your repository.
- See `SECURITY.md` for the current security model and operator responsibilities.

## Debug flags

- `TW_WARN_LITERAL_PARSE=1`: when forgiving literal parsing falls back to treating malformed JSON/Python-like literals as plain strings, emit a warning to stderr instead of failing silently
- `TW_STRICT_EVAL=1`: when expression evaluation hits a runtime error, re-raise it instead of downgrading to a warning + fallback lookup

These flags are mainly useful while debugging parser/runtime edge cases or tightening CI checks around expression handling.

# Changelog

All notable changes to TW Framework are documented here.

## [0.3.4]

### Fixed
- Dynamic-page incremental cache entries are stored as a list (one per generated slug) rather than a dict. The cache-check code assumed a dict shape for every page and crashed with `'list' object has no attribute 'get'` when building dynamic routes. It now guards for the dict shape and safely falls through to a full rebuild otherwise.

## [0.3.3]

### Fixed
- The `response { header ... }` / `response { cookie ... }` block inside a middleware rule used the same greedy line-parsing bug as the top-level `header`/`cookie` keys (fixed in 0.2.5), but this occurrence was missed. Two values on one line (`header "X" "Y"`) inside a `response { }` block now parse correctly instead of crashing.

## [0.3.2]

### Fixed
- **Decimal number tokenization** — numeric literals like `3.14` were split into three tokens (`3`, `.`, `14`) because `.` was always treated as a standalone operator. Any bare decimal value in a `.tw` file was corrupted on output (e.g. `data-ratio 3.14` rendered as `data-ratio="3 . 14"`).
- **`data-tw-on` / `data-tw-bind` JSON corruption** — these framework-generated attributes (holding JSON for reactive event handlers) were being passed back through the general string-interpolation step, which mis-parsed the leading `{` as a template expression and re-serialized the value as a Python dict repr (single-quoted keys) instead of valid JSON. This broke `on:click` handlers on any element that also had other attributes. Framework-generated `data-tw-*` attributes are no longer re-interpolated.
- **Boolean attribute rendering** — a bare `true`/`false` value rendered as Python's `str(True)` → `"True"` (capital T), which is not valid for HTML/JS boolean conventions. Booleans now render as lowercase `"true"` / `"false"`.

## [0.3.1]

### Fixed
- **Major:** single-line elements with multiple properties (e.g. `a { href "/" target "_blank" text "Home" }`) had every property after the first swallowed into the first property's value, because the property-value parser only treated a quoted string as "complete" when directly followed by a newline or `}`. On the same line, the next property name looked like a continuation of the previous value and was consumed by it. A quoted string value is now always treated as complete on its own — this was likely the single highest-impact bug found, since single-line elements are an extremely common way to write markup.

## [0.3.0]

### Fixed
- `.tss` stylesheet values wrapped in quotes (needed for multi-word CSS values like `animation "pulse 2s infinite"` or `transform "translateY(-6px)"`) kept their literal quote characters in the compiled CSS output, producing invalid CSS (`animation: "pulse 2s infinite";`). Quoted `.tss` values are now unwrapped before being written out.

## [0.2.9]

### Fixed
- The dev-mode search index builder's HTML-to-text extractor (`strip_html_to_text`) had double-escaped regex patterns (`\\s` instead of `\s`) for stripping `<script>`/`<style>` blocks. Because the patterns never actually matched, raw inline JavaScript and the page's `__TW_DATA__` JSON blob leaked into every search result's excerpt text.

## [0.2.8]

### Fixed
- `pyproject.toml` only listed Python packages under `[tool.setuptools]`, so the `twm_api_runner.js` asset file (required to execute `.twm` API routes) was never included in the built wheel. Every API route failed with `Missing twm_api_runner.js (framework installation is incomplete)` on a fresh `pip install`. Added `[tool.setuptools.package-data]` to include `*.js` files.

## [0.2.7]

### Fixed
- Reactive directives `on:click` / `bind:value` were never usable: the tokenizer split `on:click` into three tokens (`on`, `:`, `click`) since `:` was always a standalone operator, and even after fixing the tokenizer, the property classifier didn't recognize `on:` / `bind:` / `show:` / `tw-*` prefixed names as valid attributes (reactivity.py explicitly expects these). Both the tokenizer and the property classifier were fixed.
- The default `tw create` starter project's `search` page relies on a raw `script { ... }` block, which is blocked by default for safety. Enabled `allow_raw_script: true` in the starter's `tw.config` so the example works out of the box.

## [0.2.6]

### Fixed
- Kebab-case attribute names (`aria-label`, `data-foo`) were split into multiple tokens by the tokenizer, since `-` was always treated as a standalone operator. This broke any accessibility or `data-*` attribute — including in the default `tw create` template itself (`ThemeToggle.tw`'s `aria-label`).

## [0.2.5]

### Fixed
- **Middleware crash:** the default `middleware.tw` template's `auth "cookie" "redirect"` and `header "name" "value"` directives put two values on one line. The value parser used a line-greedy collector for the first value, which consumed both values, leaving nothing for the second and crashing every request with `RuntimeError: Expected value token`. This affected every project created with `tw create`, since the crashing directives were in the default template.
- **String quote corruption:** parsed string literal values (e.g. `match "/dashboard/**"`) retained their literal surrounding quote characters instead of being unquoted, so middleware path-matching rules like `match` never matched real request paths.
- Removed a duplicate `doctor` subcommand registration in the CLI that crashed argument parsing (`conflicting subparser: doctor`).
- Fixed a diagnostic-formatting pipeline mismatch across three files (`compiler.py`, `diagnostics.py`, `error_formatter.py`) where the rich `Diagnostic` fields the error formatter expected had been stripped from the simplified `Diagnostic` dataclass. Any compiler error — valid or not — crashed instead of showing a readable message.
- `pyproject.toml` only declared the top-level `tw_framework` package, so the `tw_framework.adapters` subpackage (Vercel/Netlify/Cloudflare deploy adapters) was missing from the installed package, breaking every deploy-related import.

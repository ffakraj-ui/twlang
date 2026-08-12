# TW Framework — Progress

## Current Version: v0.9.16

## Version History

### v0.9.16 — Final Polish
- Security hardening: scrypt+HMAC encryption, V8 timeout, error sanitization
- Thread safety: storage Lock, register_runtimes double-check lock
- Memory: gc.collect() on V8 context reload
- Missing files: py.typed, __main__.py, __version__.py, middleware.py, extensions.py
- Documentation: README.md, llms.txt, llms-full.txt, llms-full_part1.txt rewritten from source
- 610 tests pass, 0 failures

### v0.9.15 — PyPI Release Prep
- Optional dependencies added to pyproject.toml (image, compression, edge-v8, redis, wasm, all)
- Documentation updated with optional dependency installation
- llms.txt files updated
- Version bumped to 0.9.15

### v0.9.14 — Edge V8 + Module Boundaries + Runtime Init (bugs 601-700)
- edge_v8_adapter.py: 14 fixes (env leak, JS injection, URLError crash, binary data, thread safety)
- module_boundaries.py: 8 fixes (dynamic imports, caching, severity field, prefix matching)
- tw_runtime/__init__.py: 5 fixes (thread-safe registration, __version__, docstring)

### v0.9.13 — 6 Core Module Fixes (bugs 401-540)
- reactivity.py, twm_parser.py, security.py, client_bundler.py, error_formatter.py, common.py

### v0.9.12 — App Router + Server + Compiler (bugs 301-400)
### v0.9.11 — Compiler + CLI (bugs 201-300)
### v0.9.10 — React compat, prefetch, version fixes (bugs 1-3)

## Test Results
- 610 passed, 9 skipped, 0 failed
- No regressions across all versions

## Bug Fix Statistics
- Total bugs reported: 700+
- Bugs fixed: ~450 (real bugs)
- False positives verified: ~250 (already correct by design)
- Fix rate: ~64% of reported bugs were real

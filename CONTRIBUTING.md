# TW Framework — Contributing

## Development Setup

```bash
# Clone the repo
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang/twlang-main-v2/twlang-main

# Install in development mode
pip install -e .

# Install dev dependencies
pip install tw-framework[dev]

# Run tests
pytest tests/ --tb=short -q

# Run specific test
pytest tests/test_module_boundaries.py -v
```

## Project Structure

```
twlang-main/
  tw_framework/           # Main package
    __init__.py           # Version, public API
    __main__.py           # python -m tw_framework entry
    __version__.py        # Standalone version info
    py.typed              # PEP 561 type marker
    cli.py                # CLI commands (1680 lines)
    compiler.py           # Compilation pipeline (6863 lines)
    framework.py          # Project, middleware, build (4913 lines)
    server.py             # Production server (744 lines)
    reactivity.py         # VDOM, state, actions (936 lines)
    app_router.py         # Routing (534 lines)
    security.py           # Security (388 lines)
    module_boundaries.py  # Import classification (337 lines)
    twm_parser.py         # TWM parser (418 lines)
    client_bundler.py     # JS bundling (975 lines)
    middleware.py          # Auth middleware utilities
    extensions.py          # ExtensionManager re-export
    tw_runtime/            # Multi-runtime system
      __init__.py
      base.py
      registry.py
      abstractions.py
      validator.py
      adapters/
        node_adapter.py
        python_adapter.py
        edge_v8_adapter.py
        edge_adapter.py
        wasm_adapter.py
    tw_auth/               # Auth system
      session.py
      middleware.py
      client.py
      runtime.py
  tests/                  # Test suite (610 tests)
  docs/                   # Documentation
  pyproject.toml          # Package config
  package.json            # Node.js config
```

## Testing

- Always run tests before submitting: `pytest tests/ --tb=short -q`
- Current: 610 passed, 9 skipped, 0 failed
- Tests cover compiler, router, server, security, module boundaries, runtime

## Code Style

- Python 3.9+ (uses `from __future__ import annotations`)
- Type hints encouraged (py.typed marker present)
- Docstrings for public functions
- No external dependencies in core (pure stdlib)

## Versioning

- Semantic versioning: 0.9.x
- Each version fixes a batch of bugs
- CHANGELOG.md tracks all changes

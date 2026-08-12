# TW Framework — Contributing

## Development Setup

```bash
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang
pip install -e .
pip install tw-framework[dev]
pytest
```

## Running Tests

```bash
pytest                           # All tests
pytest tests/test_stability.py -v      # Architecture module tests
pytest tests/test_stability_core.py -v  # Core module tests
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make changes, add tests
4. Run `pytest` to verify
5. Submit a pull request

## Debug Mode

Use `--debug` to get full error details during development:

```bash
tw --debug build
tw --debug serve
tw --debug dev
```

## Authors

- TW MRMK
- TW MLKRAJ
- TW ASLAM
- TW BADAL
- TW ROHIT
- TW RISHU

## License

MIT

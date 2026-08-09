# Testing

## Testing .twm Modules

Use pytest to test API logic:

```python
import pytest

def test_hello_api():
    from tw_framework.framework import execute_twm_api_handler
    result = execute_twm_api_handler(
        handler_path="[home]/api/hello.twm",
        method="GET",
        url_path="/api/hello",
        headers={},
        body=None
    )
    assert result["status"] == 200
    assert "message" in result["json"]
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Testing Build Output

```python
import os

def test_build_produces_html():
    assert os.path.exists("dist/index.html")

def test_no_js_for_static_pages():
    with open("dist/index.html") as f:
        html = f.read()
    assert "<script" not in html or "data-tw" in html
```

## Using tw check

```bash
tw check [home]/index.tw
tw check [home]/index.tw --diagnostics
```

## CI Pipeline

```yaml
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install tw-framework pytest
      - run: tw build --prod
      - run: pytest tests/ -v
```

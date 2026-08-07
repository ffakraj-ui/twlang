# Testing TW Applications

## Testing .twm API Modules

Use pytest to test API route handlers:

```python
# tests/test_api.py

import pytest
from tw_framework.framework import execute_twm_api_handler

def test_hello_endpoint():
    result = execute_twm_api_handler(
        handler_path="[home]/api/hello.twm",
        method="GET",
        url_path="/api/hello",
        headers={},
        body=None
    )
    assert result["status"] == 200
    assert result["json"]["message"] == "Hello from TW!"

def test_create_user():
    result = execute_twm_api_handler(
        handler_path="[home]/api/users/route.twm",
        method="POST",
        url_path="/api/users",
        headers={"content-type": "application/json"},
        body={"name": "John", "email": "john@example.com"}
    )
    assert result["status"] == 201
```

## Testing Middleware

```python
# tests/test_middleware.py

from tw_framework.framework import parse_middleware_rules

def test_middleware_parses():
    rules = parse_middleware_rules("[home]")
    assert len(rules) > 0
```

## Testing Build Output

```python
# tests/test_build.py

import os
from tw_framework.framework import build_hidden_site

def test_build_produces_output():
    build_hidden_site(".", "dist_test", force=True, minify=False)
    assert os.path.exists("dist_test/index.html")
```

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

## Test Structure

```
my-site/
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_build.py
│   ├── test_middleware.py
│   └── test_compiler.py
├── [home]/
└── pytest.ini
```

## Compiler Tests

```python
from tw_framework import compiler

def test_tokenize_simple():
    tokens = compiler.tokenize('div { class "hero" }')
    assert tokens[0].type == "WORD"
    assert tokens[0].value == "div"

def test_error_on_invalid_syntax():
    with pytest.raises(compiler.CompilerError):
        compiler.tokenize('h1 "unterminated')
```

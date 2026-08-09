# Python API Reference

TW Framework exposes a Python API for programmatic use, testing, and custom tooling.

## Installation

```bash
pip install tw-framework
```

## Core Modules

### `tw_framework.compiler`

The main compilation pipeline.

#### `compile_text_pipeline(text, **kwargs)`

Compiles a `.tw` source string into HTML.

```python
from tw_framework.compiler import compile_text_pipeline

result = compile_text_pipeline('''
page { title "Test" render static }
body { h1 "Hello" }
''')

print(result.html)
print(result.diagnostics)
print(result.ast)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | required | Raw `.tw` source |
| `base_dir` | `str` | `"."` | Base directory for resolving imports |
| `file_path` | `str` | `""` | Virtual file path for error reporting |
| `context` | `dict` | `None` | Runtime context variables |
| `css_href` | `str` | `None` | CSS file URL to inject |
| `route_path` | `str` | `"/"` | Route path for the page |
| `capture_errors` | `bool` | `False` | Return diagnostics instead of raising |
| `dependency_paths` | `list` | `None` | Extra dependency paths for cache |

**Returns:** `CompilerArtifacts` dataclass with:
- `source_path`: Original file path
- `tokens`: Token list
- `ast`: AST dictionary
- `ir`: IR dictionary
- `html`: Final HTML string
- `diagnostics`: List of diagnostic dicts
- `dependencies`: List of file dependencies
- `metadata`: Build metadata dict

#### `compile_file_pipeline(path, **kwargs)`

Same as `compile_text_pipeline` but reads from a file.

```python
from tw_framework.compiler import compile_file_pipeline

result = compile_file_pipeline("[home]/index.tw")
```

### `tw_framework.lexer`

#### `tokenize_tw(code)`

Tokenizes `.tw` source into a list of `LexerToken`.

```python
from tw_framework.lexer import tokenize_tw

tokens = tokenize_tw('page { title "Home" }')
for token in tokens:
    print(token.type, token.value, token.line, token.col)
```

**Token Types:**

| Type | Example |
|------|---------|
| `WORD` | `page`, `div`, `class` |
| `STRING` | `"Hello"` |
| `BRACE` | `{`, `}` |
| `NL` | newline |
| `COMMENT` | `// comment` |

### `tw_framework.parser`

#### `parse_text(text, base_dir=".", file_path="")`

Parses tokens into a modular AST.

```python
from tw_framework.parser import parse_text

program = parse_text('''
page { title "Home" layout "main" render static }
body { h1 "Hello World" }
''')

print(program.meta.title)
print(program.meta.layout)
print(program.meta.render_mode)
```

### `tw_framework.cli`

Programmatic CLI access:

```python
from tw_framework.cli import main as cli_main
import sys

sys.argv = ["tw", "build", "--prod"]
cli_main()
```

### `tw_framework.server`

#### `create_dev_server(port=3000)`

Creates a development server instance.

```python
from tw_framework.server import create_dev_server

server = create_dev_server(port=3000)
server.serve_forever()
```

### `tw_framework.lsp_server`

#### `start_lsp_server()`

Starts the Language Server Protocol server.

```python
from tw_framework.lsp_server import start_lsp_server

start_lsp_server()
```

## Data Classes

### `CompilerArtifacts`

```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class CompilerArtifacts:
    source_path: str
    tokens: List[Dict]
    ast: Optional[Dict]
    ir: Optional[Dict]
    html: Optional[str]
    diagnostics: List[Dict]
    dependencies: List[str]
    route_path: str
    pipeline: str
    metadata: Dict[str, Any]
    program: Optional[Any] = None
    runtime_context: Optional[Dict] = None
```

## Error Handling

### `CompilerError`

```python
from tw_framework.compiler import CompilerError

try:
    result = compile_file_pipeline("bad-file.tw")
except CompilerError as e:
    print(e.message)
    print(e.code)
    print(e.suggestion)
    print(e.file_path)
    print(e.line)
    print(e.col)
```

## Utility Functions

### `read_text_file(path)`

Reads a file with UTF-8 encoding, normalizing line endings.

```python
from tw_framework.compiler import read_text_file

content = read_text_file("[home]/index.tw")
```

### `load_config()`

Parses `tw.config` into a dictionary.

```python
from tw_framework.compiler import load_config

config = load_config()
print(config.get("name"))
print(config.get("theme"))
```

## Example: Custom Build Script

```python
#!/usr/bin/env python3
import os
from tw_framework.compiler import compile_file_pipeline

pages_dir = "[home]/pages"
build_dir = "dist"

for filename in os.listdir(pages_dir):
    if filename.endswith(".tw"):
        path = os.path.join(pages_dir, filename)
        result = compile_file_pipeline(path, capture_errors=True)

        if result.diagnostics:
            for d in result.diagnostics:
                print(f"[{d['severity']}] {d['message']}")
        else:
            out_path = os.path.join(build_dir, filename.replace(".tw", ".html"))
            with open(out_path, "w") as f:
                f.write(result.html)
            print(f"Built: {out_path}")
```

---

For internal APIs and advanced usage, see the source code in `tw_framework/`.

# Contributing to the Compiler

Want to hack on TW Framework's core? This guide covers the compiler architecture and how to contribute.

## Architecture Overview

```
Source (.tw) → Lexer → Tokens → Parser → AST → IR → CodeGen → HTML
```

### 1. Lexer (`tw_framework/lexer.py`)

Converts raw `.tw` text into tokens.

```python
# Example: tokenize a simple page
tokens = tokenize_tw('page { title "Home" }')
# [
#   LexerToken(type='WORD', value='page', line=1, col=1),
#   LexerToken(type='BRACE', value='{', line=1, col=6),
#   LexerToken(type='WORD', value='title', line=1, col=8),
#   LexerToken(type='STRING', value='Home', line=1, col=14),
#   LexerToken(type='BRACE', value='}', line=1, col=20)
# ]
```

Key classes:
- `LexerToken`: Individual token with type, value, position
- `LexerState`: Tracks indentation, brace depth, line/column

### 2. Parser (`tw_framework/parser.py`)

Builds an Abstract Syntax Tree (AST) from tokens.

```python
program = parse_text('page { title "Home" }')
# ProgramNode:
#   meta: PageMetaNode(title="Home")
#   body: BodyNode(children=[...])
```

Key classes:
- `ProgramNode`: Root of the AST
- `PageMetaNode`: Page metadata (title, layout, render mode)
- `BodyNode`: Page body content
- `ComponentNode`: Component usage
- `ElementNode`: HTML element

### 3. IR (`tw_framework/compiler.py`)

Intermediate Representation — a simplified form for code generation.

```python
ir = {
    "type": "page",
    "meta": {"title": "Home", "layout": "main", "render": "static"},
    "head": [...],
    "body": [...]
}
```

### 4. Code Generator

Converts IR to final HTML.

## Setting Up Development Environment

```bash
# Clone the repo
git clone https://github.com/ffakraj-ui/twlang.git
cd twlang

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in editable mode
pip install tw-framework

# Install dev dependencies
pip install pytest pytest-cov black flake8 mypy

# Run tests
pytest

# Run specific test
pytest tests/test_lexer.py -v
```

## Adding a New Feature

### Example: Adding a New Directive

1. **Define the directive in the lexer**:

```python
# tw_framework/lexer.py
DIRECTIVES = {
    'load', 'import', 'env',
    'analytics',  # NEW
}
```

2. **Parse it in the parser**:

```python
# tw_framework/parser.py
def parse_directive(self):
    directive = self.consume('WORD')
    if directive.value == 'analytics':
        tracking_id = self.consume('STRING')
        return AnalyticsDirectiveNode(tracking_id=tracking_id.value)
```

3. **Handle it in the compiler**:

```python
# tw_framework/compiler.py
def _compile_analytics_directive(self, node):
    script = f'<script async src="https://analytics.com/track.js?id={node.tracking_id}"></script>'
    self._head_injections.append(script)
```

4. **Add tests**:

```python
# tests/test_compiler.py
def test_analytics_directive():
    result = compile_text_pipeline('analytics "UA-123"\nbody { h1 "Test" }')
    assert 'UA-123' in result.html
```

## Testing

### Unit Tests

```python
# tests/test_lexer.py
def test_tokenize_string():
    tokens = tokenize_tw('"hello world"')
    assert len(tokens) == 1
    assert tokens[0].type == 'STRING'
    assert tokens[0].value == 'hello world'
```

### Integration Tests

```python
# tests/test_build.py
def test_full_build():
    result = compile_file_pipeline("fixtures/simple-page.tw")
    assert result.html is not None
    assert '<h1>Hello</h1>' in result.html
    assert len(result.diagnostics) == 0
```

### Regression Tests

When fixing a bug, add a test that would have caught it:

```python
def test_issue_42_nested_components():
    # Reproduces GitHub issue #42
    source = '''
    Card {
        Header {
            Title { text "Hello" }
        }
    }
    '''
    result = compile_text_pipeline(source)
    assert result.html is not None
```

## Code Style

- Follow PEP 8
- Use type hints for public functions
- Document with docstrings
- Keep functions under 50 lines

## Submitting a PR

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes with tests
4. Run the full test suite: `pytest`
5. Update documentation
6. Submit PR with clear description

## Debugging the Compiler

Enable verbose logging:

```bash
TW_DEBUG=1 tw build [home]/index.tw
```

This prints:
- Token stream
- AST dump
- IR dump
- Compilation time per phase

## Common Issues

| Issue | Solution |
|-------|----------|
| Token not recognized | Add to `LexerState.keywords` or `DIRECTIVES` |
| Parse error on valid syntax | Check `Parser.expect()` calls |
| HTML missing content | Verify IR generation for that node type |
| Infinite loop | Check `while` conditions in lexer/parser |

## Performance Profiling

```python
import cProfile
from tw_framework.compiler import compile_file_pipeline

cProfile.run('compile_file_pipeline("[home]/index.tw")', 'stats.prof')
```

Analyze with `snakeviz`:

```bash
pip install snakeviz
snakeviz stats.prof
```

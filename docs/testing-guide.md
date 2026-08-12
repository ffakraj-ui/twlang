# Testing Guide

Ensure your TW Framework projects are reliable with comprehensive testing.

## Testing Pyramid

```
    /\
   /  \     E2E Tests (Few)
  /----\
 /      \   Integration Tests (Some)
/--------\
          \ Unit Tests (Many)
```

## Unit Tests

### Testing Lexer

```python
# tests/test_lexer.py
import pytest
from tw_framework.lexer import tokenize_tw, LexerToken

def test_tokenize_simple_page():
    source = 'page { title "Home" }'
    tokens = tokenize_tw(source)

    assert len(tokens) == 5
    assert tokens[0] == LexerToken(type='WORD', value='page', line=1, col=1)
    assert tokens[1] == LexerToken(type='BRACE', value='{', line=1, col=6)
    assert tokens[2] == LexerToken(type='WORD', value='title', line=1, col=8)
    assert tokens[3] == LexerToken(type='STRING', value='Home', line=1, col=14)
    assert tokens[4] == LexerToken(type='BRACE', value='}', line=1, col=20)

def test_tokenize_multiline():
    source = '''page {
    title "Home"
}'''
    tokens = tokenize_tw(source)

    # Check line numbers
    assert tokens[0].line == 1
    assert tokens[-1].line == 3

def test_tokenize_comments():
    source = '// This is a comment\npage { title "Home" }'
    tokens = tokenize_tw(source)

    comment_tokens = [t for t in tokens if t.type == 'COMMENT']
    assert len(comment_tokens) == 1
    assert 'comment' in comment_tokens[0].value
```

### Testing Parser

```python
# tests/test_parser.py
from tw_framework.parser import parse_text

def test_parse_page_meta():
    source = '''
    page {
        title "Home"
        layout "main"
        render static
    }
    '''
    program = parse_text(source)

    assert program.meta.title == "Home"
    assert program.meta.layout == "main"
    assert program.meta.render_mode == "static"

def test_parse_body_elements():
    source = '''
    body {
        h1 "Hello"
        p "World"
    }
    '''
    program = parse_text(source)

    assert len(program.body.children) == 2
    assert program.body.children[0].tag == "h1"
    assert program.body.children[1].tag == "p"

def test_parse_component_with_props():
    source = '''
    Hero {
        title "Welcome"
        subtitle "To my site"
    }
    '''
    program = parse_text(source)

    hero = program.body.children[0]
    assert hero.name == "Hero"
    assert hero.props["title"] == "Welcome"
    assert hero.props["subtitle"] == "To my site"
```

### Testing Compiler

```python
# tests/test_compiler.py
from tw_framework.compiler import compile_text_pipeline

def test_compile_simple_page():
    source = '''
    page { title "Test" render static }
    body { h1 "Hello" }
    '''
    result = compile_text_pipeline(source)

    assert result.html is not None
    assert '<h1>Hello</h1>' in result.html
    assert '<title>Test</title>' in result.html
    assert len(result.diagnostics) == 0

def test_compile_with_css():
    source = '''
    page { title "Test" render static }
    load "@./style/test.tss"
    body { div { class "test" "Content" } }
    '''
    result = compile_text_pipeline(source, base_dir="fixtures")

    assert 'class="test"' in result.html

def test_compile_errors():
    source = 'page { title }'  # Missing string value
    result = compile_text_pipeline(source, capture_errors=True)

    assert len(result.diagnostics) > 0
    assert result.diagnostics[0]['severity'] == 'error'
```

## Integration Tests

### Testing API Routes

```python
# tests/test_api.py
import pytest
from tw_framework.server import create_test_client

@pytest.fixture
def client():
    return create_test_client()

def test_get_products(client):
    response = client.get('/api/products')

    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_create_product(client):
    response = client.post('/api/products', json={
        'name': 'Test Product',
        'price': 99.99
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['id'] is not None

def test_invalid_product(client):
    response = client.post('/api/products', json={
        'name': ''  # Invalid: empty name
    })

    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data
```

### Testing Full Pages

```python
# tests/test_pages.py
from tw_framework.compiler import compile_file_pipeline

def test_home_page():
    result = compile_file_pipeline('[home]/index.tw')

    assert result.html is not None
    assert '<!DOCTYPE html>' in result.html
    assert '<html' in result.html

def test_404_page():
    result = compile_file_pipeline('[home]/404.tw')

    assert '404' in result.html or 'Not Found' in result.html

def test_dynamic_route():
    result = compile_file_pipeline(
        '[home]/blog/[slug].tw',
        context={'post': {'title': 'Test', 'body': 'Content'}}
    )

    assert '<h1>Test</h1>' in result.html
    assert 'Content' in result.html
```

## E2E Tests

### Using Playwright

```bash
pip install pytest-playwright
playwright install
```

```python
# tests/e2e/test_blog.py
import pytest
from playwright.sync_api import Page

def test_blog_homepage(page: Page):
    page.goto('http://localhost:3000/blog')

    # Check title
    assert page.title() == 'Blog | My Site'

    # Check posts exist
    posts = page.locator('.post-card')
    assert posts.count() > 0

    # Click first post
    posts.first.click()

    # Verify navigation
    assert '/blog/' in page.url
    assert page.locator('article').is_visible()

def test_navigation_menu(page: Page):
    page.goto('http://localhost:3000/')

    # Click nav links
    page.click('text=About')
    assert page.url.endswith('/about')

    page.click('text=Contact')
    assert page.url.endswith('/contact')

def test_contact_form(page: Page):
    page.goto('http://localhost:3000/contact')

    # Fill form
    page.fill('input[name="name"]', 'Test User')
    page.fill('input[name="email"]', 'test@example.com')
    page.fill('textarea[name="message"]', 'Hello!')

    # Submit
    page.click('button[type="submit"]')

    # Check success message
    assert page.locator('.success-message').is_visible()

def test_dark_mode_toggle(page: Page):
    page.goto('http://localhost:3000/')

    # Toggle dark mode
    page.click('#theme-toggle')

    # Check data-theme attribute
    theme = page.evaluate('() => document.documentElement.getAttribute("data-theme")')
    assert theme == 'dark'
```

### Using Selenium

```python
# tests/e2e/test_selenium.py
from selenium import webdriver
from selenium.webdriver.common.by import By
import pytest

@pytest.fixture
def driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()

def test_page_loads(driver):
    driver.get('http://localhost:3000')
    assert 'My Site' in driver.title

    header = driver.find_element(By.TAG_NAME, 'h1')
    assert header.is_displayed()
```

## Performance Tests

### Lighthouse CI

```yaml
# .github/workflows/lighthouse.yml
name: Lighthouse CI
on: [push]
jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build site
        run: tw build --prod
      - name: Run Lighthouse
        uses: treosh/lighthouse-ci-action@v10
        with:
          configPath: './lighthouserc.json'
```

```json
// lighthouserc.json
{
  "ci": {
    "assert": {
      "assertions": {
        "categories:performance": ["warn", {"minScore": 0.9}],
        "categories:accessibility": ["error", {"minScore": 0.95}],
        "categories:best-practices": ["warn", {"minScore": 0.9}],
        "categories:seo": ["warn", {"minScore": 0.9}]
      }
    }
  }
}
```

### Load Testing

```python
# tests/perf/test_load.py
import asyncio
import aiohttp
import time

async def fetch(session, url):
    async with session.get(url) as response:
        return response.status, await response.text()

async def load_test(url, concurrent=50, total=1000):
    start = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, url) for _ in range(total)]
        results = await asyncio.gather(*tasks)

    duration = time.time() - start
    success = sum(1 for status, _ in results if status == 200)

    print(f"Requests: {total}")
    print(f"Success: {success}")
    print(f"Duration: {duration:.2f}s")
    print(f"RPS: {total/duration:.2f}")
    print(f"Avg latency: {duration/total*1000:.2f}ms")

asyncio.run(load_test('http://localhost:3000'))
```

## Test Fixtures

```python
# tests/conftest.py
import pytest
import tempfile
import os

@pytest.fixture
def temp_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal TW project structure
        os.makedirs(f"{tmpdir}/pages")
        os.makedirs(f"{tmpdir}/components")
        os.makedirs(f"{tmpdir}/style")

        # Create tw.config
        with open(f"{tmpdir}/tw.config", 'w') as f:
            f.write('name: "Test Project"\n')

        yield tmpdir

@pytest.fixture
def sample_page():
    return '''
    page {
        title "Test Page"
        layout "main"
        render static
    }

    body {
        h1 "Hello World"
        p "This is a test page."
    }
    '''
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tw_framework --cov-report=html

# Run specific file
pytest tests/test_lexer.py

# Run specific test
pytest tests/test_compiler.py::test_compile_simple_page

# Run in parallel
pytest -n auto

# Run E2E tests only
pytest tests/e2e/

# Run with verbose output
pytest -v
```

## CI Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install tw-framework
          pip install pytest pytest-cov pytest-asyncio playwright
          playwright install

      - name: Run unit tests
        run: pytest tests/unit/ --cov=tw_framework

      - name: Run E2E tests
        run: |
          tw dev &
          sleep 5
          pytest tests/e2e/
```

## Best Practices

1. **Test behavior, not implementation**: Check outputs, not internal state.
2. **Use fixtures**: Share setup code across tests.
3. **Mock external services**: Don't hit real APIs in tests.
4. **Test edge cases**: Empty inputs, special characters, large data.
5. **Keep tests fast**: Unit tests should run in milliseconds.
6. **Name tests clearly**: `test_should_do_x_when_y`.
7. **One assertion per test**: Or group related assertions.

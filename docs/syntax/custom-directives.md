# Custom Directives

TW Framework supports extending the language with custom directives.

## What Are Directives?

Directives are special instructions processed by the compiler. Built-in examples include:

- `load "@./style.tss"` — loads a stylesheet
- `import "Hero"` — imports a component
- `env: public: "API_KEY"` — exposes environment variables

## Creating a Custom Directive

### Step 1: Define the Handler

Create a Python module:

```python
# [home]/directives/analytics.py
from tw_framework.plugin_runtime import register_directive

def analytics_directive(context, directive_args):
    tracking_id = directive_args[0] if directive_args else ""
    script = f'<script async src="https://analytics.example.com/track.js?id={tracking_id}"></script>'
    return {
        "head": script,
        "context_updates": {"analytics_id": tracking_id}
    }

register_directive("analytics", analytics_directive)
```

### Step 2: Register in tw.config

```
name: "My Site"
directives:
    analytics: "[home]/directives/analytics.py"
```

### Step 3: Use in .tw Files

```tw
page {
    title "Home"
    layout "main"
    render static
}

analytics "UA-123456-1"

body {
    h1 "Welcome"
}
```

## Directive Lifecycle

1. **Parse phase**: Directive is recognized and arguments captured.
2. **Analysis phase**: Arguments are validated.
3. **Render phase**: Handler runs and injects content.

## Common Use Cases

### Google Analytics

```python
def ga_directive(context, args):
    tracking_id = args[0]
    return {
        "head": f'''<script async src="https://www.googletagmanager.com/gtag/js?id={tracking_id}"></script>
        <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{tracking_id}');</script>'''
    }
```

### Custom Fonts

```python
def font_directive(context, args):
    font_url = args[0]
    font_family = args[1] if len(args) > 1 else "CustomFont"
    return {
        "head": f'<link rel="stylesheet" href="{font_url}">',
        "context_updates": {"font_family": font_family}
    }
```

Usage:

```tw
font "https://fonts.googleapis.com/css2?family=Inter" "Inter"
```

## Best Practices

1. **Validate arguments**: Always check required args.
2. **Escape output**: Use `html_escape()` for dynamic content.
3. **Document directives**: Add README in `directives/`.
4. **Keep handlers pure**: Avoid file writes or network calls.
5. **Test independently**: Write unit tests for handlers.

## Testing Directives

```python
from directives.analytics import analytics_directive

def test_analytics_directive():
    result = analytics_directive({}, ["UA-123"])
    assert "UA-123" in result["head"]
    assert result["context_updates"]["analytics_id"] == "UA-123"
```

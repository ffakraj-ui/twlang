# Plugin Development

## TW Framework Plugin System

TW Framework has a plugin runtime that allows extending the compiler and framework.

## Plugin API

```python
# [home]/plugins/my_plugin.py

from tw_framework.plugin_runtime import PluginAPI

class MyPlugin(PluginAPI):
    name = "my-plugin"
    version = "1.0.0"

    def init(self, config):
        self.config = config

    def before_compile(self, page_info):
        return page_info

    def after_compile(self, page_info, output):
        return output

    def before_build(self, project_root):
        pass

    def after_build(self, output_dir):
        pass
```

## Registering Plugins

In tw.config:

```
plugins {
  my-plugin {
    enabled true
    option "value"
  }
}
```

## Plugin Use Cases

### Custom Analytics

```python
class AnalyticsPlugin(PluginAPI):
    name = "analytics"

    def after_compile(self, page_info, output):
        script = '<script>track_page_view();</script>'
        return output.replace('</body>', script + '</body>')
```

### Custom CSS Processing

```python
class CSSPlugin(PluginAPI):
    name = "css-processor"

    def after_compile(self, page_info, output):
        return output.replace('</head>', '<style>.custom{color:red}</style></head>')
```

## Plugin Lifecycle

1. init(config) - Plugin loaded
2. before_build(project_root) - Build starting
3. before_compile(page_info) - Per-page, before compile
4. after_compile(page_info, output) - Per-page, after compile
5. after_build(output_dir) - Build complete

## VS Code Extension Plugin

For VS Code extensions, see vscode-tw/ folder:

- extension.js - LSP client
- server.js - JSON-RPC bridge
- package.json - Extension metadata
- language-configuration.json - Editor config
- syntaxes/ - TextMate grammar files

## ACode Plugin

For ACode (Android editor), see the ACode plugin zip:

- plugin.json - Plugin metadata
- main.js - Plugin code (registers language, LSP)
- icon.png - Plugin icon

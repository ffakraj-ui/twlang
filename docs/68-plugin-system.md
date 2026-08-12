# Plugin System

## Overview

TW Framework has a plugin runtime for extending build and dev server.

## Plugin API

```python
from tw_framework.plugin_runtime import PluginAPI

class MyPlugin:
    def init(self):
        self.api = PluginAPI()
        self.api.on_build_start(self.before_build)
        self.api.on_build_end(self.after_build)
        self.api.on_page_compile(self.transform_page)

    def before_build(self, context):
        print("Build starting")

    def after_build(self, summary):
        print(f"Build complete: {summary.pages} pages")

    def transform_page(self, page_ast, context):
        return page_ast
```

## Available Hooks

| Hook | When | Use Case |
|---|---|---|
| on_build_start | Before build | Setup, validation |
| on_build_end | After build | Reporting, cleanup |
| on_page_compile | Before page compiles | AST transformation |
| on_dev_start | Dev server starts | Dev-only setup |
| on_request | Before each request | Request middleware |

## Plugin vs Middleware

| Feature | Plugin | Middleware |
|---|---|---|
| Scope | Build + dev | Runtime |
| Language | Python | TW syntax |
| Access | AST, build context | Request/response |

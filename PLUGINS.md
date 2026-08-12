# TW Framework — Plugin System

## Overview

TW Framework has a WordPress-inspired plugin system with `.twp` format, 5 lifecycle hooks, and auto-yes permissions.

## Commands

```bash
tw plugin add seo-booster    # Install plugin
tw plugin remove seo-booster # Remove plugin
tw plugin list               # List installed plugins
tw plugin search             # Search registry
```

## Plugin Format (.twp)

Plugins are `.twp` files that define hooks for build and request lifecycle events.

## Lifecycle Hooks

| Hook | When | Use Case |
|------|------|----------|
| `beforeBuild` | Before compilation starts | Modify build config, inject assets |
| `afterBuild` | After build completes | Post-build transformations, optimizations |
| `beforeRoute` | Before route is processed | Route-level modifications, redirects |
| `afterRoute` | After route is processed | Post-route analytics, caching |
| `beforeRequest` | Before each request | Per-request auth, logging, rate limiting |

## ExtensionManager API

```python
from tw_framework.plugin_runtime import ExtensionManager

manager = ExtensionManager(project_root, config, env)
manager.refresh()                          # Discover and load .twp files
manager.emit("beforeBuild", project=...)   # Emit event to all hooks
manager.dependency_paths()                 # Get extension dependency paths
manager.register_hook("beforeBuild", handler, "my-plugin")
```

## Plugin Discovery

Plugins are discovered from:
1. `[home]/plugins/` directory
2. Project root `plugins/` directory
3. Installed via `tw plugin add`

## Permissions

Plugins use auto-yes permissions — no explicit permission grants needed. All hooks are executed in the order they were registered.

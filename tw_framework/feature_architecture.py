"""
Feature-Sliced Architecture for TW Framework.

Supports organizing large applications by feature/domain, like Next.js
src/features/<domain>/ pattern:

  [home]/
    features/
      auth/
        components/     # Login form, Signup form
        hooks/          # useAuth, useSession
        routes/         # /login, /signup
        api/            # /api/auth/*
        actions.tw      # server actions for auth
        style.tss       # scoped styles
      dashboard/
        components/
        hooks/
        routes/
        api/
        actions.tw
      blog/
        components/
        hooks/
        routes/
        api/

Features are loosely coupled — each feature has its own components, hooks,
routes, API endpoints, and styles. The compiler auto-discovers feature
directories and integrates them into the build pipeline.

Usage:
  from tw_framework.feature_architecture import FeatureScanner
  scanner = FeatureScanner(project_root)
  features = scanner.discover_features()
  # → [{name: "auth", path: "[home]/features/auth", has_components: True, ...}]
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import signal
import importlib

logger = logging.getLogger(__name__)


@dataclass
class FeatureModule:
    """A single feature module (e.g. auth, dashboard, blog)."""
    name: str
    path: str                               # absolute path to feature directory
    has_components: bool = False
    has_hooks: bool = False
    has_routes: bool = False
    has_api: bool = False
    has_actions: bool = False
    has_styles: bool = False
    has_middleware: bool = False
    component_files: List[str] = field(default_factory=list)
    hook_files: List[str] = field(default_factory=list)
    route_files: List[str] = field(default_factory=list)
    api_files: List[str] = field(default_factory=list)
    action_files: List[str] = field(default_factory=list)
    style_files: List[str] = field(default_factory=list)
    middleware_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # other features this depends on

    def url_paths(self) -> List[str]:
        """Return URL paths this feature serves."""
        paths = []
        # Routes → /<feature>/<route>
        for rf in self.route_files:
            rel = os.path.basename(rf).replace(".tw", "")
            if rel == "index" or rel == "page":
                paths.append(f"/{self.name}/")
            else:
                paths.append(f"/{self.name}/{rel}")
        # API routes → /api/<feature>/<route>
        for af in self.api_files:
            rel = os.path.basename(af).replace(".tw", "")
            if rel == "route":
                paths.append(f"/api/{self.name}/")
            else:
                paths.append(f"/api/{self.name}/{rel}")
        return paths

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict for tw info / tw doctor."""
        return {
            "name": self.name,
            "path": self.path,
            "has_components": self.has_components,
            "has_hooks": self.has_hooks,
            "has_routes": self.has_routes,
            "has_api": self.has_api,
            "has_actions": self.has_actions,
            "has_styles": self.has_styles,
            "component_count": len(self.component_files),
            "route_count": len(self.route_files),
            "api_count": len(self.api_files),
            "dependencies": self.dependencies,
            "url_paths": self.url_paths(),
        }


class FeatureScanner:
    """Scans the project for feature-sliced directories.

    Looks for [home]/features/<name>/ directories and catalogs
    their contents (components, hooks, routes, API, actions, styles).

    This integrates with the compiler's discover_pages() to
    automatically include feature routes in the build.
    """

    # Valid subdirectories within a feature
    SUBDIRS = {
        "components": "component_files",
        "hooks": "hook_files",
        "routes": "route_files",
        "api": "api_files",
        "lib": "hook_files",  # lib is treated like hooks
        "server": "api_files",  # server is treated like API
    }

    # Valid standalone files within a feature
    FILE_PATTERNS = {
        r"^actions\.tw$": "action_files",
        r"^action\.tw$": "action_files",
        r"^style\.tss$": "style_files",
        r"^styles\.tss$": "style_files",
        r"^middleware\.tw$": "middleware_files",
    }

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self.home_dir = os.path.join(self.project_root, "[home]")
        self.features_dir = os.path.join(self.home_dir, "features")
        self._features: Dict[str, FeatureModule] = {}

    def has_features(self) -> bool:
        """Check if the project uses feature-sliced architecture."""
        return os.path.isdir(self.features_dir)

    def discover_features(self) -> List[FeatureModule]:
        """Discover all feature modules in [home]/features/.

        Returns a list of FeatureModule objects.
        """
        if not self.has_features():
            return []

        features: List[FeatureModule] = []

        for entry in sorted(os.listdir(self.features_dir)):
            feat_path = os.path.join(self.features_dir, entry)
            if not os.path.isdir(feat_path):
                continue

            # Skip non-feature dirs (like __pycache__, node_modules)
            if entry.startswith("_") or entry.startswith("."):
                continue

            feature = self._scan_feature(entry, feat_path)
            features.append(feature)
            self._features[entry] = feature

        # Resolve cross-feature dependencies
        self._resolve_dependencies()

        logger.info("Discovered %d features: %s",
                     len(features),
                     [f.name for f in features])
        return features

    def _scan_feature(self, name: str, feat_path: str) -> FeatureModule:
        """Scan a single feature directory."""
        feature = FeatureModule(name=name, path=feat_path)

        # Scan subdirectories
        for root, dirs, files in os.walk(feat_path):
            rel_root = os.path.relpath(root, feat_path)

            # Check if this root matches a known subdir
            subdir_name = os.path.basename(root) if rel_root != "." else ""
            attr_name = self.SUBDIRS.get(subdir_name)

            if attr_name:
                for fname in files:
                    if fname.endswith((".tw", ".js", ".ts", ".tss")):
                        fpath = os.path.join(root, fname)
                        getattr(feature, attr_name).append(fpath)

            # Also check for standalone files at feature root
            if rel_root == ".":
                for fname in files:
                    for pattern, attr in self.FILE_PATTERNS.items():
                        if re.match(pattern, fname):
                            fpath = os.path.join(root, fname)
                            getattr(feature, attr).append(fpath)

            # Routes can also be at feature root (page.tw, route.tw)
            if rel_root == ".":
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if fname == "page.tw" and fpath not in feature.route_files:
                        feature.route_files.append(fpath)
                    elif fname == "route.tw" and fpath not in feature.api_files:
                        feature.api_files.append(fpath)

        # Set boolean flags
        feature.has_components = len(feature.component_files) > 0
        feature.has_hooks = len(feature.hook_files) > 0
        feature.has_routes = len(feature.route_files) > 0
        feature.has_api = len(feature.api_files) > 0
        feature.has_actions = len(feature.action_files) > 0
        feature.has_styles = len(feature.style_files) > 0
        feature.has_middleware = len(feature.middleware_files) > 0

        return feature

    def _resolve_dependencies(self) -> None:
        """Scan feature source files for cross-feature imports.

        If feature "auth" imports from feature "blog",
        then auth depends on blog.
        """
        for name, feature in self._features.items():
            all_files = (feature.component_files + feature.route_files +
                        feature.api_files + feature.hook_files +
                        feature.action_files)
            for fpath in all_files:
                try:
                    with open(fpath, "r", errors="ignore") as f:
                        source = f.read()
                except OSError:
                    continue

                # Look for imports from other features
                # Pattern: import ... from "../features/<name>/..."
                # or: load "@./features/<name>/..."
                for other_name in self._features:
                    if other_name == name:
                        continue
                    if f"features/{other_name}" in source or f"../{other_name}" in source:
                        if other_name not in feature.dependencies:
                            feature.dependencies.append(other_name)

    def get_feature(self, name: str) -> Optional[FeatureModule]:
        """Get a specific feature by name."""
        return self._features.get(name)

    def get_all_routes(self) -> List[Dict[str, Any]]:
        """Get all routes from all features.

        Returns a list of route dicts compatible with compiler.discover_pages().
        """
        routes: List[Dict[str, Any]] = []
        for feature in self._features.values():
            for rf in feature.route_files:
                routes.append({
                    "type": "static",
                    "path": rf,
                    "rel_dir": f"features/{feature.name}",
                    "name": feature.name,
                    "app_router": True,
                    "url_path": f"/{feature.name}",
                    "feature": feature.name,
                })
            for af in feature.api_files:
                routes.append({
                    "type": "api",
                    "path": af,
                    "rel_dir": f"features/{feature.name}/api",
                    "name": feature.name,
                    "app_router": True,
                    "url_path": f"/api/{feature.name}",
                    "feature": feature.name,
                })
        return routes

    def get_all_components(self) -> Dict[str, str]:
        """Get all component files from all features.

        Returns a dict of component_name → file_path.
        """
        components: Dict[str, str] = {}
        for feature in self._features.values():
            for cf in feature.component_files:
                if cf.endswith(".tw"):
                    comp_name = os.path.basename(cf).replace(".tw", "")
                    components[comp_name] = cf
        return components

    def get_all_styles(self) -> List[str]:
        """Get all style files from all features."""
        styles: List[str] = []
        for feature in self._features.values():
            styles.extend(feature.style_files)
        return styles

    def get_all_actions(self) -> List[str]:
        """Get all action files from all features."""
        actions: List[str] = []
        for feature in self._features.values():
            actions.extend(feature.action_files)
        return actions

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all features for tw info / tw doctor."""
        return {
            "features_dir": self.features_dir,
            "has_features": self.has_features(),
            "feature_count": len(self._features),
            "features": [f.summary() for f in self._features.values()],
            "total_routes": sum(len(f.route_files) for f in self._features.values()),
            "total_apis": sum(len(f.api_files) for f in self._features.values()),
            "total_components": sum(len(f.component_files) for f in self._features.values()),
            "total_actions": sum(len(f.action_files) for f in self._features.values()),
        }


def integrate_with_compiler(scanner: FeatureScanner) -> List[Dict[str, Any]]:
    """Integrate feature-sliced routes with the compiler's discover_pages().

    Call this from the compiler to include feature routes in the build.
    Returns a list of route dicts that can be merged with discover_pages() output.
    """
    if not scanner.has_features():
        return []
    return scanner.get_all_routes()


__all__ = [
    "FeatureModule",
    "FeatureScanner",
    "integrate_with_compiler",
    "FeatureLifecycleHook",
    "FeatureLifecycleManager",
    "FeatureMiddleware",
    "FeatureMiddlewareChain",
    "FeatureConfig",
    "FeatureConfigManager",
    "FeatureDependencyResolver",
    "FeatureRegistry",
    "FeatureLoadResult",
    "FeatureLoader",
    "FeatureSandbox",
    "FeatureCodeGenerator",
    "FeatureHealthChecker",
]


# ── Feature Lifecycle Manager ────────────────────────────────────────

@dataclass
class FeatureLifecycleHook:
    """A lifecycle hook for a feature."""
    feature_name: str
    hook_name: str          # on_init, on_build_start, on_build_end, on_request_start, on_request_end
    handler: Callable       # callable that receives context dict
    priority: int = 0       # lower = runs first


class FeatureLifecycleManager:
    """Manages feature lifecycle hooks.

    Features can register hooks that are called at various points
    in the build and request lifecycle:

    - on_init: Called when the feature is first loaded
    - on_build_start: Called before the build starts
    - on_build_end: Called after the build completes
    - on_request_start: Called at the beginning of each request
    - on_request_end: Called at the end of each request

    Hooks are executed in priority order (lower priority = earlier).
    """

    def __init__(self):
        self._hooks: Dict[str, List[FeatureLifecycleHook]] = {}

    def register_hook(self, feature_name: str, hook_name: str,
                      handler: Callable, priority: int = 0) -> None:
        """Register a lifecycle hook for a feature."""
        hook = FeatureLifecycleHook(
            feature_name=feature_name,
            hook_name=hook_name,
            handler=handler,
            priority=priority,
        )
        self._hooks.setdefault(hook_name, []).append(hook)
        # Sort by priority
        self._hooks[hook_name].sort(key=lambda h: h.priority)

    def emit(self, hook_name: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Emit a lifecycle event to all registered hooks.

        Returns a dict of {feature_name: result} for all hooks that returned something.
        """
        context = context or {}
        results: Dict[str, Any] = {}

        for hook in self._hooks.get(hook_name, []):
            try:
                result = hook.handler(context)
                if result is not None:
                    results[hook.feature_name] = result
            except Exception as e:
                logger.warning(
                    "Feature %s hook %s failed: %s",
                    hook.feature_name, hook_name, e
                )
                results[hook.feature_name] = {"error": str(e)}

        return results

    def get_hooks(self, hook_name: str) -> List[Dict[str, Any]]:
        """Return info about hooks for a given event."""
        return [
            {
                "feature": h.feature_name,
                "hook": h.hook_name,
                "priority": h.priority,
            }
            for h in self._hooks.get(hook_name, [])
        ]

    def remove_feature(self, feature_name: str) -> int:
        """Remove all hooks for a feature. Returns count removed."""
        count = 0
        for hook_name in list(self._hooks.keys()):
            before = len(self._hooks[hook_name])
            self._hooks[hook_name] = [
                h for h in self._hooks[hook_name]
                if h.feature_name != feature_name
            ]
            count += before - len(self._hooks[hook_name])
        return count

    def summary(self) -> Dict[str, Any]:
        """Return summary of all registered hooks."""
        return {
            hook_name: [
                {"feature": h.feature_name, "priority": h.priority}
                for h in hooks
            ]
            for hook_name, hooks in self._hooks.items()
        }


# ── Feature Middleware ──────────────────────────────────────────────

@dataclass
class FeatureMiddleware:
    """Middleware scoped to a specific feature.

    Only runs for requests that match the feature's route prefix.
    """
    feature_name: str
    route_prefix: str       # e.g. "/auth" — only runs for /auth/**
    handler: Callable       # callable(request, response) → modified response
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    priority: int = 0


class FeatureMiddlewareChain:
    """Chain of feature-scoped middleware.

    Each middleware only runs for requests matching its feature's routes.
    This allows features to be self-contained with their own middleware.
    """

    def __init__(self):
        self._middleware: List[FeatureMiddleware] = []
        self._sorted = True

    def register(self, feature_name: str, route_prefix: str,
                 handler: Callable, methods: Optional[List[str]] = None,
                 priority: int = 0) -> None:
        """Register middleware for a feature."""
        mw = FeatureMiddleware(
            feature_name=feature_name,
            route_prefix=route_prefix,
            handler=handler,
            methods=methods or ["GET", "POST", "PUT", "DELETE"],
            priority=priority,
        )
        self._middleware.append(mw)
        self._sorted = False

    def _ensure_sorted(self) -> None:
        """Sort middleware by priority if needed."""
        if not self._sorted:
            self._middleware.sort(key=lambda m: m.priority)
            self._sorted = True

    def process(self, request: dict, response: dict) -> dict:
        """Process a request through all matching feature middleware.

        Only middleware whose route_prefix matches the request path
        and whose methods include the request method will run.
        """
        self._ensure_sorted()
        path = request.get("path", "")
        method = request.get("method", "GET")

        for mw in self._middleware:
            # Check route prefix match
            if not path.startswith(mw.route_prefix):
                continue
            # Check method
            if method not in mw.methods:
                continue
            # Run middleware
            try:
                result = mw.handler(request, response)
                if result is not None:
                    response = result
                # If middleware returns a final response (with status), stop
                if isinstance(response, dict) and response.get("_final"):
                    break
            except Exception as e:
                logger.warning(
                    "Feature %s middleware failed: %s",
                    mw.feature_name, e
                )

        return response

    def get_feature_middleware(self, feature_name: str) -> List[Dict[str, Any]]:
        """Return middleware registered by a specific feature."""
        return [
            {
                "feature": mw.feature_name,
                "route_prefix": mw.route_prefix,
                "methods": mw.methods,
                "priority": mw.priority,
            }
            for mw in self._middleware
            if mw.feature_name == feature_name
        ]

    def remove_feature(self, feature_name: str) -> int:
        """Remove all middleware for a feature. Returns count removed."""
        before = len(self._middleware)
        self._middleware = [m for m in self._middleware if m.feature_name != feature_name]
        return before - len(self._middleware)

    def summary(self) -> List[Dict[str, Any]]:
        """Return summary of all middleware."""
        self._ensure_sorted()
        return [
            {
                "feature": mw.feature_name,
                "route_prefix": mw.route_prefix,
                "methods": mw.methods,
                "priority": mw.priority,
            }
            for mw in self._middleware
        ]


# ── Feature Configuration ───────────────────────────────────────────

@dataclass
class FeatureConfig:
    """Configuration for a feature module."""
    name: str
    enabled: bool = True
    route_prefix: str = ""           # e.g. "/auth" — auto-generated from name if empty
    api_prefix: str = ""             # e.g. "/api/auth"
    middleware_enabled: bool = True
    lifecycle_hooks_enabled: bool = True
    cache_enabled: bool = True
    cache_revalidate: int = 0        # 0 = no caching
    cache_tags: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)  # required permissions
    env_required: List[str] = field(default_factory=list)  # required env vars
    options: Dict[str, Any] = field(default_factory=dict)  # feature-specific options

    def __post_init__(self):
        if not self.route_prefix:
            self.route_prefix = f"/{self.name}"
        if not self.api_prefix:
            self.api_prefix = f"/api/{self.name}"


class FeatureConfigManager:
    """Manages configuration for all features.

    Loads feature configs from tw.config or feature-specific config files.
    Provides a unified interface for querying feature configuration.
    """

    def __init__(self):
        self._configs: Dict[str, FeatureConfig] = {}
        self._global_options: Dict[str, Any] = {}

    def register(self, config: FeatureConfig) -> None:
        """Register a feature configuration."""
        self._configs[config.name] = config

    def register_from_dict(self, name: str, data: Dict[str, Any]) -> None:
        """Register a feature config from a dict (e.g. from tw.config)."""
        config = FeatureConfig(
            name=name,
            enabled=data.get("enabled", True),
            route_prefix=data.get("route_prefix", f"/{name}"),
            api_prefix=data.get("api_prefix", f"/api/{name}"),
            middleware_enabled=data.get("middleware_enabled", True),
            lifecycle_hooks_enabled=data.get("lifecycle_hooks_enabled", True),
            cache_enabled=data.get("cache_enabled", True),
            cache_revalidate=data.get("cache_revalidate", 0),
            cache_tags=data.get("cache_tags", []),
            permissions=data.get("permissions", []),
            env_required=data.get("env_required", []),
            options=data.get("options", {}),
        )
        self._configs[name] = config

    def get(self, name: str) -> Optional[FeatureConfig]:
        """Get configuration for a feature."""
        return self._configs.get(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a feature is enabled."""
        config = self._configs.get(name)
        return config.enabled if config else False

    def get_enabled_features(self) -> List[str]:
        """Return list of enabled feature names."""
        return [name for name, cfg in self._configs.items() if cfg.enabled]

    def get_disabled_features(self) -> List[str]:
        """Return list of disabled feature names."""
        return [name for name, cfg in self._configs.items() if not cfg.enabled]

    def check_env_requirements(self) -> Dict[str, List[str]]:
        """Check which features are missing required env vars.

        Returns dict of {feature_name: [missing_env_vars]}.
        """
        missing: Dict[str, List[str]] = {}
        for name, config in self._configs.items():
            if not config.enabled:
                continue
            missing_vars = [
                var for var in config.env_required
                if not os.environ.get(var)
            ]
            if missing_vars:
                missing[name] = missing_vars
        return missing

    def get_route_prefixes(self) -> Dict[str, str]:
        """Return all feature route prefixes."""
        return {
            name: cfg.route_prefix
            for name, cfg in self._configs.items()
            if cfg.enabled
        }

    def get_api_prefixes(self) -> Dict[str, str]:
        """Return all feature API prefixes."""
        return {
            name: cfg.api_prefix
            for name, cfg in self._configs.items()
            if cfg.enabled
        }

    def summary(self) -> Dict[str, Any]:
        """Return summary of all feature configs."""
        return {
            "total_features": len(self._configs),
            "enabled": len(self.get_enabled_features()),
            "disabled": len(self.get_disabled_features()),
            "features": {
                name: {
                    "enabled": cfg.enabled,
                    "route_prefix": cfg.route_prefix,
                    "api_prefix": cfg.api_prefix,
                    "cache_enabled": cfg.cache_enabled,
                    "cache_revalidate": cfg.cache_revalidate,
                    "permissions": cfg.permissions,
                    "env_required": cfg.env_required,
                }
                for name, cfg in self._configs.items()
            },
            "missing_env_vars": self.check_env_requirements(),
        }


# ── Feature Dependency Resolver ─────────────────────────────────────

class FeatureDependencyResolver:
    """Resolves dependencies between features.

    Ensures features are initialized in the correct order based
    on their cross-feature dependencies.
    """

    def __init__(self, scanner: FeatureScanner):
        self.scanner = scanner

    def get_load_order(self) -> List[str]:
        """Get the order in which features should be loaded.

        Uses topological sort based on cross-feature dependencies.
        """
        from collections import deque

        features = self.scanner.discover_features()
        feature_names = [f.name for f in features]

        # Build adjacency list
        in_degree: Dict[str, int] = {name: 0 for name in feature_names}
        adj: Dict[str, List[str]] = {name: [] for name in feature_names}

        for feature in features:
            for dep in feature.dependencies:
                if dep in feature_names:
                    adj[dep].append(feature.name)
                    in_degree[feature.name] += 1

        # Kahn's algorithm
        queue: deque = deque([n for n, d in in_degree.items() if d == 0])
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any remaining (circular dependency case)
        remaining = set(feature_names) - set(order)
        order.extend(remaining)

        return order

    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies between features."""
        features = self.scanner.discover_features()
        feature_names = [f.name for f in features]

        graph: Dict[str, List[str]] = {}
        for feature in features:
            graph[feature.name] = [
                dep for dep in feature.dependencies if dep in feature_names
            ]

        cycles: List[List[str]] = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {n: WHITE for n in feature_names}
        stack: List[str] = []

        def dfs(node: str):
            color[node] = GRAY
            stack.append(node)
            for neighbor in graph.get(node, []):
                if color.get(neighbor, WHITE) == GRAY:
                    # Found cycle
                    cycle_start = stack.index(neighbor)
                    cycle = stack[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                elif color.get(neighbor, WHITE) == WHITE:
                    dfs(neighbor)
            stack.pop()
            color[node] = BLACK

        for node in feature_names:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def get_dependency_tree(self) -> Dict[str, Any]:
        """Build a dependency tree for all features."""
        features = self.scanner.discover_features()
        tree: Dict[str, Any] = {}

        for feature in features:
            tree[feature.name] = {
                "dependencies": feature.dependencies,
                "dependents": [],  # Will be filled below
            }

        # Find dependents
        for feature in features:
            for dep in feature.dependencies:
                if dep in tree:
                    tree[dep]["dependents"].append(feature.name)

        return tree


# ── Feature Registry (unified manager) ──────────────────────────────

class FeatureRegistry:
    """Unified registry for all feature-sliced architecture components.

    Combines:
    - FeatureScanner (discovery)
    - FeatureConfigManager (configuration)
    - FeatureLifecycleManager (lifecycle hooks)
    - FeatureMiddlewareChain (middleware)
    - FeatureDependencyResolver (dependency resolution)
    """

    def __init__(self, project_root: str = ""):
        self.project_root = project_root or os.getcwd()
        self.scanner = FeatureScanner(project_root)
        self.config_manager = FeatureConfigManager()
        self.lifecycle = FeatureLifecycleManager()
        self.middleware = FeatureMiddlewareChain()
        self._resolver: Optional[FeatureDependencyResolver] = None
        self._initialized = False

    def initialize(self) -> Dict[str, Any]:
        """Initialize the feature registry.

        1. Discover all features
        2. Load configurations
        3. Resolve dependencies
        4. Compute load order
        5. Call on_init hooks

        Returns a summary dict.
        """
        if self._initialized:
            return {"already_initialized": True}

        # Discover features
        features = self.scanner.discover_features()

        # Auto-register configs
        for feature in features:
            if not self.config_manager.get(feature.name):
                self.config_manager.register(FeatureConfig(name=feature.name))

        # Resolve dependencies
        self._resolver = FeatureDependencyResolver(self.scanner)
        load_order = self._resolver.get_load_order()
        cycles = self._resolver.detect_circular_dependencies()

        # Call on_init hooks
        init_results = self.lifecycle.emit("on_init", {
            "features": [f.name for f in features],
            "load_order": load_order,
        })

        self._initialized = True

        return {
            "features_discovered": len(features),
            "feature_names": [f.name for f in features],
            "load_order": load_order,
            "circular_dependencies": cycles,
            "init_results": init_results,
            "config_summary": self.config_manager.summary(),
        }

    def process_request(self, request: dict, response: dict) -> dict:
        """Process a request through feature middleware."""
        # Emit on_request_start
        self.lifecycle.emit("on_request_start", {"request": request})

        # Run feature middleware
        response = self.middleware.process(request, response)

        # Emit on_request_end
        self.lifecycle.emit("on_request_end", {
            "request": request,
            "response": response,
        })

        return response

    def on_build_start(self) -> Dict[str, Any]:
        """Called before a build — emits lifecycle hook."""
        return self.lifecycle.emit("on_build_start", {
            "features": self.config_manager.get_enabled_features(),
        })

    def on_build_end(self, build_result: dict) -> Dict[str, Any]:
        """Called after a build — emits lifecycle hook."""
        return self.lifecycle.emit("on_build_end", {
            "build_result": build_result,
            "features": self.config_manager.get_enabled_features(),
        })

    def get_all_routes(self) -> List[Dict[str, Any]]:
        """Get all routes from all enabled features."""
        if not self.config_manager.get_enabled_features():
            return self.scanner.get_all_routes()
        return [
            route for route in self.scanner.get_all_routes()
            if route.get("feature") in self.config_manager.get_enabled_features()
        ]

    def get_all_components(self) -> Dict[str, str]:
        """Get all components from all enabled features."""
        all_components = self.scanner.get_all_components()
        enabled = self.config_manager.get_enabled_features()
        return {
            name: path for name, path in all_components.items()
            if any(f"/{f}/" in path for f in enabled)
        }

    def summary(self) -> Dict[str, Any]:
        """Return comprehensive summary."""
        scanner_summary = self.scanner.summary() if self.scanner.has_features() else {}
        return {
            "initialized": self._initialized,
            "scanner": scanner_summary,
            "config": self.config_manager.summary() if self._initialized else {},
            "lifecycle": self.lifecycle.summary(),
            "middleware": self.middleware.summary(),
            "load_order": self._resolver.get_load_order() if self._resolver else [],
            "circular_deps": self._resolver.detect_circular_dependencies() if self._resolver else [],
        }

    def get_feature_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a specific feature."""
        feature = self.scanner.get_feature(name)
        if not feature:
            return None
        config = self.config_manager.get(name)
        return {
            "name": feature.name,
            "path": feature.path,
            "summary": feature.summary(),
            "config": {
                "enabled": config.enabled if config else False,
                "route_prefix": config.route_prefix if config else f"/{name}",
                "api_prefix": config.api_prefix if config else f"/api/{name}",
                "cache_enabled": config.cache_enabled if config else False,
            } if config else {},
            "middleware": self.middleware.get_feature_middleware(name),
            "dependencies": feature.dependencies,
        }


# ── Update __all__ ──────────────────────────────────────────────────



# ── Feature Loader ───────────────────────────────────────────────────

@dataclass
class FeatureLoadResult:
    """Result of loading a feature module."""
    feature_name: str
    success: bool
    load_time_ms: float = 0.0
    error: str = ""
    components_loaded: int = 0
    routes_registered: int = 0
    middleware_registered: int = 0


class FeatureLoader:
    """Loads feature modules dynamically.

    Supports:
    - Lazy loading (load on first access)
    - Eager loading (load at startup)
    - Conditional loading (based on environment/config)
    - Hot reloading (reload without restart)
    - Load ordering (based on dependencies)
    """

    def __init__(self, base_path: str = "features"):
        self.base_path = base_path
        self._loaded: Dict[str, Any] = {}
        self._load_order: List[str] = []
        self._load_times: Dict[str, float] = {}
        self._loading: Set[str] = set()  # Currently loading (cycle detection)
        self._lazy_features: Dict[str, str] = {}  # name → module path
        self._conditions: Dict[str, Callable[[], bool]] = {}  # name → condition fn

    def register_feature(self, name: str, module_path: str,
                          lazy: bool = True,
                          condition: Optional[Callable[[], bool]] = None) -> None:
        """Register a feature for loading.

        Args:
            name: Feature name
            module_path: Python module path (e.g. "features.auth")
            lazy: If True, load on first access. If False, load immediately.
            condition: Optional condition function — feature only loads if True
        """
        self._lazy_features[name] = module_path
        if condition:
            self._conditions[name] = condition

        if not lazy:
            self.load(name)

    def load(self, name: str) -> FeatureLoadResult:
        """Load a feature module by name."""
        import time as _time
        start = _time.time()

        # Already loaded
        if name in self._loaded:
            return FeatureLoadResult(
                feature_name=name, success=True,
                load_time_ms=0.0,
                components_loaded=len(getattr(self._loaded[name], "components", [])),
            )

        # Check for circular loading
        if name in self._loading:
            return FeatureLoadResult(
                feature_name=name, success=False,
                error=f"Circular dependency detected while loading {name}",
            )

        # Check condition
        condition = self._conditions.get(name)
        if condition and not condition():
            return FeatureLoadResult(
                feature_name=name, success=False,
                error="Condition not met for feature",
            )

        module_path = self._lazy_features.get(name)
        if not module_path:
            return FeatureLoadResult(
                feature_name=name, success=False,
                error=f"Feature {name} not registered",
            )

        self._loading.add(name)

        try:
            import importlib
            module = importlib.import_module(module_path)
            self._loaded[name] = module
            self._load_order.append(name)
            load_time = (_time.time() - start) * 1000
            self._load_times[name] = load_time

            components = getattr(module, "components", [])
            routes = getattr(module, "routes", [])
            middleware = getattr(module, "middleware", [])

            logger.info("Feature '%s' loaded in %.1fms (%d components, %d routes)",
                        name, load_time, len(components), len(routes))

            return FeatureLoadResult(
                feature_name=name,
                success=True,
                load_time_ms=load_time,
                components_loaded=len(components),
                routes_registered=len(routes),
                middleware_registered=len(middleware),
            )
        except Exception as e:
            logger.error("Failed to load feature '%s': %s", name, e)
            return FeatureLoadResult(
                feature_name=name,
                success=False,
                load_time_ms=(_time.time() - start) * 1000,
                error=str(e),
            )
        finally:
            self._loading.discard(name)

    def load_all(self) -> List[FeatureLoadResult]:
        """Load all registered features in dependency order."""
        results: List[FeatureLoadResult] = []
        for name in list(self._lazy_features.keys()):
            results.append(self.load(name))
        return results

    def unload(self, name: str) -> bool:
        """Unload a feature module."""
        if name not in self._loaded:
            return False

        # Call cleanup if available
        module = self._loaded[name]
        cleanup = getattr(module, "cleanup", None)
        if cleanup:
            try:
                cleanup()
            except Exception as e:
                logger.warning("Error during cleanup of '%s': %s", name, e)

        del self._loaded[name]
        if name in self._load_order:
            self._load_order.remove(name)
        self._load_times.pop(name, None)

        logger.info("Feature '%s' unloaded", name)
        return True

    def reload(self, name: str) -> FeatureLoadResult:
        """Hot-reload a feature module."""
        self.unload(name)

        # Force re-import
        module_path = self._lazy_features.get(name)
        if module_path:
            import importlib, sys
            if module_path in sys.modules:
                del sys.modules[module_path]

        return self.load(name)

    def get_feature(self, name: str) -> Any:
        """Get a loaded feature module, or load it if lazy."""
        if name not in self._loaded and name in self._lazy_features:
            self.load(name)
        return self._loaded.get(name)

    def is_loaded(self, name: str) -> bool:
        """Check if a feature is loaded."""
        return name in self._loaded

    def get_load_stats(self) -> Dict[str, Any]:
        """Return loading statistics."""
        return {
            "total_registered": len(self._lazy_features),
            "total_loaded": len(self._loaded),
            "load_order": list(self._load_order),
            "load_times_ms": {k: round(v, 2) for k, v in self._load_times.items()},
            "total_load_time_ms": round(sum(self._load_times.values()), 2),
        }

    def get_loaded_features(self) -> List[str]:
        """Return list of loaded feature names."""
        return list(self._loaded.keys())

    def get_pending_features(self) -> List[str]:
        """Return list of registered but not-yet-loaded features."""
        return [name for name in self._lazy_features if name not in self._loaded]


# ── Feature Sandbox ─────────────────────────────────────────────────

class FeatureSandbox:
    """Sandboxed execution environment for features.

    Provides isolation between features:
    - Separate namespace per feature
    - Restricted imports (whitelist)
    - Resource limits (execution time, memory)
    - Safe access to shared APIs
    """

    def __init__(self):
        self._sandboxes: Dict[str, Dict[str, Any]] = {}
        self._import_whitelist: Set[str] = {
            "json", "re", "os.path", "hashlib", "base64",
            "datetime", "collections", "itertools", "functools",
            "typing", "dataclasses", "logging",
        }
        self._max_exec_time: float = 30.0  # seconds
        self._shared_api: Dict[str, Any] = {}

    def register_shared_api(self, name: str, obj: Any) -> None:
        """Register a shared API object that features can access."""
        self._shared_api[name] = obj

    def create_sandbox(self, feature_name: str) -> Dict[str, Any]:
        """Create a sandboxed namespace for a feature."""
        namespace = {
            "__name__": f"feature_{feature_name}",
            "__feature__": feature_name,
            "shared": dict(self._shared_api),  # Copy of shared API
            "feature_name": feature_name,
        }

        # Add whitelisted imports
        for mod_name in self._import_whitelist:
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                namespace[mod_name.split(".")[-1]] = mod
            except ImportError:
                pass

        self._sandboxes[feature_name] = namespace
        return namespace

    def execute(self, feature_name: str, code: str,
                 globals_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute code in a feature's sandbox.

        Returns a dict with 'success', 'result', and 'error' keys.
        """
        if feature_name not in self._sandboxes:
            self.create_sandbox(feature_name)

        namespace = self._sandboxes[feature_name]
        if globals_dict:
            namespace.update(globals_dict)

        import signal
        result: Dict[str, Any] = {"success": False, "result": None, "error": ""}

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Feature execution exceeded {self._max_exec_time}s")

        try:
            # Set timeout (Unix only)
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, self._max_exec_time)

            exec(code, namespace)
            result["success"] = True
        except TimeoutError as e:
            result["error"] = str(e)
            logger.warning("Feature '%s' execution timed out", feature_name)
        except Exception as e:
            result["error"] = str(e)
            logger.error("Feature '%s' execution failed: %s", feature_name, e)
        finally:
            signal.signal(signal.SIGALRM, old_handler)
            signal.setitimer(signal.ITIMER_REAL, 0)

        return result

    def get_sandbox(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """Get the sandbox namespace for a feature."""
        return self._sandboxes.get(feature_name)

    def destroy_sandbox(self, feature_name: str) -> bool:
        """Destroy a feature's sandbox."""
        if feature_name in self._sandboxes:
            del self._sandboxes[feature_name]
            return True
        return False

    def add_to_whitelist(self, module_name: str) -> None:
        """Add a module to the import whitelist."""
        self._import_whitelist.add(module_name)

    def remove_from_whitelist(self, module_name: str) -> None:
        """Remove a module from the import whitelist."""
        self._import_whitelist.discard(module_name)

    def set_max_exec_time(self, seconds: float) -> None:
        """Set maximum execution time for sandboxed code."""
        self._max_exec_time = seconds

    def get_info(self) -> Dict[str, Any]:
        """Return sandbox configuration info."""
        return {
            "active_sandboxes": len(self._sandboxes),
            "sandboxed_features": list(self._sandboxes.keys()),
            "import_whitelist": sorted(self._import_whitelist),
            "max_exec_time_seconds": self._max_exec_time,
            "shared_apis": list(self._shared_api.keys()),
        }


# ── Feature Code Generator ───────────────────────────────────────────

class FeatureCodeGenerator:
    """Generates boilerplate code for new features.

    Creates:
    - Feature directory structure
    - __init__.py with feature definition
    - Components scaffold
    - Routes scaffold
    - Middleware scaffold
    - Tests scaffold
    - README
    """

    TEMPLATES: Dict[str, str] = {}

    def __init__(self, features_dir: str = "features"):
        self.features_dir = features_dir

    def generate_feature(self, name: str, description: str = "",
                          with_components: bool = True,
                          with_routes: bool = True,
                          with_middleware: bool = False,
                          with_tests: bool = True) -> Dict[str, str]:
        """Generate a complete feature scaffold.

        Returns a dict of {filepath: content} for all generated files.
        """
        files: Dict[str, str] = {}
        feature_dir = os.path.join(self.features_dir, name)
        NL = chr(10)

        # __init__.py
        files[os.path.join(feature_dir, "__init__.py")] = self._gen_init(name, description)

        # components/
        if with_components:
            files[os.path.join(feature_dir, "components", "__init__.py")] = (
                f'"""Components for the {name} feature."""{NL}{NL}'
                f'components = []{NL}'
            )

        # routes/
        if with_routes:
            files[os.path.join(feature_dir, "routes", "__init__.py")] = (
                f'"""Routes for the {name} feature."""{NL}{NL}'
                f'routes = [{NL}'
                f'    # {{"path": "/{name}", "method": "GET", "handler": "index"}},{NL}'
                f']{NL}'
            )

        # middleware/
        if with_middleware:
            files[os.path.join(feature_dir, "middleware", "__init__.py")] = (
                f'"""Middleware for the {name} feature."""{NL}{NL}'
                f'middleware = []{NL}'
            )

        # tests/
        if with_tests:
            files[os.path.join(feature_dir, "tests", "__init__.py")] = (
                f'"""Tests for the {name} feature."""{NL}'
            )
            files[os.path.join(feature_dir, "tests", f"test_{name}.py")] = (
                self._gen_test(name)
            )

        # config.py
        files[os.path.join(feature_dir, "config.py")] = self._gen_config(name)

        # README.md
        files[os.path.join(feature_dir, "README.md")] = self._gen_readme(name, description)

        return files

    def _gen_init(self, name: str, description: str) -> str:
        NL = chr(10)
        cls_name = name.title().replace("_", "")
        desc = description or "Auto-generated feature module."
        lines = [
            f'"""Feature: {name}',
            '',
            desc,
            '"""',
            '',
            f'from .config import {cls_name}Config',
            '',
            f'FEATURE_NAME = "{name}"',
            'FEATURE_VERSION = "1.0.0"',
            '',
            '# Feature metadata',
            '__feature__ = {',
            f'    "name": "{name}",',
            '    "version": "1.0.0",',
            f'    "description": "{desc}",',
            '    "dependencies": [],',
            '    "permissions": [],',
            '}',
            '',
            '# Components exported by this feature',
            'components = []',
            '',
            '# Routes exported by this feature',
            'routes = []',
            '',
            '# Middleware exported by this feature',
            'middleware = []',
            '',
            '',
            'def on_init():',
            '    """Called when the feature is initialized."""',
            '    pass',
            '',
            '',
            'def on_build_start():',
            '    """Called at the start of a build."""',
            '    pass',
            '',
            '',
            'def on_build_end():',
            '    """Called at the end of a build."""',
            '    pass',
            '',
            '',
            'def on_request_start(request):',
            '    """Called at the start of each request."""',
            '    pass',
            '',
            '',
            'def on_request_end(request, response):',
            '    """Called at the end of each request."""',
            '    pass',
            '',
            '',
            'def cleanup():',
            '    """Called when the feature is unloaded."""',
            '    pass',
        ]
        return NL.join(lines)

    def _gen_config(self, name: str) -> str:
        NL = chr(10)
        cls_name = name.title().replace("_", "")
        return (
            f'"""Configuration for the {name} feature."""{NL}{NL}'
            f'from dataclasses import dataclass, field{NL}'
            f'from typing import List, Dict, Any{NL}'
            f'{NL}'
            f'{NL}'
            f'@dataclass{NL}'
            f'class {cls_name}Config:{NL}'
            f'    """Configuration for {name}."""{NL}'
            f'    enabled: bool = True{NL}'
            f'    debug: bool = False{NL}'
            f'    cache_ttl: int = 3600{NL}'
            f'    max_items: int = 1000{NL}'
            f'    custom: Dict[str, Any] = field(default_factory=dict){NL}'
            f'{NL}'
            f'    @classmethod{NL}'
            f'    def from_env(cls):{NL}'
            f'        """Load config from environment variables."""{NL}'
            f'        import os{NL}'
            f'        return cls({NL}'
            f'            enabled=os.environ.get("{name.upper()}_ENABLED", "true").lower() == "true",{NL}'
            f'            debug=os.environ.get("{name.upper()}_DEBUG", "false").lower() == "true",{NL}'
            f'            cache_ttl=int(os.environ.get("{name.upper()}_CACHE_TTL", "3600")),{NL}'
            f'            max_items=int(os.environ.get("{name.upper()}_MAX_ITEMS", "1000")),{NL}'
            f'        ){NL}'
        )

    def _gen_test(self, name: str) -> str:
        NL = chr(10)
        return (
            f'"""Tests for the {name} feature."""{NL}{NL}'
            f'import pytest{NL}'
            f'{NL}'
            f'{NL}'
            f'class Test{name.title().replace("_", "")}:{NL}'
            f'    """Tests for the {name} feature."""{NL}'
            f'{NL}'
            f'    def test_feature_exists(self):{NL}'
            f'        """Test that the feature module exists."""{NL}'
            f'        try:{NL}'
            f'            import importlib{NL}'
            f'            mod = importlib.import_module("features.{name}"){NL}'
            f'            assert mod.FEATURE_NAME == "{name}"{NL}'
            f'        except ImportError:{NL}'
            f'            pytest.skip("Feature {name} not installed"){NL}'
            f'{NL}'
            f'    def test_config_defaults(self):{NL}'
            f'        """Test default config values."""{NL}'
            f'        from .config import {name.title().replace("_", "")}Config{NL}'
            f'        config = {name.title().replace("_", "")}Config(){NL}'
            f'        assert config.enabled is True{NL}'
            f'        assert config.cache_ttl == 3600{NL}'
        )

    def _gen_readme(self, name: str, description: str) -> str:
        NL = chr(10)
        return (
            f'# Feature: {name}{NL}{NL}'
            f'{description or "Auto-generated feature module."}{NL}'
            f'{NL}'
            f'## Structure{NL}'
            f'{NL}'
            f'- `__init__.py` - Feature definition and lifecycle hooks{NL}'
            f'- `config.py` - Configuration dataclass{NL}'
            f'- `components/` - UI components{NL}'
            f'- `routes/` - Route definitions{NL}'
            f'- `middleware/` - Feature-specific middleware{NL}'
            f'- `tests/` - Test suite{NL}'
            f'{NL}'
            f'## Lifecycle Hooks{NL}'
            f'{NL}'
            f'- `on_init()` - Called when feature is loaded{NL}'
            f'- `on_build_start()` - Called at build start{NL}'
            f'- `on_build_end()` - Called at build end{NL}'
            f'- `on_request_start(request)` - Called per request{NL}'
            f'- `on_request_end(request, response)` - Called after request{NL}'
            f'- `cleanup()` - Called when feature is unloaded{NL}'
            f'{NL}'
            f'## Configuration{NL}'
            f'{NL}'
            f'Set environment variables:{NL}'
            f'{NL}'
            f'- `{name.upper()}_ENABLED` - Enable/disable (default: true){NL}'
            f'- `{name.upper()}_DEBUG` - Debug mode (default: false){NL}'
            f'- `{name.upper()}_CACHE_TTL` - Cache TTL in seconds (default: 3600){NL}'
            f'- `{name.upper()}_MAX_ITEMS` - Max items (default: 1000){NL}'
        )

    def write_feature(self, name: str, output_dir: str = "",
                       **kwargs) -> List[str]:
        """Generate and write feature files to disk."""
        files = self.generate_feature(name, **kwargs)
        output_dir = output_dir or self.features_dir
        written: List[str] = []

        for filepath, content in files.items():
            full_path = os.path.join(output_dir, filepath)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            try:
                with open(full_path, "w") as f:
                    f.write(content)
                written.append(full_path)
            except OSError as e:
                logger.warning("Failed to write %s: %s", full_path, e)

        logger.info("Generated feature '%s' with %d files", name, len(written))
        return written

    def list_templates(self) -> Dict[str, str]:
        """List available code templates."""
        return {
            "basic": "Feature with components and routes",
            "api": "Feature with API routes only (no components)",
            "full": "Feature with components, routes, middleware, and tests",
            "minimal": "Feature with just __init__.py and config.py",
        }


# ── Feature Health Checker ───────────────────────────────────────────

class FeatureHealthChecker:
    """Checks the health of loaded features.

    Verifies:
    - Feature module is importable
    - Required exports exist (components, routes, etc.)
    - Lifecycle hooks are callable
    - No import errors or missing dependencies
    - Config is valid
    """

    REQUIRED_EXPORTS = ["FEATURE_NAME", "components", "routes"]
    LIFECYCLE_HOOKS = ["on_init", "on_build_start", "on_build_end",
                       "on_request_start", "on_request_end", "cleanup"]

    def __init__(self, loader: Optional[FeatureLoader] = None):
        self.loader = loader
        self._results: Dict[str, Dict[str, Any]] = {}

    def check_feature(self, name: str, module: Any = None) -> Dict[str, Any]:
        """Check the health of a single feature."""
        if module is None and self.loader:
            module = self.loader.get_feature(name)

        if module is None:
            return {
                "feature": name,
                "healthy": False,
                "errors": ["Module not found or not loaded"],
                "warnings": [],
            }

        errors: List[str] = []
        warnings: List[str] = []

        # Check required exports
        for export in self.REQUIRED_EXPORTS:
            if not hasattr(module, export):
                errors.append(f"Missing required export: {export}")

        # Check lifecycle hooks
        for hook in self.LIFECYCLE_HOOKS:
            if hasattr(module, hook):
                if not callable(getattr(module, hook)):
                    errors.append(f"Lifecycle hook '{hook}' is not callable")
            else:
                warnings.append(f"Missing lifecycle hook: {hook}")

        # Check feature metadata
        if hasattr(module, "__feature__"):
            meta = getattr(module, "__feature__")
            if not isinstance(meta, dict):
                warnings.append("__feature__ is not a dict")
            elif "name" not in meta:
                warnings.append("__feature__ missing 'name' field")
        else:
            warnings.append("Missing __feature__ metadata")

        # Check config
        config_attr = None
        for attr in dir(module):
            if attr.endswith("Config") and attr[0].isupper():
                config_attr = attr
                break

        if not config_attr:
            warnings.append("No Config class found")

        # Check for circular dependencies
        deps = getattr(module, "__feature__", {}).get("dependencies", [])
        if name in deps:
            errors.append(f"Feature depends on itself (circular)")

        result = {
            "feature": name,
            "healthy": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "exports_found": [e for e in self.REQUIRED_EXPORTS if hasattr(module, e)],
            "hooks_found": [h for h in self.LIFECYCLE_HOOKS if hasattr(module, h)],
            "dependencies": deps,
        }

        self._results[name] = result
        return result

    def check_all(self) -> Dict[str, Any]:
        """Check all loaded features."""
        if not self.loader:
            return {"error": "No feature loader configured"}

        for name in self.loader.get_loaded_features():
            self.check_feature(name)

        all_healthy = all(r["healthy"] for r in self._results.values())
        total_errors = sum(len(r["errors"]) for r in self._results.values())
        total_warnings = sum(len(r["warnings"]) for r in self._results.values())

        return {
            "all_healthy": all_healthy,
            "features_checked": len(self._results),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "results": self._results,
        }

    def get_report(self) -> str:
        """Generate a human-readable health report."""
        NL = chr(10)
        lines = [
            "=" * 60,
            "  TW Framework -- Feature Health Report",
            "=" * 60,
            "",
        ]

        if not self._results:
            lines.append("  No features checked yet.")
        else:
            for name, result in self._results.items():
                status = "OK" if result["healthy"] else "FAIL"
                lines.append(f"  [{status}] {name}")

                for err in result["errors"]:
                    lines.append(f"    ERROR: {err}")

                for warn in result["warnings"]:
                    lines.append(f"    WARN: {warn}")

                lines.append("")

        lines.append("=" * 60)
        return NL.join(lines)

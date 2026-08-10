"""
TW React Compatibility Layer (v0.8.1)

Allows using React alongside TW Framework. React can be used as:
1. A client-side library for specific interactive components
2. An island of interactivity within TW's Zero-JS pages
3. A progressive enhancement alongside TW's native VDOM

Usage in .twm files:
  import React from "react"
  import { createRoot } from "react-dom/client"

  export client function MyComponent() {
    return React.createElement("div", null, "Hello from React")
  }

Usage in .tw pages:
  import { MyComponent } from "@/lib/react-component"

  page {
    title "React Demo"
    render interactive
  }

  body {
    div { id "react-root" }
  }

  script { on:load "MyComponent('react-root')" }

The TW build system will:
  - Bundle React from node_modules into a client chunk
  - Generate an import map for React resolution
  - Mount React components in TW-managed DOM nodes
  - Preserve TW's Zero-JS for static pages

This does NOT replace TW's native VDOM — it coexists.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Optional


# React client-side bootstrap script
REACT_BOOTSTRAP_JS = """// TW React Bootstrap (v0.8.1)
(function() {
  'use strict';
  window.__tw = window.__tw || {};
  __tw.react = {
    _roots: {},
    _components: {},

    register: function(name, component) {
      this._components[name] = component;
    },

    mount: function(name, targetId, props) {
      var target = document.getElementById(targetId);
      if (!target) {
        console.error('[TW React] Target element not found:', targetId);
        return;
      }
      var component = this._components[name];
      if (!component) {
        console.error('[TW React] Component not registered:', name);
        return;
      }
      // Defer React mounting to after React is loaded
      if (typeof __twReact === 'undefined') {
        this._pendingMounts = this._pendingMounts || [];
        this._pendingMounts.push({ name: name, targetId: targetId, props: props });
        return;
      }
      this._doMount(name, targetId, props);
    },

    _doMount: function(name, targetId, props) {
      var React = __twReact;
      var ReactDOM = __twReactDOM;
      var component = this._components[name];
      var target = document.getElementById(targetId);

      // Unmount existing root if present
      if (this._roots[targetId]) {
        try { this._roots[targetId].unmount(); } catch(e) {}
      }

      var root = ReactDOM.createRoot(target);
      this._roots[targetId] = root;
      root.render(React.createElement(component, props || {}));
    },

    unmount: function(targetId) {
      if (this._roots[targetId]) {
        try { this._roots[targetId].unmount(); } catch(e) {}
        delete this._roots[targetId];
      }
    },

    // Called after React/DOM libs are loaded
    _flushPending: function() {
      if (!this._pendingMounts) return;
      while (this._pendingMounts.length) {
        var mount = this._pendingMounts.shift();
        this._doMount(mount.name, mount.targetId, mount.props);
      }
    }
  };
})();
"""


# React CDN loaders (used when React not in node_modules)
REACT_CDN_SCRIPT = """<!-- TW React CDN Loader (v0.8.1) -->
<script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
<script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
<script>
window.__twReact = window.React;
window.__twReactDOM = window.ReactDOM;
if (window.__tw && window.__tw.react && window.__tw.react._flushPending) {
  window.__tw.react._flushPending();
}
</script>
"""


class ReactCompat:
    """Manages React integration with TW Framework."""

    def __init__(self, project_root: str = ""):
        self.project_root = project_root
        self._react_installed = None

    def is_react_installed(self) -> bool:
        """Check if React is installed in node_modules."""
        if self._react_installed is not None:
            return self._react_installed
        if not self.project_root:
            self._react_installed = False
            return False
        react_path = os.path.join(
            self.project_root, "node_modules", "react", "package.json"
        )
        react_dom_path = os.path.join(
            self.project_root, "node_modules", "react-dom", "package.json"
        )
        self._react_installed = (
            os.path.exists(react_path) and os.path.exists(react_dom_path)
        )
        return self._react_installed

    def get_react_version(self) -> Optional[str]:
        """Get installed React version."""
        if not self.is_react_installed():
            return None
        import json
        react_pkg = os.path.join(
            self.project_root, "node_modules", "react", "package.json"
        )
        try:
            with open(react_pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("version", "unknown")
        except (OSError, json.JSONDecodeError):
            return None

    def get_bootstrap_js(self) -> str:
        """Get the React bootstrap JS for client injection."""
        return REACT_BOOTSTRAP_JS

    def get_react_loader_script(self, use_cdn: bool = True) -> str:
        """
        Get script tags to load React — intelligent detection (v0.8.37).

        Priority:
        1. React installed in node_modules → ALWAYS bundle from node_modules.
           No CDN dependency. This is what Next.js does — you installed React,
           so we use YOUR React, not a CDN copy.

        2. React NOT installed → fall back to CDN (latest stable).
           This is the dev/quickstart path only. A warning is logged.

        The `use_cdn` config option is DEPRECATED — if React is installed,
        it is always bundled from node_modules regardless of this flag.
        CDN is only used as a last resort when React is not installed.
        """
        if self.is_react_installed():
            # React is installed — always bundle from node_modules.
            # This is the correct production behavior (like Next.js).
            # The build system (client_bundler.py) bundles React
            # from node_modules into /dist/js/react-bundle.js
            return (
                '<script src="/js/react-bundle.js"></script>\n'
                '<script>'
                'window.__twReact = window.React;'
                'window.__twReactDOM = window.ReactDOM;'
                'if (window.__tw && window.__tw.react && '
                'window.__tw.react._flushPending) {'
                'window.__tw.react._flushPending();'
                '}'
                '</script>'
            )
        else:
            # React NOT installed — fall back to CDN
            # This is a dev/quickstart fallback only
            import logging
            logging.getLogger("tw_framework").warning(
                "React is not installed in node_modules. "
                "Using CDN fallback. For production, install with: "
                "tw install react react-dom"
            )
            return REACT_CDN_SCRIPT

    def _cdn_script_for_version(self, version: str) -> str:
        """Generate CDN script tags for a specific React version."""
        # Extract major version for UMD path
        major = version.split(".")[0] if version else "18"
        return (
            f'<!-- TW React CDN Loader (react@{version}) -->\n'
            f'<script crossorigin src="https://unpkg.com/react@{version}/umd/react.production.min.js"></script>\n'
            f'<script crossorigin src="https://unpkg.com/react-dom@{version}/umd/react-dom.production.min.js"></script>\n'
            '<script>\n'
            'window.__twReact = window.React;\n'
            'window.__twReactDOM = window.ReactDOM;\n'
            'if (window.__tw && window.__tw.react && window.__tw.react._flushPending) {\n'
            '  window.__tw.react._flushPending();\n'
            '}\n'
            '</script>'
        )

    def detect_react_usage(self, source: str) -> bool:
        """Detect if a .tw or .twm source uses React."""
        indicators = [
            "import React",
            "from \"react\"",
            "from 'react'",
            "from \"react-dom\"",
            "from 'react-dom'",
            "React.createElement",
            "useState",
            "useEffect",
            "useRef",
            "useMemo",
            "useCallback",
        ]
        return any(ind in source for ind in indicators)

    def get_react_setup_hint(self) -> str:
        """Return setup instructions for React + TW."""
        return """
To use React with TW Framework:

1. Install React:
   tw install react react-dom

2. Create a React component in a .twm file:
   // [home]/lib/react-component.twm
   import React, { useState } from "react"
   import { createRoot } from "react-dom/client"

   export client function Counter() {
     const [count, setCount] = useState(0)
     return React.createElement("div", { className: "counter" },
       React.createElement("h2", null, "React Counter"),
       React.createElement("p", null, "Count: " + count),
       React.createElement("button", {
         onClick: () => setCount(count + 1)
       }, "Increment")
     )
   }

3. Use in your .tw page:
   import { Counter } from "@/lib/react-component"

   page {
     title "React Demo"
     render interactive
   }

   body {
     div { id "react-root" }
     script { on:load "__tw.react.mount('Counter', 'react-root')" }
   }

4. Build and deploy:
   tw build

TW will automatically:
  - Bundle React from node_modules
  - Generate import maps for ESM resolution
  - Mount React components in TW-managed DOM nodes
  - Preserve Zero-JS for static pages without React
"""


__all__ = ["ReactCompat", "REACT_BOOTSTRAP_JS", "REACT_CDN_SCRIPT"]

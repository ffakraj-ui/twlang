"""
TW Framework — CSR Mode (v0.9.08)

Client-Side Rendering mode — full React CSR.
When `render csr` is used, TW injects React + ReactDOM + bootstrap script.

Usage in .tw files:
  page {
    title "My App"
    render csr
  }

API:
  window.__twCSRRender = function(root, React, ReactDOM) { ... }
  window.__twCSRComponent = <React Component>
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

REACT_CDN_URL = "https://unpkg.com/react@18.3.1/umd/react.production.min.js"
REACT_DOM_CDN_URL = "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js"
REACT_DEV_CDN_URL = "https://unpkg.com/react@18.3.1/umd/react.development.js"
REACT_DOM_DEV_CDN_URL = "https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js"

CSR_BOOTSTRAP_JS = """
// TW CSR Bootstrap (v0.9.08)
(function() {
  'use strict';
  function waitForReact(callback) {
    if (typeof React !== 'undefined' && typeof ReactDOM !== 'undefined') {
      callback();
    } else {
      setTimeout(function() { waitForReact(callback); }, 50);
    }
  }
  waitForReact(function() {
    var rootElement = document.getElementById('root');
    if (!rootElement) {
      console.error('[TW CSR] No #root element found. Add <div id="root"></div> to your page.');
      return;
    }
    if (typeof window.__twCSRRender === 'function') {
      var root = ReactDOM.createRoot(rootElement);
      window.__twCSRRender(root, React, ReactDOM);
      console.log('[TW CSR] App mounted via __twCSRRender');
    } else if (typeof window.__twCSRComponent !== 'undefined') {
      var Component = window.__twCSRComponent;
      var root = ReactDOM.createRoot(rootElement);
      root.render(React.createElement(Component));
      console.log('[TW CSR] App mounted via __twCSRComponent');
    } else {
      console.warn('[TW CSR] No render function found. Define window.__twCSRRender or window.__twCSRComponent.');
    }
  });
})();
"""


def inject_csr_runtime(html_doc: str, use_dev: bool = False, use_cdn: bool = True) -> str:
    """Inject CSR runtime into HTML document."""
    if 'id="root"' not in html_doc and "id='root'" not in html_doc:
        html_doc = html_doc.replace("</body>", '<div id="root"></div>\n</body>', 1)

    scripts = []
    if use_cdn:
        react_url = REACT_DEV_CDN_URL if use_dev else REACT_CDN_URL
        react_dom_url = REACT_DOM_DEV_CDN_URL if use_dev else REACT_DOM_CDN_URL
        scripts.append('<script crossorigin src="' + react_url + '"></script>')
        scripts.append('<script crossorigin src="' + react_dom_url + '"></script>')
    else:
        # v0.9.08 FIX: Use bundled React from node_modules
        import os as _os
        nm_react = _os.path.join(_os.getcwd(), "node_modules", "react", "umd", "react.production.min.js")
        nm_dom = _os.path.join(_os.getcwd(), "node_modules", "react-dom", "umd", "react-dom.production.min.js")
        if _os.path.exists(nm_react) and _os.path.exists(nm_dom):
            scripts.append('<script src="/_tw/static/react.production.min.js"></script>')
            scripts.append('<script src="/_tw/static/react-dom.production.min.js"></script>')
        else:
            # Fallback to CDN if bundle not available
            scripts.append('<script crossorigin src="' + REACT_CDN_URL + '"></script>')
            scripts.append('<script crossorigin src="' + REACT_DOM_CDN_URL + '"></script>')

    scripts.append('<script>\n' + CSR_BOOTSTRAP_JS + '\n</script>')

    injection = "\n".join(scripts)
    if "</body>" in html_doc:
        html_doc = html_doc.replace("</body>", injection + "\n</body>", 1)
    else:
        html_doc = html_doc + injection

    html_doc = html_doc.replace("<html", '<html data-tw-render="csr"', 1)
    return html_doc


def get_csr_bootstrap_js() -> str:
    return CSR_BOOTSTRAP_JS


def is_csr_page(page) -> bool:
    return getattr(page, "render_mode", "") == "csr"


def get_csr_info() -> dict:
    return {
        "mode": "csr",
        "description": "Client-Side Rendering with React",
        "react_version": "18.3.1",
        "mount_point": "#root",
        "api": {
            "window.__twCSRRender": "function(root, React, ReactDOM) — custom render",
            "window.__twCSRComponent": "React component to mount",
        },
    }


# ── next/dynamic CSR Support (#5) ────────────────────────────────────


class DynamicImport:
    """Represents a dynamic import (next/dynamic equivalent).

    Wraps a component import so it only loads on the client side,
    skipping SSR entirely. Server sends a loading placeholder,
    client replaces it after loading the component.
    """

    def __init__(self, loader_fn, loading=None, ssr=False):
        self.loader = loader_fn
        self.loading = loading or "Loading..."
        self.ssr = ssr
        self._component = None
        self._loaded = False

    def load(self):
        if not self._loaded:
            self._component = self.loader()
            self._loaded = True
        return self._component

    def render_ssr(self):
        if self.ssr:
            comp = self.load()
            return comp() if callable(comp) else str(comp)
        return '<div class="tw-dynamic-loading">' + self.loading + '</div>'

    def render_client_script(self, mount_id):
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var mount = document.getElementById("' + mount_id + '");',
            '  if (!mount) return;',
            '  mount.innerHTML = "' + self.loading + '";',
            '  window.__tw_dynamic__ = window.__tw_dynamic__ || {};',
            '  window.__tw_dynamic__["' + mount_id + '"] = function(comp) {',
            '    mount.innerHTML = comp.render({});',
            '    mount.setAttribute("data-tw-loaded", "true");',
            '  };',
            '})();',
            '</script>',
        ]
        return NL.join(lines)


def dynamic(loader, loading=None, ssr=False):
    """Create a dynamic import (next/dynamic equivalent)."""
    return DynamicImport(loader, loading=loading, ssr=ssr)


def generate_csr_bootstrap(mount_id="#root", component_path=""):
    """Generate the CSR bootstrap script."""
    NL = chr(10)
    lines = [
        '<script>',
        '(function() {',
        '  var mountId = "' + mount_id + '";',
        '  var componentPath = "' + component_path + '";',
        '  function mount() {',
        '    var mount = document.querySelector(mountId);',
        '    if (!mount) { console.error("[CSR] Mount point not found"); return; }',
        '    mount.innerHTML = "<div class=\\"tw-csr-loading\\">Loading...</div>";',
        '    if (window.__tw_bundles__ && window.__tw_bundles__[componentPath]) {',
        '      var Component = window.__tw_bundles__[componentPath];',
        '      try {',
        '        mount.innerHTML = Component.render({});',
        '        mount.setAttribute("data-tw-mounted", "true");',
        '      } catch(e) { console.error("[CSR] Render failed:", e); }',
        '    } else {',
        '      var script = document.createElement("script");',
        '      script.src = "/_bundles/" + componentPath + ".js";',
        '      script.onload = function() {',
        '        if (window.__tw_bundles__ && window.__tw_bundles__[componentPath]) {',
        '          mount.innerHTML = window.__tw_bundles__[componentPath].render({});',
        '          mount.setAttribute("data-tw-mounted", "true");',
        '        }',
        '      };',
        '      document.head.appendChild(script);',
        '    }',
        '  }',
        '  if (document.readyState === "loading") {',
        '    document.addEventListener("DOMContentLoaded", mount);',
        '  } else { mount(); }',
        '})();',
        '</script>',
    ]
    return NL.join(lines)


class CSRBoundary:
    """Marks a component boundary for CSR-only rendering."""

    def __init__(self, component_name, loading=None):
        self.component_name = component_name
        self.loading = loading or "Loading..."
        self._mount_id = "tw-csr-" + component_name

    def render_placeholder(self):
        return (
            '<div id="' + self._mount_id + '" class="tw-csr-boundary">'
            '<div class="tw-csr-loading">' + self.loading + '</div>'
            '</div>'
        )

    def render_hydration_script(self, bundle_url):
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  var mount = document.getElementById("' + self._mount_id + '");',
            '  if (!mount) return;',
            '  var script = document.createElement("script");',
            '  script.src = "' + bundle_url + '";',
            '  script.onload = function() {',
            '    var comp = window.__tw_bundles__ && window.__tw_bundles__["' + self.component_name + '"];',
            '    if (comp) { mount.innerHTML = comp.render({}); mount.setAttribute("data-tw-loaded", "true"); }',
            '  };',
            '  document.head.appendChild(script);',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

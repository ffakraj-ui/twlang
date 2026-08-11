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

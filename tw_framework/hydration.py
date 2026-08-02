"""
Partial hydration / islands architecture for TW Framework.

Interactive components are wrapped with data attributes and a small runtime
that hydrates only those components, leaving static HTML untouched.
"""

import html
import json
import logging
from typing import Dict, List, Optional

from .ir import IRComponent, IRElement, IRProgram
from .runtime_values import RuntimeEnvironment

logger = logging.getLogger(__name__)


def _is_interactive(node) -> bool:
    """Check if a node has interactive attributes (events, router, or lazy component)."""
    if isinstance(node, IRElement):
        if node.events or node.router:
            return True
        for child in node.children:
            if _is_interactive(child):
                return True
    if isinstance(node, IRComponent):
        for prop in node.props:
            if prop.get("name") == "lazy" and prop.get("value") in (True, "true"):
                return True
        for child in node.children:
            if _is_interactive(child):
                return True
    return False


def _collect_interactive_nodes(node, path: str, interactive: List[Dict]):
    """Recursively collect interactive nodes with their paths."""
    if isinstance(node, IRElement):
        if node.events or node.router:
            interactive.append({
                "path": path,
                "tag": node.tag,
                "events": [{"name": e["name"], "value": e["value"]} for e in node.events],
                "router": dict(node.router),
            })
        for i, child in enumerate(node.children):
            _collect_interactive_nodes(child, f"{path}.children[{i}]", interactive)
    if isinstance(node, IRComponent):
        for prop in node.props:
            if prop.get("name") == "lazy" and prop.get("value") in (True, "true"):
                interactive.append({
                    "path": path,
                    "tag": f"component:{node.name}",
                    "lazy": True,
                })
        for i, child in enumerate(node.children):
            _collect_interactive_nodes(child, f"{path}.children[{i}]", interactive)


def wrap_interactive_nodes(html: str, program: IRProgram, context: Optional[Dict] = None) -> str:
    """Wrap interactive nodes with data-tw-hydrate attributes and inject hydration script."""
    interactive = []
    for i, node in enumerate(program.body):
        _collect_interactive_nodes(node, f"body[{i}]", interactive)
    if not interactive:
        return html

    # Inject data attributes
    for item in interactive:
        path = item["path"]
        tag = item["tag"]
        if item.get("lazy"):
            html = html.replace(
                f"<{tag}",
                f'<{tag} data-tw-hydrate="lazy" data-tw-path="{html.escape(path, quote=True)}"',
                1,
            )
        else:
            html = html.replace(
                f"<{tag}",
                f'<{tag} data-tw-hydrate="interactive" data-tw-path="{html.escape(path, quote=True)}"',
                1,
            )

    # Inject hydration runtime
    runtime_js = """
(function() {
  var hydratable = document.querySelectorAll('[data-tw-hydrate]');
  if (!hydratable.length) return;
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        var el = entry.target;
        var type = el.getAttribute('data-tw-hydrate');
        if (type === 'lazy') {
          // Lazy component: load chunk and hydrate
          var path = el.getAttribute('data-tw-path');
          import('/_tw/chunks/' + path + '.js').then(function(mod) {
            if (mod.hydrate) mod.hydrate(el);
          }).catch(function(err) {
            console.warn('TW hydration failed for', path, err);
          });
        } else {
          // Interactive element: attach events
          var events = JSON.parse(el.getAttribute('data-tw-events') || '[]');
          events.forEach(function(ev) {
            el.addEventListener(ev.name, function(event) {
              try {
                var fn = new Function('event', ev.value);
                fn(event);
              } catch(e) {
                console.warn('TW event handler error', e);
              }
            });
          });
        }
        observer.unobserve(el);
      }
    });
  }, { rootMargin: '200px' });
  hydratable.forEach(function(el) { observer.observe(el); });
})();
"""
    html = html.replace("</body>", f"<script>{runtime_js}</script></body>", 1)
    return html


__all__ = ["wrap_interactive_nodes", "_is_interactive"]

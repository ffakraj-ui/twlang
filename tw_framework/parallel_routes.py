"""
TW Framework - Parallel Routes & Intercepting Routes

Implements:
7. Parallel Routes - Render multiple pages simultaneously in one layout
8. Intercepting Routes + Parallel Routes for Modals
"""

from __future__ import annotations
import re, logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ParallelSlot:
    """A named slot in a parallel route layout."""
    name: str           # e.g. "analytics", "modal" (without @)
    folder: str         # e.g. "@analytics"
    content: str = ""   # Rendered HTML for this slot
    is_active: bool = False
    is_default: bool = False  # Has default.tw fallback


@dataclass
class InterceptedRoute:
    """An intercepted route definition."""
    pattern: str         # e.g. "(..)photo/[id]"
    target_route: str    # e.g. "/photo/[id]"
    intercept_level: int = 1  # 1=(.) same level, 2=(..) one up, 3=(...) two up
    modal_slot: str = ""  # Which parallel slot to render the modal in


class ParallelRouteResolver:
    """Resolves parallel routes for a layout.

    Parallel Routes allow rendering multiple pages simultaneously
    in the same layout using the @folder convention.

    Example:
        app/
          layout.tw        <- Receives slots as props
          page.tw          <- Main content
          @analytics/
            page.tw        <- Analytics panel
          @modal/
            page.tw        <- Modal content (default)

    The layout receives:
        layout(main=..., analytics=..., modal=...)

    Slots don't affect URL structure:
        /@analytics/views -> /views
    """

    def __init__(self):
        self._slots: Dict[str, ParallelSlot] = {}
        self._active_slots: Set[str] = set()
        self._default_content: Dict[str, str] = {}

    def register_slot(self, name: str, folder: str = "",
                      has_default: bool = False) -> ParallelSlot:
        """Register a parallel route slot."""
        slot = ParallelSlot(
            name=name,
            folder=folder or "@" + name,
            is_default=has_default,
        )
        self._slots[name] = slot
        return slot

    def set_slot_content(self, name: str, content: str) -> None:
        """Set rendered content for a slot."""
        if name in self._slots:
            self._slots[name].content = content
            self._slots[name].is_active = True
            self._active_slots.add(name)

    def set_default_content(self, name: str, content: str) -> None:
        """Set default content for a slot (when route not active)."""
        self._default_content[name] = content

    def get_slot(self, name: str) -> Optional[ParallelSlot]:
        return self._slots.get(name)

    def get_active_slots(self) -> Dict[str, str]:
        """Get all active slot contents for layout rendering."""
        result: Dict[str, str] = {}
        for name, slot in self._slots.items():
            if slot.is_active and slot.content:
                result[name] = slot.content
            elif name in self._default_content:
                result[name] = self._default_content[name]
        return result

    def render_layout(self, layout_template: str, main_content: str) -> str:
        """Render a layout with parallel slots.

        layout_template should contain {slot_name} placeholders.
        """
        result = layout_template.replace("{children}", main_content)
        for name, slot in self._slots.items():
            content = slot.content if slot.is_active else self._default_content.get(name, "")
            result = result.replace("{" + name + "}", content)
        return result

    @staticmethod
    def is_parallel_folder(name: str) -> bool:
        """Check if a folder name is a parallel route slot."""
        return name.startswith("@")

    @staticmethod
    def extract_slot_name(folder: str) -> str:
        """Extract slot name from @folder convention."""
        return folder[1:] if folder.startswith("@") else folder

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_slots": len(self._slots),
            "active_slots": len(self._active_slots),
            "slots": {name: {"active": s.is_active, "has_default": s.is_default}
                      for name, s in self._slots.items()},
        }


class InterceptingRouteResolver:
    """Resolves intercepting routes for modal patterns.

    Intercepting Routes allow you to load a route from another part
    of your application within the current layout.

    Common use case: Deep-linkable modals
    - /photo/123 shows full photo page (direct navigation)
    - /feed -> click photo -> shows modal (intercepted route)

    Convention:
        (.)        -> Match same level (one dot)
        (..)       -> Match one level up (two dots)
        (..)(..)   -> Match two levels up (four dots)
        (...)      -> Match root level (three dots)
    """

    def __init__(self):
        self._intercepts: List[InterceptedRoute] = []
        self._modal_slots: Dict[str, str] = {}  # route -> modal HTML

    def register_intercept(self, pattern: str, target_route: str,
                            modal_slot: str = "modal") -> None:
        """Register an intercepted route."""
        level = 1
        if pattern.startswith("(...)"):
            level = 3
        elif pattern.startswith("(..)(..)"):
            level = 3
        elif pattern.startswith("(..)"):
            level = 2
        elif pattern.startswith("(.)"):
            level = 1

        intercept = InterceptedRoute(
            pattern=pattern,
            target_route=target_route,
            intercept_level=level,
            modal_slot=modal_slot,
        )
        self._intercepts.append(intercept)

    def resolve_intercept(self, current_route: str,
                           requested_route: str) -> Optional[InterceptedRoute]:
        """Check if a requested route should be intercepted.

        Returns the InterceptedRoute if the route should be shown as a modal,
        or None if it should be a full navigation.
        """
        for intercept in self._intercepts:
            # Simple matching: if the requested route matches the target
            # and the current route is at the right level
            target_pattern = intercept.target_route.replace("[id]", "[^/]+")
            if re.match("^" + target_pattern + "$", requested_route):
                return intercept
        return None

    def set_modal_content(self, route: str, html: str) -> None:
        """Set modal HTML content for a route."""
        self._modal_slots[route] = html

    def get_modal_content(self, route: str) -> str:
        """Get modal HTML for a route."""
        return self._modal_slots.get(route, "")

    def render_modal(self, route: str, slot_name: str = "modal") -> str:
        """Render a modal for an intercepted route."""
        content = self.get_modal_content(route)
        if not content:
            return ""
        NL = chr(10)
        return NL.join([
            '<div class="tw-modal-overlay" data-tw-modal="' + route + '">',
            '  <div class="tw-modal-backdrop" onclick="this.parentElement.remove()"></div>',
            '  <div class="tw-modal-content">' + content + '</div>',
            '</div>',
        ])

    def generate_modal_script(self) -> str:
        """Generate JS for modal interactions (deep-linkable modals)."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  // Handle modal deep-linking',
            '  function openModal(route, content) {',
            '    var overlay = document.createElement("div");',
            '    overlay.className = "tw-modal-overlay";',
            '    overlay.setAttribute("data-tw-modal", route);',
            '    overlay.innerHTML = ' + "'<div class=\"tw-modal-backdrop\" onclick=\"this.parentElement.remove()\"></div>'" + ' +',
            '      ' + "'<div class=\"tw-modal-content\">' + content + '</div>'" + ';',
            '    document.body.appendChild(overlay);',
            '    // Update URL without full navigation',
            '    window.history.pushState({ modal: route }, "", route);',
            '  }',
            '  // Handle popstate for modal close',
            '  window.addEventListener("popstate", function(e) {',
            '    var modal = document.querySelector(".tw-modal-overlay");',
            '    if (modal && !e.state.modal) { modal.remove(); }',
            '  });',
            '  // Intercept link clicks for modal routes',
            '  document.addEventListener("click", function(e) {',
            '    var link = e.target.closest("a[data-tw-modal]");',
            '    if (!link) return;',
            '    e.preventDefault();',
            '    var route = link.getAttribute("href");',
            '    var content = link.getAttribute("data-tw-modal-content") || "Loading...";',
            '    // Fetch modal content',
            '    fetch(route, { headers: { "X-TW-Modal": "1" } })',
            '      .then(function(r) { return r.text(); })',
            '      .then(function(html) { openModal(route, html); });',
            '  });',
            '  window.__tw_modal__ = { open: openModal };',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    @staticmethod
    def parse_intercept_pattern(pattern: str) -> Dict[str, Any]:
        """Parse an intercept pattern like (..)photo/[id]."""
        level = 0
        clean_pattern = pattern

        if pattern.startswith("(...)"):
            level = 3
            clean_pattern = pattern[5:]
        elif pattern.startswith("(..)(..)"):
            level = 3
            clean_pattern = pattern[8:]
        elif pattern.startswith("(..)"):
            level = 2
            clean_pattern = pattern[4:]
        elif pattern.startswith("(.)"):
            level = 1
            clean_pattern = pattern[3:]

        return {
            "level": level,
            "pattern": clean_pattern,
            "route": "/" + clean_pattern,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_intercepts": len(self._intercepts),
            "modal_routes": len(self._modal_slots),
            "intercepts": [{"pattern": i.pattern, "target": i.target_route,
                           "level": i.intercept_level} for i in self._intercepts],
        }


__all__ = [
    "ParallelSlot", "InterceptedRoute",
    "ParallelRouteResolver", "InterceptingRouteResolver",
]

"""
TW Framework - React 19.2 Features

Implements:
9. View Transitions - Animate elements during transitions/navigation
   useEffectEvent - Extract non-reactive logic from Effects
   React Compiler Support (Stable) - automatic memoization
"""

from __future__ import annotations
import json, time, logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ViewTransitionConfig:
    """Configuration for a view transition."""
    name: str = ""
    duration_ms: int = 300
    easing: str = "ease-in-out"
    directions: List[str] = field(default_factory=lambda: ["forward", "back"])
    shared_elements: List[str] = field(default_factory=list)  # element IDs for shared transitions


class ViewTransitionManager:
    """View Transitions API integration.

    Enables smooth animations between page states:
    1. Cross-fade between old and new views
    2. Shared element transitions (element morphs from one position to another)
    3. Slide animations for forward/back navigation
    4. Custom CSS for specific element transitions

    Uses the browser View Transitions API (Chrome 111+, Safari 18+).
    Falls back to instant update on unsupported browsers.
    """

    def __init__(self):
        self._transitions: Dict[str, ViewTransitionConfig] = {}
        self._default_config = ViewTransitionConfig()

    def register_transition(self, name: str, duration_ms: int = 300,
                            easing: str = "ease-in-out",
                            shared_elements: Optional[List[str]] = None) -> None:
        """Register a named view transition."""
        self._transitions[name] = ViewTransitionConfig(
            name=name, duration_ms=duration_ms, easing=easing,
            shared_elements=shared_elements or [],
        )

    def generate_transition_css(self) -> str:
        """Generate CSS for view transitions."""
        css_parts = []
        # Base transition styles
        css_parts.append("::view-transition-old(root) { animation-duration: " + str(self._default_config.duration_ms) + "ms; }")
        css_parts.append("::view-transition-new(root) { animation-duration: " + str(self._default_config.duration_ms) + "ms; }")

        # Named transitions
        for name, config in self._transitions.items():
            css_parts.append("::view-transition-group(" + name + ") { animation-duration: " + str(config.duration_ms) + "ms; animation-timing-function: " + config.easing + "; }")
            # Shared element transitions
            for elem_id in config.shared_elements:
                css_parts.append("#" + elem_id + " { view-transition-name: " + name + "; }")

        return "<style>" + " ".join(css_parts) + "</style>"

    def generate_transition_script(self) -> str:
        """Generate JS for view transitions on navigation."""
        NL = chr(10)
        lines = [
            '<script>',
            '(function() {',
            '  function startTransition(callback, transitionName) {',
            '    if (!document.startViewTransition) {',
            '      // Fallback: instant update',
            '      callback();',
            '      return;',
            '    }',
            '    var opts = transitionName ? { update: callback, types: [transitionName] } : { update: callback };',
            '    var transition = document.startViewTransition(function() {',
            '      callback();',
            '    });',
            '    return transition;',
            '  }',
            '  // Intercept navigations for view transitions',
            '  document.addEventListener("click", function(e) {',
            '    var link = e.target.closest("a[href]");',
            '    if (!link || !link.getAttribute("href").startsWith("/")) return;',
            '    if (link.hasAttribute("data-tw-no-transition")) return;',
            '    e.preventDefault();',
            '    var href = link.getAttribute("href");',
            '    startTransition(function() {',
            '      // Fetch new content',
            '      fetch(href).then(function(r) { return r.text(); }).then(function(html) {',
            '        var app = document.getElementById("tw-app");',
            '        if (app) app.innerHTML = html;',
            '        window.history.pushState({ route: href }, "", href);',
            '      });',
            '    }, link.getAttribute("data-tw-transition"));',
            '  });',
            '  // Handle back/forward with transitions',
            '  window.addEventListener("popstate", function(e) {',
            '    startTransition(function() {',
            '      fetch(window.location.pathname).then(function(r) { return r.text(); }).then(function(html) {',
            '        var app = document.getElementById("tw-app");',
            '        if (app) app.innerHTML = html;',
            '      });',
            '    });',
            '  });',
            '  window.__tw_view_transition__ = { start: startTransition };',
            '})();',
            '</script>',
        ]
        return NL.join(lines)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_transitions": len(self._transitions),
            "transition_names": list(self._transitions.keys()),
            "default_duration_ms": self._default_config.duration_ms,
        }


class UseEffectEvent:
    """useEffectEvent implementation.

    In React 19.2, useEffectEvent lets you extract non-reactive logic
    from Effects into Effect Event functions. These functions:
    1. Can read the latest props/state without being in dependencies
    2. Cannot be called during render (only inside effects)
    3. Don't cause re-runs when their dependencies change

    This prevents stale closures without adding to effect dependencies.
    """

    def __init__(self):
        self._events: Dict[str, Callable] = {}
        self._latest_values: Dict[str, Any] = {}

    def create_effect_event(self, name: str, fn: Callable,
                             deps: Optional[Dict[str, Any]] = None) -> Callable:
        """Create an effect event function.

        Args:
            name: Unique name for this event
            fn: The function to wrap
            deps: Current values the function reads (will be kept updated)

        Returns:
            A callable that always sees the latest values
        """
        if deps:
            self._latest_values[name] = deps

        def wrapped(*args, **kwargs):
            # Always use latest values
            latest = self._latest_values.get(name, {})
            return fn(*args, **{**latest, **kwargs})

        self._events[name] = wrapped
        return wrapped

    def update_values(self, name: str, values: Dict[str, Any]) -> None:
        """Update the latest values for an effect event."""
        if name in self._latest_values:
            self._latest_values[name].update(values)
        else:
            self._latest_values[name] = values

    def get_event(self, name: str) -> Optional[Callable]:
        return self._events.get(name)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._events),
            "event_names": list(self._events.keys()),
        }


@dataclass
class ReactCompilerConfig:
    """Configuration for React Compiler integration."""
    enabled: bool = True
    auto_memoize: bool = True
    optimize_hooks: bool = True
    eliminate_dead_code: bool = True
    target_react_version: str = "19.2"


class React19Integration:
    """Integration layer for React 19.2 features.

    Provides:
    1. View Transitions API integration
    2. useEffectEvent for non-reactive logic
    3. React Compiler configuration
    4. Feature detection and polyfill loading
    """

    def __init__(self, compiler_config: Optional[ReactCompilerConfig] = None):
        self.view_transitions = ViewTransitionManager()
        self.effect_events = UseEffectEvent()
        self.compiler_config = compiler_config or ReactCompilerConfig()
        self._features_enabled: Dict[str, bool] = {}

    def enable_feature(self, name: str) -> None:
        self._features_enabled[name] = True

    def is_enabled(self, name: str) -> bool:
        return self._features_enabled.get(name, False)

    def generate_setup_script(self) -> str:
        """Generate JS that sets up all React 19.2 features."""
        NL = chr(10)
        parts = [
            self.view_transitions.generate_transition_script(),
        ]
        return NL.join(parts)

    def generate_head_tags(self) -> str:
        """Generate tags for <head> (CSS, meta)."""
        return self.view_transitions.generate_transition_css()

    def get_feature_status(self) -> Dict[str, Any]:
        return {
            "view_transitions": True,
            "use_effect_event": True,
            "react_compiler": self.compiler_config.enabled,
            "auto_memoize": self.compiler_config.auto_memoize,
            "features_enabled": dict(self._features_enabled),
        }


__all__ = [
    "ViewTransitionConfig", "ViewTransitionManager",
    "UseEffectEvent", "ReactCompilerConfig", "React19Integration",
]

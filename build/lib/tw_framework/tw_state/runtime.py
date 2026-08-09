"""
Client-side runtime JS generation for tw/state.

Generates the reactive store runtime that gets injected into pages
that use tw/state. Pages that don't use tw/state get zero state JS.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


_STATE_RUNTIME_JS = """// TW State Runtime — reactive global stores
(function(){
'use strict';
window.__tw = window.__tw || {};
var __stores = {};
var __derived = {};

__tw.store = function(initialState) {
  var id = 's' + Math.random().toString(36).slice(2, 9);
  var state = Object.assign({}, initialState);
  var subscribers = [];
  function notify() {
    subscribers.forEach(function(fn) { try { fn(state); } catch(e){} });
  }
  var store = {
    _id: id,
    get: function() { return Object.assign({}, state); },
    set: function(newState) {
      if (typeof newState === 'function') newState = newState(state);
      Object.assign(state, newState);
      notify();
    },
    update: function(fn) { state = fn(state); notify(); },
    subscribe: function(fn) {
      subscribers.push(fn);
      return function() {
        var idx = subscribers.indexOf(fn);
        if (idx > -1) subscribers.splice(idx, 1);
      };
    },
    reset: function() { state = Object.assign({}, initialState); notify(); }
  };
  __stores[id] = store;
  return store;
};

__tw.derived = function(deps, compute) {
  var cached = null;
  var dirty = true;
  var subs = [];
  function recompute() {
    var depValues = deps.map(function(d) { return d.get(); });
    cached = compute.apply(null, depValues);
    dirty = false;
    subs.forEach(function(fn) { try { fn(cached); } catch(e){} });
  }
  deps.forEach(function(d) {
    d.subscribe(function() { dirty = true; recompute(); });
  });
  return {
    get: function() { if (dirty) recompute(); return cached; },
    subscribe: function(fn) { subs.push(fn); return function(){ subs.splice(subs.indexOf(fn),1); }; }
  };
};

__tw.state = __stores;

// Persistence (optional)
__tw.persist = function(store, key) {
  try {
    var saved = localStorage.getItem(key);
    if (saved) store.set(JSON.parse(saved));
    store.subscribe(function(state) {
      try { localStorage.setItem(key, JSON.stringify(state)); } catch(e){}
    });
  } catch(e) {}
};
})();"""


def get_state_runtime_js() -> str:
    """Return the state runtime JS."""
    return _STATE_RUNTIME_JS


def generate_state_init_script(stores_config: List[Dict[str, Any]]) -> str:
    """Generate initialization script for client-side stores."""
    if not stores_config:
        return ""
    parts = []
    for config in stores_config:
        name = config.get("name", "")
        initial = config.get("initialState", {})
        persist = config.get("persist", False)
        js = f"var {name} = __tw.store({json.dumps(initial, ensure_ascii=False)});"
        if persist:
            js += f"\n__tw.persist({name}, 'tw_state_{name}');"
        parts.append(js)
    return "\n".join(parts)


__all__ = ["get_state_runtime_js", "generate_state_init_script"]

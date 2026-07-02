"""
TW Client Reactivity System
Generates a lightweight JS runtime injected into pages that use:
  - state { ... }       -> reactive variables
  - bind:value          -> two-way input binding
  - on:click / on:input -> event handlers
  - show:condition      -> conditional display
  - tw-for / tw-each    -> client-side list rendering (from JSON endpoint or inline array)
  - tw-ref              -> DOM refs

This module:
1. Parses .tw page/component nodes and detects reactivity usage
2. Emits a minimal vanilla-JS runtime (~2KB gzipped) per page
3. Hooks into the compiler's render pipeline via page-level `script {}` injection

No framework deps. No virtual DOM. Direct DOM updates.
"""

import json
import re
from typing import List, Optional

# ─── Runtime JS (injected once per page that uses reactivity) ─────────────────

_TW_REACTIVE_RUNTIME = r"""
(function() {
'use strict';

// ── State store ──────────────────────────────────────────────────────────────
var __twState = {};
var __twWatchers = {};
var __twRefs = {};

function __twDefineState(initialState) {
  Object.keys(initialState).forEach(function(key) {
    __twState[key] = initialState[key];
  });
  __twSync();
}

function __twSet(key, value) {
  if (__twState[key] === value) return;
  __twState[key] = value;
  (__twWatchers[key] || []).forEach(function(fn) { try { fn(value); } catch(e){} });
  __twSync();
}

function __twGet(key) {
  return __twState[key];
}

function __twWatch(key, fn) {
  if (!__twWatchers[key]) __twWatchers[key] = [];
  __twWatchers[key].push(fn);
}

// ── DOM sync ──────────────────────────────────────────────────────────────────
function __twSync() {
  // bind:value — sync input values
  document.querySelectorAll('[data-tw-bind]').forEach(function(el) {
    var key = el.getAttribute('data-tw-bind');
    if (el !== document.activeElement && key in __twState) {
      if (el.type === 'checkbox') {
        el.checked = !!__twState[key];
      } else {
        el.value = __twState[key] !== null && __twState[key] !== undefined ? __twState[key] : '';
      }
    }
  });

  // show: — toggle visibility
  document.querySelectorAll('[data-tw-show]').forEach(function(el) {
    var expr = el.getAttribute('data-tw-show');
    var val = __twEval(expr);
    el.style.display = val ? '' : 'none';
  });

  // tw-text — update text content
  document.querySelectorAll('[data-tw-text]').forEach(function(el) {
    var expr = el.getAttribute('data-tw-text');
    var val = __twEval(expr);
    el.textContent = val !== null && val !== undefined ? String(val) : '';
  });

  // tw-html — update inner HTML (escaped)
  document.querySelectorAll('[data-tw-html]').forEach(function(el) {
    var expr = el.getAttribute('data-tw-html');
    var val = __twEval(expr);
    el.innerHTML = val !== null && val !== undefined ? String(val) : '';
  });

  // class: — conditional class
  document.querySelectorAll('[data-tw-class]').forEach(function(el) {
    try {
      var pairs = JSON.parse(el.getAttribute('data-tw-class'));
      Object.keys(pairs).forEach(function(cls) {
        el.classList.toggle(cls, !!__twEval(pairs[cls]));
      });
    } catch(e) {}
  });

  // tw-for — client-side list rendering
  document.querySelectorAll('[data-tw-for]').forEach(function(container) {
    var expr = container.getAttribute('data-tw-for');
    var tmpl = container.querySelector('[data-tw-for-template]');
    if (!tmpl) return;
    var items = __twEval(expr);
    if (!Array.isArray(items)) return;
    var existing = container.querySelectorAll('[data-tw-for-item]');
    existing.forEach(function(el) { el.remove(); });
    items.forEach(function(item, idx) {
      var clone = tmpl.cloneNode(true);
      clone.removeAttribute('data-tw-for-template');
      clone.setAttribute('data-tw-for-item', idx);
      clone.style.display = '';
      // Interpolate {item.*} / {item} in text nodes and attributes
      __twInterpolateNode(clone, { item: item, index: idx });
      container.appendChild(clone);
    });
  });
}

// ── Safe expression evaluator ────────────────────────────────────────────────
function __twEval(expr) {
  try {
    var fn = new Function(
      Object.keys(__twState).join(','),
      'try { return (' + expr + '); } catch(e) { return undefined; }'
    );
    return fn.apply(null, Object.keys(__twState).map(function(k) { return __twState[k]; }));
  } catch(e) {
    return undefined;
  }
}

// ── Text interpolation for tw-for clones ─────────────────────────────────────
function __twInterpolateNode(root, ctx) {
  var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
  var node;
  while ((node = walker.nextNode())) {
    node.textContent = node.textContent.replace(/\{([^{}]+)\}/g, function(_, expr) {
      try {
        var fn = new Function(Object.keys(ctx).join(','), 'try{return('+expr+');}catch(e){return "";}');
        var v = fn.apply(null, Object.keys(ctx).map(function(k){return ctx[k];}));
        return v !== null && v !== undefined ? v : '';
      } catch(e) { return ''; }
    });
  }
  root.querySelectorAll('*').forEach(function(el) {
    Array.from(el.attributes).forEach(function(attr) {
      if (attr.name.startsWith('data-tw-')) return;
      attr.value = attr.value.replace(/\{([^{}]+)\}/g, function(_, expr) {
        try {
          var fn = new Function(Object.keys(ctx).join(','), 'try{return('+expr+');}catch(e){return "";}');
          var v = fn.apply(null, Object.keys(ctx).map(function(k){return ctx[k];}));
          return v !== null && v !== undefined ? v : '';
        } catch(e) { return ''; }
      });
    });
  });
}

// ── Event binding ─────────────────────────────────────────────────────────────
function __twBindEvents() {
  // bind:value -> two-way binding
  document.querySelectorAll('[data-tw-bind]').forEach(function(el) {
    if (el.__twBound) return;
    el.__twBound = true;
    var key = el.getAttribute('data-tw-bind');
    var eventName = (el.type === 'checkbox' || el.tagName === 'SELECT') ? 'change' : 'input';
    el.addEventListener(eventName, function() {
      var val = el.type === 'checkbox' ? el.checked : el.value;
      __twSet(key, val);
    });
  });

  // on:* -> event handlers
  document.querySelectorAll('[data-tw-on]').forEach(function(el) {
    if (el.__twOnBound) return;
    el.__twOnBound = true;
    try {
      var handlers = JSON.parse(el.getAttribute('data-tw-on'));
      Object.keys(handlers).forEach(function(eventName) {
        el.addEventListener(eventName, function(event) {
          var expr = handlers[eventName];
          try {
            var fn = new Function(
              Object.keys(__twState).concat(['event', '__twSet', '__twGet']).join(','),
              expr
            );
            fn.apply(null, Object.keys(__twState).map(function(k) { return __twState[k]; }).concat([event, __twSet, __twGet]));
          } catch(e) { console.error('TW event error:', e); }
          __twSync();
        });
      });
    } catch(e) {}
  });

  // tw-ref
  document.querySelectorAll('[data-tw-ref]').forEach(function(el) {
    __twRefs[el.getAttribute('data-tw-ref')] = el;
  });
}

// ── Fetch helper for API calls ───────────────────────────────────────────────
window.__twFetch = async function(url, options) {
  options = options || {};
  var method = (options.method || 'GET').toUpperCase();
  var headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  var body = options.body !== undefined ? JSON.stringify(options.body) : undefined;
  try {
    var res = await fetch(url, { method: method, headers: headers, body: body });
    var ct = res.headers.get('content-type') || '';
    var data = ct.includes('application/json') ? await res.json() : await res.text();
    return { ok: res.ok, status: res.status, data: data };
  } catch(e) {
    return { ok: false, status: 0, data: null, error: e.message };
  }
};

// ── Public API ────────────────────────────────────────────────────────────────
window.__tw = {
  state: __twState,
  set: __twSet,
  get: __twGet,
  watch: __twWatch,
  sync: __twSync,
  refs: __twRefs,
  eval: __twEval,
  fetch: __twFetch,
};

// ── Init on DOM ready ─────────────────────────────────────────────────────────
function __twInit() {
  __twBindEvents();
  __twSync();
  // Re-bind after dynamic DOM changes (tw-for, etc.)
  var observer = new MutationObserver(function() {
    __twBindEvents();
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', __twInit);
} else {
  __twInit();
}

})();
"""

# ─── Compiler directive parsers ───────────────────────────────────────────────

_STATE_BLOCK_RE = re.compile(r'\bstate\s*\{([^}]*)\}', re.DOTALL)
_STATE_KV_RE = re.compile(r'(\w+)\s+(.+?)(?=\n\s*\w|\Z)', re.DOTALL)


def parse_state_block(source: str) -> dict:
    """
    Parse:
        state {
            count 0
            name "hello"
            items []
        }
    Returns {"count": 0, "name": "hello", "items": []}
    """
    state = {}
    for block_match in _STATE_BLOCK_RE.finditer(source):
        body = block_match.group(1)
        for kv in _STATE_KV_RE.finditer(body.strip()):
            key = kv.group(1).strip()
            raw = kv.group(2).strip()
            from . import compiler as _c
            val = _c.parse_literal_value(raw)
            # Strip outer quotes from string values
            if isinstance(val, str) and len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            state[key] = val
    return state


def has_reactivity(source: str) -> bool:
    """Quick check: does this .tw file use any reactive features?"""
    patterns = [
        r'\bstate\s*\{',
        r'\bbind:',
        r'\bon:',
        r'\bshow:',
        r'\btw-for\b',
        r'\btw-text\b',
        r'\btw-ref\b',
    ]
    return any(re.search(p, source) for p in patterns)


def build_state_init_script(state: dict) -> str:
    """Generates the inline script that seeds __twDefineState."""
    if not state:
        return ""
    return f"__twDefineState({json.dumps(state, ensure_ascii=False)});"


def get_reactivity_runtime_js() -> str:
    return _TW_REACTIVE_RUNTIME


# ─── HTML attribute transformer ───────────────────────────────────────────────
# These convert .tw reactive directives to data-tw-* HTML attributes
# so the runtime JS can pick them up.

def transform_reactive_attrs(attrs: list) -> list:
    """
    Convert:
        bind:value "count"   -> data-tw-bind="count"
        show:visible "count > 0" -> data-tw-show="count > 0"
        on:click "count++"   -> data-tw-on='{"click":"count++"}'
        tw-ref "myInput"     -> data-tw-ref="myInput"
        tw-text "count"      -> data-tw-text="count"
    """
    out = []
    on_handlers = {}
    for name, value in attrs:
        nl = name.lower()
        if nl.startswith("bind:"):
            out.append(("data-tw-bind", value))
        elif nl.startswith("show:"):
            out.append(("data-tw-show", value))
        elif nl.startswith("on:"):
            event = nl[3:]
            on_handlers[event] = value
        elif nl in {"tw-ref", "tw:ref"}:
            out.append(("data-tw-ref", value))
        elif nl in {"tw-text", "tw:text"}:
            out.append(("data-tw-text", value))
        elif nl in {"tw-html", "tw:html"}:
            out.append(("data-tw-html", value))
        elif nl in {"tw-for", "tw:for"}:
            out.append(("data-tw-for", value))
        elif nl in {"tw-class", "tw:class"}:
            # Expect JSON string: '{"active": "isActive", "hidden": "!show"}'
            out.append(("data-tw-class", value))
        else:
            out.append((name, value))

    if on_handlers:
        out.append(("data-tw-on", json.dumps(on_handlers)))

    return out

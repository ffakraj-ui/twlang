"""
Runtime Loader for TW Framework.

Analyzes what client-side capabilities a page needs and generates
the minimal set of <script> tags to load only those runtimes.

Each capability (state, router, form, realtime, auth, fetch) has its
own JS chunk. Static pages get zero script tags.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .module_boundaries import CLIENT, SERVER, SHARED, ImportClassifier, ImportInfo


@dataclass
class PageCapability:
    """What client capabilities a page needs."""
    needs_state: bool = False
    needs_router: bool = False
    needs_forms: bool = False
    needs_realtime: bool = False
    needs_auth_client: bool = False
    needs_fetch: bool = False
    needs_npm_packages: List[str] = field(default_factory=list)
    needs_client_components: List[str] = field(default_factory=list)
    needs_events: bool = False
    is_zero_js: bool = True
    tw_imports: List[str] = field(default_factory=list)
    npm_imports: List[str] = field(default_factory=list)

    def __post_init__(self):
        if any([self.needs_state, self.needs_router, self.needs_forms,
                self.needs_realtime, self.needs_auth_client, self.needs_fetch,
                self.needs_events, self.needs_npm_packages, self.needs_client_components]):
            self.is_zero_js = False


# ── Client runtime JS chunks ───────────────────────────────────────────────────

_BASE_RUNTIME_JS = """// TW Base Runtime (~0.5KB)
(function(){
'use strict';
window.__tw = window.__tw || {};
__tw.ready = function(fn) {
  if (document.readyState !== 'loading') fn();
  else document.addEventListener('DOMContentLoaded', fn);
};
__tw._initQueue = [];
__tw.onInit = function(fn) { __tw._initQueue.push(fn); };
})();"""

_STATE_RUNTIME_JS = """// TW State Runtime (~2KB)
(function(){
'use strict';
var __stores = {};
var __derived = {};

__tw.store = function(initialState) {
  var id = 's' + Math.random().toString(36).slice(2, 9);
  var state = Object.assign({}, initialState);
  var subscribers = [];
  function notify() {
    subscribers.forEach(function(fn) { try { fn(state); } catch(e){} });
  }
  __stores[id] = {
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
  return __stores[id];
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
})();"""

_ROUTER_RUNTIME_JS = """// TW Router Runtime (~4KB)
(function(){
'use strict';
__tw.router = {
  current: window.location.pathname,
  loading: false,
  error: null,
  _routes: {},
  _subscribers: [],
  _cache: {},

  init: function(routes) {
    this._routes = routes || {};
    window.addEventListener('popstate', this._onPopState.bind(this));
    document.addEventListener('click', this._onClick.bind(this));
  },

  goto: function(path, opts) {
    opts = opts || {};
    if (path === window.location.pathname && !opts.force) return Promise.resolve();
    this.loading = true;
    this.error = null;
    this._notify();

    return fetch(path, { headers: { 'X-TW-Route': '1' }, credentials: 'same-origin' })
      .then(function(res) {
        if (!res.ok) throw new Error('Route error: ' + res.status);
        return res.text();
      })
      .then(function(html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var newBody = doc.querySelector('body');
        if (newBody) {
          document.body.innerHTML = newBody.innerHTML;
        }
        var newTitle = doc.querySelector('title');
        if (newTitle) document.title = newTitle.textContent;
        window.history.pushState({}, '', path);
        this.current = path;
        this.loading = false;
        this._notify();
        if (__tw._initQueue) {
          __tw._initQueue.forEach(function(fn) { try { fn(); } catch(e){} });
        }
      }.bind(this))
      .catch(function(err) {
        this.error = err.message;
        this.loading = false;
        this._notify();
        if (!opts.silent) console.error('[TW Router]', err);
      }.bind(this));
  },

  prefetch: function(path) {
    if (this._cache[path]) return;
    var link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = path;
    link.as = 'document';
    document.head.appendChild(link);
    this._cache[path] = true;
  },

  back: function() { window.history.back(); },
  forward: function() { window.history.forward(); },

  subscribe: function(fn) {
    this._subscribers.push(fn);
    return this._subscribers.splice.bind(this._subscribers, this._subscribers.indexOf(fn), 1);
  },

  _notify: function() {
    this._subscribers.forEach(function(fn) {
      try { fn({ current: this.current, loading: this.loading, error: this.error }); } catch(e){}
    }.bind(this));
  },

  _onClick: function(e) {
    var link = e.target.closest('[data-tw-link]');
    if (!link) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    this.goto(link.getAttribute('data-tw-link'));
  },

  _onPopState: function(e) {
    this.goto(window.location.pathname, { force: true });
  }
};
})();"""

_FORM_RUNTIME_JS = """// TW Form Runtime (~3KB)
(function(){
'use strict';
__tw.form = {
  _forms: {},
  _validators: {},

  register: function(name, config) {
    this._forms[name] = {
      values: Object.assign({}, config.initialValues || {}),
      errors: {},
      touched: {},
      dirty: {},
      submitting: false,
      step: 0,
      _subs: []
    };
    this._validators[name] = config.validate || {};
    return this._forms[name];
  },

  get: function(name) { return this._forms[name]; },

  setValue: function(formName, field, value) {
    var f = this._forms[formName];
    if (!f) return;
    f.values[field] = value;
    f.dirty[field] = true;
    this._validateField(formName, field);
    this._notify(formName);
  },

  setTouched: function(formName, field) {
    var f = this._forms[formName];
    if (!f) return;
    f.touched[field] = true;
    this._notify(formName);
  },

  _validateField: function(formName, field) {
    var f = this._forms[formName];
    var validators = this._validators[formName] || {};
    var validator = validators[field];
    if (!validator) { delete f.errors[field]; return; }
    var error = validator(f.values[field], f.values);
    if (error) f.errors[field] = error;
    else delete f.errors[field];
  },

  validate: function(formName) {
    var f = this._forms[formName];
    if (!f) return false;
    var validators = this._validators[formName] || {};
    var valid = true;
    Object.keys(validators).forEach(function(field) {
      this._validateField(formName, field);
      if (f.errors[field]) valid = false;
    }.bind(this));
    this._notify(formName);
    return valid;
  },

  submit: function(formName, action) {
    var f = this._forms[formName];
    if (!f) return Promise.resolve();
    if (!this.validate(formName)) return Promise.reject(new Error('Validation failed'));
    f.submitting = true;
    this._notify(formName);
    return Promise.resolve(action(f.values))
      .then(function(result) {
        f.submitting = false;
        this._notify(formName);
        return result;
      }.bind(this))
      .catch(function(err) {
        f.submitting = false;
        if (err.field) f.errors[err.field] = err.message;
        this._notify(formName);
        throw err;
      }.bind(this));
  },

  reset: function(formName) {
    var f = this._forms[formName];
    if (!f) return;
    var config = this._validators[formName];
    f.values = {};
    f.errors = {};
    f.touched = {};
    f.dirty = {};
    f.submitting = false;
    this._notify(formName);
  },

  subscribe: function(formName, fn) {
    var f = this._forms[formName];
    if (!f) return function(){};
    f._subs.push(fn);
    return function() {
      var idx = f._subs.indexOf(fn);
      if (idx > -1) f._subs.splice(idx, 1);
    };
  },

  _notify: function(formName) {
    var f = this._forms[formName];
    if (!f) return;
    f._subs.forEach(function(fn) { try { fn(f); } catch(e){} });
  }
};
})();"""

_REALTIME_RUNTIME_JS = """// TW Realtime Runtime (~2KB)
(function(){
'use strict';
__tw.realtime = {
  _connections: {},

  connect: function(path, opts) {
    opts = opts || {};
    if (this._connections[path]) return this._connections[path];

    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + path;
    var ws = new WebSocket(url);
    var handlers = {};
    var reconnectDelay = 1000;
    var maxDelay = 30000;
    var shouldReconnect = true;
    var ready = false;

    var conn = {
      on: function(event, fn) {
        if (!handlers[event]) handlers[event] = [];
        handlers[event].push(fn);
        return function() {
          var idx = handlers[event].indexOf(fn);
          if (idx > -1) handlers[event].splice(idx, 1);
        };
      },
      send: function(type, data) {
        if (ws.readyState === 1) {
          ws.send(JSON.stringify({ type: type, data: data }));
        }
      },
      close: function() {
        shouldReconnect = false;
        ws.close();
        delete __tw.realtime._connections[path];
      },
      isReady: function() { return ready; }
    };

    ws.onopen = function() {
      ready = true;
      reconnectDelay = 1000;
      (handlers.open || []).forEach(function(fn) { try { fn(); } catch(e){} });
    };

    ws.onmessage = function(e) {
      try {
        var msg = JSON.parse(e.data);
        (handlers[msg.type] || []).forEach(function(fn) {
          try { fn(msg.data); } catch(e){}
        });
      } catch(err) {
        (handlers.message || []).forEach(function(fn) { try { fn(e.data); } catch(e){} });
      }
    };

    ws.onerror = function(err) {
      (handlers.error || []).forEach(function(fn) { try { fn(err); } catch(e){} });
    };

    ws.onclose = function() {
      ready = false;
      (handlers.close || []).forEach(function(fn) { try { fn(); } catch(e){} });
      if (shouldReconnect) {
        setTimeout(function() {
          if (reconnectDelay < maxDelay) reconnectDelay *= 2;
          __tw.realtime._connections[path] = null;
          __tw.realtime.connect(path, opts);
        }, reconnectDelay);
      }
    };

    this._connections[path] = conn;
    return conn;
  }
};
})();"""

_AUTH_CLIENT_RUNTIME_JS = """// TW Auth Client Runtime (~1KB)
(function(){
'use strict';
__tw.auth = {
  user: null,
  loggedIn: false,
  _subs: [],

  init: function(session) {
    this.user = session ? session.user : null;
    this.loggedIn = !!session;
    this._notify();
  },

  login: function(credentials) {
    return fetch('/__tw/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials)
    }).then(function(res) { return res.json(); })
      .then(function(result) {
        if (result.user) {
          this.user = result.user;
          this.loggedIn = true;
          this._notify();
        }
        return result;
      }.bind(this));
  },

  logout: function() {
    return fetch('/__tw/auth/logout', { method: 'POST' })
      .then(function(res) { return res.json(); })
      .then(function() {
        this.user = null;
        this.loggedIn = false;
        this._notify();
      }.bind(this));
  },

  hasRole: function(role) {
    if (!this.user || !this.user.roles) return false;
    return this.user.roles.indexOf(role) > -1;
  },

  can: function(permission) {
    if (!this.user || !this.user.permissions) return false;
    return this.user.permissions.indexOf(permission) > -1;
  },

  subscribe: function(fn) {
    this._subs.push(fn);
    return function() {
      var idx = this._subs.indexOf(fn);
      if (idx > -1) this._subs.splice(idx, 1);
    }.bind(this);
  },

  _notify: function() {
    this._subs.forEach(function(fn) {
      try { fn({ user: this.user, loggedIn: this.loggedIn }); } catch(e){}
    }.bind(this));
  }
};
})();"""

_FETCH_RUNTIME_JS = """// TW Fetch Runtime (~1KB)
(function(){
'use strict';
var _cache = {};
var _pending = {};

__tw.fetch = function(url, opts) {
  opts = opts || {};
  var cacheKey = opts.cacheKey || url;
  var revalidate = opts.revalidate || 0;

  // Deduplication: if a request is already pending, wait for it
  if (_pending[cacheKey]) return _pending[cacheKey];

  // Check cache
  if (_cache[cacheKey]) {
    var entry = _cache[cacheKey];
    if (!revalidate || (Date.now() - entry.at) < revalidate * 1000) {
      return Promise.resolve(entry.data);
    }
  }

  var promise = fetch(url, opts).then(function(res) {
    return res.json();
  }).then(function(data) {
    _cache[cacheKey] = { data: data, at: Date.now() };
    delete _pending[cacheKey];
    return data;
  }).catch(function(err) {
    delete _pending[cacheKey];
    throw err;
  });

  _pending[cacheKey] = promise;
  return promise;
};

__tw.fetch.invalidate = function(key) {
  if (key) delete _cache[key];
  else _cache = {};
};
})();"""


class RuntimeLoader:
    """Determines and generates required JS chunks per page."""

    RUNTIME_SOURCES = {
        "base": _BASE_RUNTIME_JS,
        "state": _STATE_RUNTIME_JS,
        "router": _ROUTER_RUNTIME_JS,
        "form": _FORM_RUNTIME_JS,
        "realtime": _REALTIME_RUNTIME_JS,
        "auth": _AUTH_CLIENT_RUNTIME_JS,
        "fetch": _FETCH_RUNTIME_JS,
    }

    CAPABILITY_TO_RUNTIME = {
        "needs_state": "state",
        "needs_router": "router",
        "needs_forms": "form",
        "needs_realtime": "realtime",
        "needs_auth_client": "auth",
        "needs_fetch": "fetch",
    }

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir
        self._chunk_cache: Dict[str, str] = {}

    def analyze_page_capabilities(
        self,
        source: str = "",
        page_ast=None,
        imports: Optional[List[ImportInfo]] = None,
    ) -> PageCapability:
        """Analyze what client capabilities a page needs."""
        cap = PageCapability()

        # Check imports
        if imports:
            for imp in imports:
                path = imp.path if hasattr(imp, 'path') else str(imp)
                if path.startswith("tw/"):
                    cap.tw_imports.append(path)
                    if path == "tw/state":
                        cap.needs_state = True
                    elif path == "tw/router":
                        cap.needs_router = True
                    elif path == "tw/form":
                        cap.needs_forms = True
                    elif path == "tw/realtime":
                        cap.needs_realtime = True
                    elif path == "tw/auth":
                        cap.needs_auth_client = True
                    elif path == "tw/fetch":
                        cap.needs_fetch = True
                elif "/" in path or path.startswith("@"):
                    cap.npm_imports.append(path)

        # Check source for reactive directives (existing reactivity system)
        if source:
            if re.search(r'\bstate\s*\{', source):
                cap.needs_state = True
            if re.search(r'\bon:\w+', source) or re.search(r'\bbind:', source):
                cap.needs_events = True
                cap.is_zero_js = False
            if re.search(r'\bLink\s*\{', source) or re.search(r'\blink\s+"', source):
                cap.needs_router = True
            if re.search(r'\bsocket\s*\(', source) or re.search(r'\bWebSocket\b', source):
                cap.needs_realtime = True
            if re.search(r'\bForm\s*\{', source):
                cap.needs_forms = True
            if re.search(r'\buseAuth\s*\(', source):
                cap.needs_auth_client = True
            if re.search(r'\buseFetch\s*\(', source):
                cap.needs_fetch = True

        # Check page AST for state_vars, events, router
        if page_ast:
            if getattr(page_ast, "state_vars", None):
                cap.needs_state = True
            if getattr(page_ast, "loaded_modules", None):
                cap.is_zero_js = False

        # Recompute is_zero_js
        cap.__post_init__()

        return cap

    def get_chunk_url(self, runtime_name: str) -> str:
        """Get or create a chunk URL for a runtime."""
        if runtime_name in self._chunk_cache:
            return self._chunk_cache[runtime_name]

        js = self.RUNTIME_SOURCES.get(runtime_name, "")
        if not js:
            return ""

        url = self._write_chunk(js, runtime_name)
        self._chunk_cache[runtime_name] = url
        return url

    def _write_chunk(self, js_content: str, name: str) -> str:
        """Write a JS chunk to the output directory."""
        digest = hashlib.sha256(js_content.encode("utf-8")).hexdigest()[:12]
        filename = f"{name}.{digest}.js"

        if not self.output_dir:
            # In-memory: return a virtual URL
            return f"/_tw/chunks/{filename}"

        chunk_dir = os.path.join(self.output_dir, "_tw", "chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path = os.path.join(chunk_dir, filename)

        if not os.path.exists(chunk_path):
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(js_content)

        return f"/_tw/chunks/{filename}"

    def generate_runtime_tags(self, cap: PageCapability) -> str:
        """Generate <script> tags for needed runtime chunks."""
        if cap.is_zero_js:
            return ""

        tags = []

        # Base runtime always needed for interactive pages
        base_url = self.get_chunk_url("base")
        if base_url:
            tags.append(f'<script src="{base_url}"></script>')

        # Add specific runtime chunks
        for cap_key, runtime_name in self.CAPABILITY_TO_RUNTIME.items():
            if getattr(cap, cap_key, False):
                url = self.get_chunk_url(runtime_name)
                if url:
                    tags.append(f'<script src="{url}"></script>')

        # Add events runtime if needed (existing reactivity)
        if cap.needs_events:
            # The existing reactivity runtime handles events
            # It's injected by _inject_reactivity_runtime in compiler.py
            pass

        return "\n".join(tags) if tags else ""

    def get_required_runtimes(self, cap: PageCapability) -> List[str]:
        """Return list of runtime names needed for this page."""
        if cap.is_zero_js:
            return []

        runtimes = ["base"]
        for cap_key, runtime_name in self.CAPABILITY_TO_RUNTIME.items():
            if getattr(cap, cap_key, False):
                if runtime_name not in runtimes:
                    runtimes.append(runtime_name)
        return runtimes


__all__ = ["PageCapability", "RuntimeLoader"]

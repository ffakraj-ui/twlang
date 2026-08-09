"""Client-side router runtime JS for tw/router."""

_ROUTER_RUNTIME_JS = """// TW Router Runtime — client-side SPA navigation
(function(){
'use strict';
window.__tw = window.__tw || {};
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
        if (newBody) document.body.innerHTML = newBody.innerHTML;
        var newTitle = doc.querySelector('title');
        if (newTitle) document.title = newTitle.textContent;
        window.history.pushState({}, '', path);
        this.current = path;
        this.loading = false;
        this._notify();
        if (__tw._initQueue) __tw._initQueue.forEach(function(fn) { try { fn(); } catch(e){} });
      }.bind(this))
      .catch(function(err) {
        this.error = err.message;
        this.loading = false;
        this._notify();
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
    var self = this;
    return function() {
      var idx = self._subscribers.indexOf(fn);
      if (idx > -1) self._subscribers.splice(idx, 1);
    };
  },

  _notify: function() {
    var self = this;
    this._subscribers.forEach(function(fn) {
      try { fn({ current: self.current, loading: self.loading, error: self.error }); } catch(e){}
    });
  },

  _onClick: function(e) {
    var link = e.target.closest('[data-tw-link]');
    if (!link) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    this.goto(link.getAttribute('data-tw-link'));
  },

  _onPopState: function() {
    this.goto(window.location.pathname, { force: true });
  }
};
})();"""


def get_router_runtime_js() -> str:
    return _ROUTER_RUNTIME_JS


__all__ = ["get_router_runtime_js"]

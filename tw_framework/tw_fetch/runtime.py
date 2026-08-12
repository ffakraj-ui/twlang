"""Client-side fetch runtime JS for tw/fetch."""

_FETCH_RUNTIME_JS = """// TW Fetch Runtime — cached client-side fetch with deduplication
(function(){
'use strict';
window.__tw = window.__tw || {};
var _cache = {};
var _pending = {};

__tw.fetch = function(url, opts) {
  opts = opts || {};
  var cacheKey = opts.cacheKey || url;
  var revalidate = opts.revalidate || 0;

  // Deduplication
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

__tw.fetch.mutate = function(url, opts) {
  opts = opts || {};
  opts.method = opts.method || 'POST';
  return fetch(url, opts).then(function(res) { return res.json(); });
};
})();"""


def get_fetch_runtime_js() -> str:
    return _FETCH_RUNTIME_JS


__all__ = ["get_fetch_runtime_js"]

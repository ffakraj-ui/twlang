"""Client-side realtime runtime JS for tw/realtime."""

_REALTIME_RUNTIME_JS = """// TW Realtime Runtime — WebSocket connections with auto-reconnect
(function(){
'use strict';
window.__tw = window.__tw || {};
__tw.realtime = {
  _connections: {},

  connect: function(path, opts) {
    opts = opts || {};
    if (this._connections[path]) return this._connections[path];

    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + location.host + path;
    var ws = new WebSocket(url);
    var handlers = {};
    var reconnectDelay = opts.reconnectDelay || 1000;
    var maxDelay = opts.maxReconnectDelay || 30000;
    var shouldReconnect = opts.autoReconnect !== false;
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
        if (ws.readyState === 1) ws.send(JSON.stringify({ type: type, data: data }));
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
      reconnectDelay = opts.reconnectDelay || 1000;
      (handlers.open || []).forEach(function(fn) { try { fn(); } catch(e){} });
    };

    ws.onmessage = function(e) {
      try {
        var msg = JSON.parse(e.data);
        (handlers[msg.type] || []).forEach(function(fn) { try { fn(msg.data); } catch(e){} });
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


def get_realtime_runtime_js() -> str:
    return _REALTIME_RUNTIME_JS


__all__ = ["get_realtime_runtime_js"]

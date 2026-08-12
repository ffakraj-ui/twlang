"""Client-side auth runtime JS for tw/auth."""

_AUTH_CLIENT_RUNTIME_JS = """// TW Auth Client Runtime — session state and auth methods
(function(){
'use strict';
window.__tw = window.__tw || {};
__tw.auth = {
  user: null,
  loggedIn: false,
  _subs: [],

  init: function(session) {
    if (session) {
      this.user = session.user || null;
      this.loggedIn = !!session.loggedIn;
    }
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
    var self = this;
    return function() {
      var idx = self._subs.indexOf(fn);
      if (idx > -1) self._subs.splice(idx, 1);
    };
  },

  _notify: function() {
    var self = this;
    this._subs.forEach(function(fn) {
      try { fn({ user: self.user, loggedIn: self.loggedIn }); } catch(e){}
    });
  }
};
})();"""


def get_auth_client_runtime_js() -> str:
    return _AUTH_CLIENT_RUNTIME_JS


__all__ = ["get_auth_client_runtime_js"]

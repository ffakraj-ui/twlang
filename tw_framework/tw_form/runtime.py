"""Client-side form runtime JS for tw/form."""

_FORM_RUNTIME_JS = """// TW Form Runtime — form state, validation, and submission
(function(){
'use strict';
window.__tw = window.__tw || {};
__tw.form = {
  _forms: {},
  _validators: {},

  register: function(name, config) {
    config = config || {};
    this._forms[name] = {
      values: Object.assign({}, config.initialValues || {}),
      errors: {},
      touched: {},
      dirty: {},
      submitting: false,
      step: 0,
      totalSteps: config.totalSteps || 1,
      _subs: []
    };
    this._validators[name] = config.validators || {};
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
    if (!f) return;
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
        if (err && err.field) f.errors[err.field] = err.message;
        this._notify(formName);
        throw err;
      }.bind(this));
  },

  reset: function(formName) {
    var f = this._forms[formName];
    if (!f) return;
    f.values = {};
    f.errors = {};
    f.touched = {};
    f.dirty = {};
    f.submitting = false;
    f.step = 0;
    this._notify(formName);
  },

  nextStep: function(formName) {
    var f = this._forms[formName];
    if (!f) return;
    if (f.step < f.totalSteps - 1) { f.step++; this._notify(formName); }
  },

  prevStep: function(formName) {
    var f = this._forms[formName];
    if (!f) return;
    if (f.step > 0) { f.step--; this._notify(formName); }
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


def get_form_runtime_js() -> str:
    return _FORM_RUNTIME_JS


__all__ = ["get_form_runtime_js"]

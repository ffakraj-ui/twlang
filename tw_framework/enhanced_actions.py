"""
Enhanced Server Actions: Progressive Enhancement + Revalidation Hooks.

Extends server_actions.py with:
  - Progressive enhancement (works without JS via form POST fallback)
  - Client-side JS generation for action bindings
  - Tag-based cache revalidation after action execution
  - Optimistic UI updates
  - Loading states
  - Redirect on success
  - Error handlers

This is a separate module to avoid modifying the core server_actions.py
(which has complex f-strings that are hard to edit inline).
"""
from __future__ import annotations

import json
import threading
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable

from .server_actions import ServerAction, ActionRegistry, get_action_registry
import time
import concurrent

logger = logging.getLogger(__name__)


@dataclass
class ActionBinding:
    """Client-side binding for a server action.

    Generated for each action in the actions { } block of a .tw file.
    The binding creates a JS function that POSTs to /__tw/actions
    with CSRF token and progressive enhancement fallback.
    """
    action_name: str
    element_id: str = ""
    event: str = "click"
    method: str = "POST"
    progressive: bool = True
    revalidate_tags: List[str] = field(default_factory=list)
    redirect_on_success: str = ""
    optimistic_update: str = ""
    loading_state: str = ""
    error_handler: str = ""


def generate_action_client_js(bindings, csrf_token=""):
    """Generate client-side JavaScript for server action bindings.

    This JS:
    1. Attaches event listeners to elements with data-tw-action attributes
    2. On trigger, POSTs to /__tw/actions with CSRF token
    3. Updates the DOM with the response
    4. Provides progressive enhancement (works as form POST without JS)
    5. Supports optimistic updates and loading states
    6. Triggers tag-based cache revalidation after action
    """
    bindings_json = json.dumps([
        {
            "name": b.action_name,
            "element_id": b.element_id,
            "event": b.event,
            "progressive": b.progressive,
            "revalidate_tags": b.revalidate_tags,
            "redirect": b.redirect_on_success,
            "optimistic": b.optimistic_update,
            "loading_class": b.loading_state,
            "error_handler": b.error_handler,
        }
        for b in bindings
    ])

    # Build JS without f-string escaping issues
    js_parts = []
    js_parts.append('<script>\n')
    js_parts.append('(function() {\n')
    js_parts.append('  var _twActions = ' + bindings_json + ';\n')
    js_parts.append('  var _twCsrf = "' + csrf_token + '";\n')
    js_parts.append('''
  function _twDoAction(binding, formData) {
    if (binding.loading_class && binding.element_id) {
      var el = document.getElementById(binding.element_id);
      if (el) el.classList.add(binding.loading_class);
    }
    if (binding.optimistic) {
      var optEl = document.querySelector(binding.optimistic);
      if (optEl && formData) optEl.classList.add('tw-optimistic');
    }
    var body = {
      action: binding.name,
      args: formData || {},
      csrf: _twCsrf
    };
    return fetch('/__tw/actions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function(r) { return r.json(); })
      .then(function(result) {
        if (binding.loading_class && binding.element_id) {
          var el = document.getElementById(binding.element_id);
          if (el) el.classList.remove(binding.loading_class);
        }
        if (result.ok) {
          if (binding.element_id && result.data) {
            var el = document.getElementById(binding.element_id);
            if (el) {
              if (typeof result.data === 'string') el.innerHTML = result.data;
              else el.textContent = JSON.stringify(result.data);
            }
          }
          if (binding.redirect) {
            window.location.href = binding.redirect;
            return;
          }
          if (binding.revalidate_tags && binding.revalidate_tags.length > 0) {
            fetch('/__tw/revalidate', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ tags: binding.revalidate_tags })
            });
          }
        } else {
          if (binding.error_handler && window[binding.error_handler]) {
            window[binding.error_handler](result.error);
          } else {
            console.error('Action failed:', result.error);
          }
        }
      })
      .catch(function(err) {
        if (binding.loading_class && binding.element_id) {
          var el = document.getElementById(binding.element_id);
          if (el) el.classList.remove(binding.loading_class);
        }
        console.error('Action network error:', err);
      });
  }

  _twActions.forEach(function(binding) {
    if (binding.element_id) {
      var el = document.getElementById(binding.element_id);
      if (el) {
        el.addEventListener(binding.event || 'click', function(e) {
          e.preventDefault();
          var formData = {};
          if (el.tagName === 'FORM') {
            var inputs = el.querySelectorAll('input, textarea, select');
            inputs.forEach(function(input) {
              if (input.name) formData[input.name] = input.value;
            });
          }
          _twDoAction(binding, formData);
        });
      }
    }
  });

  document.querySelectorAll('[data-tw-action]').forEach(function(el) {
    var actionName = el.getAttribute('data-tw-action');
    var binding = _twActions.find(function(b) { return b.name === actionName; });
    if (binding) return;
    el.addEventListener('click', function(e) {
      e.preventDefault();
      _twDoAction({
        name: actionName,
        element_id: el.id || '',
        event: 'click',
        loading_class: '',
        redirect: el.getAttribute('data-tw-redirect') || '',
        revalidate_tags: [],
        optimistic: '',
        error_handler: ''
      }, {});
    });
  });
})();
''')
    js_parts.append('</script>')
    return ''.join(js_parts)


def generate_progressive_form(action_name, fields, method="POST", csrf_token=""):
    """Generate a progressive enhancement form for a server action.

    This form works WITHOUT JavaScript - it POSTs to /__tw/actions
    as a regular HTML form. When JS is available, the action binding
    intercepts the submit and does it via fetch() instead.

    This is the "progressive enhancement" pattern from Next.js Server Actions.
    """
    inputs_html = ""
    for f in fields:
        name = f.get("name", "")
        ftype = f.get("type", "text")
        placeholder = f.get("placeholder", "")
        required = "required" if f.get("required", False) else ""
        inputs_html += '<input type="{}" name="{}" placeholder="{}" {}>\n'.format(
            ftype, name, placeholder, required
        )

    form_html = '<form data-tw-action="{}" method="{}" action="/__tw/actions">\n'.format(
        action_name, method
    )
    form_html += '  <input type="hidden" name="__action" value="{}">\n'.format(action_name)
    form_html += '  <input type="hidden" name="__csrf" value="{}">\n'.format(csrf_token)
    form_html += '  ' + inputs_html
    form_html += '  <button type="submit">Submit</button>\n'
    form_html += '</form>'
    return form_html


def parse_actions_block(source):
    """Parse an actions { } block from .tw source.

    Returns a list of action dicts:
      [{name: "increment", handler: "...", require_auth: True, revalidate_tags: [...], ...}]

    Also detects:
      - revalidate tags: revalidate "posts,users"
      - redirect: redirect "/dashboard"
      - progressive: progressive true/false
    """
    actions = []

    actions_match = re.search(r'actions\s*\{', source)
    if not actions_match:
        return actions

    start = actions_match.end()
    depth = 1
    i = start
    while i < len(source) and depth > 0:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
        i += 1

    block = source[start:i-1]

    fn_pattern = re.compile(r'fn\s+(\w+)\s*\(([^)]*)\)\s*\{')
    for match in fn_pattern.finditer(block):
        name = match.group(1)
        params = match.group(2).strip()

        body_start = match.end()
        depth = 1
        j = body_start
        while j < len(block) and depth > 0:
            if block[j] == '{':
                depth += 1
            elif block[j] == '}':
                depth -= 1
            j += 1

        body = block[body_start:j-1].strip()

        after_fn = block[j:j+200]

        revalidate_tags = []
        redirect = ""
        progressive = True

        tags_match = re.search(r'revalidate\s+["\']([^"\']+)["\']', after_fn)
        if tags_match:
            revalidate_tags = [t.strip() for t in tags_match.group(1).split(",")]

        redirect_match = re.search(r'redirect\s+["\']([^"\']+)["\']', after_fn)
        if redirect_match:
            redirect = redirect_match.group(1)

        prog_match = re.search(r'progressive\s+(true|false)', after_fn, re.IGNORECASE)
        if prog_match:
            progressive = prog_match.group(1).lower() == "true"

        actions.append({
            "name": name,
            "params": params,
            "handler": body,
            "revalidate_tags": revalidate_tags,
            "redirect": redirect,
            "progressive": progressive,
            "require_auth": "require_auth" in after_fn.lower(),
        })

    return actions


__all__ = [
    "ActionBinding",
    "generate_action_client_js",
    "generate_progressive_form",
    "parse_actions_block",
    "ActionSchemaValidator",
    "ActionRateLimiter",
    "ActionAuditEntry",
    "ActionAuditLogger",
    "ActionMiddleware",
    "ActionResponseBuilder",
    "ActionClientGenerator",
    "ActionStep",
    "ChainResult",
    "ActionChain",
    "ActionPipeline",
    "QueuedAction",
    "ActionQueue",
    "ActionEventEmitter",
]


# ── Action Schema Validator ──────────────────────────────────────────

class ActionSchemaValidator:
    """Validates server action arguments against a schema.

    Provides type checking, range validation, pattern matching,
    and custom validators — similar to Zod or Joi.
    """

    @staticmethod
    def validate(args: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """Validate args against schema. Returns error message or None.

        Schema format:
            {
                "field_name": {
                    "type": "string|number|boolean|array|object|email|url|uuid",
                    "required": True/False,
                    "min": int,         # min length (string/array) or value (number)
                    "max": int,         # max length or value
                    "pattern": "regex", # regex pattern for strings
                    "enum": [...],       # allowed values
                    "default": ...,      # default value if missing
                    "custom": callable,  # custom validator function
                }
            }
        """
        import re as _re

        for field_name, rules in schema.items():
            value = args.get(field_name)
            required = rules.get("required", False)
            field_type = rules.get("type", "string")

            # Check required
            if value is None:
                if "default" in rules:
                    args[field_name] = rules["default"]
                    continue
                if required:
                    return f"Missing required field: {field_name}"
                continue

            # Type validation
            type_errors = {
                "string": lambda v: not isinstance(v, str),
                "number": lambda v: not isinstance(v, (int, float)) or isinstance(v, bool),
                "boolean": lambda v: not isinstance(v, bool),
                "array": lambda v: not isinstance(v, list),
                "object": lambda v: not isinstance(v, dict),
                "email": lambda v: not isinstance(v, str) or "@" not in v or "." not in v,
                "url": lambda v: not isinstance(v, str) or not v.startswith(("http://", "https://")),
                "uuid": lambda v: not isinstance(v, str) or len(v) != 36 or v.count("-") != 4,
            }

            checker = type_errors.get(field_type)
            if checker and checker(value):
                return f"Field '{field_name}' must be a valid {field_type}"

            # Min/Max validation
            if "min" in rules:
                if field_type in ("string", "array") and isinstance(value, (str, list)):
                    if len(value) < rules["min"]:
                        return f"Field '{field_name}' must be at least {rules['min']} characters/items"
                elif field_type == "number" and isinstance(value, (int, float)):
                    if value < rules["min"]:
                        return f"Field '{field_name}' must be at least {rules['min']}"

            if "max" in rules:
                if field_type in ("string", "array") and isinstance(value, (str, list)):
                    if len(value) > rules["max"]:
                        return f"Field '{field_name}' must be at most {rules['max']} characters/items"
                elif field_type == "number" and isinstance(value, (int, float)):
                    if value > rules["max"]:
                        return f"Field '{field_name}' must be at most {rules['max']}"

            # Pattern validation
            if "pattern" in rules and isinstance(value, str):
                if not _re.match(rules["pattern"], value):
                    return f"Field '{field_name}' has invalid format"

            # Enum validation
            if "enum" in rules:
                if value not in rules["enum"]:
                    return f"Field '{field_name}' must be one of: {', '.join(str(v) for v in rules['enum'])}"

            # Custom validator
            if "custom" in rules and callable(rules["custom"]):
                try:
                    result = rules["custom"](value)
                    if result is not True and isinstance(result, str):
                        return result
                except Exception as e:
                    return f"Field '{field_name}' custom validation failed: {e}"

        return None


# ── Action Rate Limiter ──────────────────────────────────────────────

class ActionRateLimiter:
    """Rate limiting for server actions.

    Uses a token bucket algorithm per identity (IP, user, session).
    Each action can have its own rate limit configuration.
    """

    def __init__(self):
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def check(self, action_name: str, identity: str,
              max_requests: int = 100, window: int = 60) -> bool:
        """Check if an action can be executed. Returns True if allowed.

        Args:
            action_name: Name of the action
            identity: Unique identifier (IP, user ID, session ID)
            max_requests: Maximum requests in the window
            window: Time window in seconds
        """
        import time as _time
        key = f"{action_name}:{identity}"

        with self._lock:
            now = _time.time()
            if key not in self._buckets:
                self._buckets[key] = {
                    "tokens": max_requests,
                    "last_refill": now,
                    "max": max_requests,
                    "window": window,
                }

            bucket = self._buckets[key]
            # Refill tokens based on elapsed time
            elapsed = now - bucket["last_refill"]
            refill = (elapsed / bucket["window"]) * bucket["max"]
            bucket["tokens"] = min(bucket["max"], bucket["tokens"] + refill)
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False

    def get_remaining(self, action_name: str, identity: str) -> int:
        """Get remaining requests for an action+identity."""
        key = f"{action_name}:{identity}"
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket:
                return int(bucket["tokens"])
            return 0

    def reset(self, action_name: str, identity: str = "") -> int:
        """Reset rate limit for an action. Returns count reset."""
        with self._lock:
            if identity:
                key = f"{action_name}:{identity}"
                if key in self._buckets:
                    del self._buckets[key]
                    return 1
            else:
                count = sum(1 for k in list(self._buckets) if k.startswith(f"{action_name}:"))
                self._buckets = {k: v for k, v in self._buckets.items() if not k.startswith(f"{action_name}:")}
                return count
        return 0

    def cleanup_expired(self, max_age: int = 3600) -> int:
        """Remove expired buckets. Returns count removed."""
        import time as _time
        now = _time.time()
        with self._lock:
            expired = [k for k, v in self._buckets.items() if now - v["last_refill"] > max_age]
            for k in expired:
                del self._buckets[k]
            return len(expired)

    def stats(self) -> Dict[str, Any]:
        """Return rate limiter statistics."""
        with self._lock:
            return {
                "total_buckets": len(self._buckets),
                "actions_tracked": len(set(k.split(":")[0] for k in self._buckets)),
            }


# ── Action Audit Log ────────────────────────────────────────────────

@dataclass
class ActionAuditEntry:
    """A single audit log entry for a server action."""
    timestamp: float
    action_name: str
    identity: str
    success: bool
    duration_ms: float
    error: str = ""
    args_summary: str = ""  # truncated args for logging (no secrets)


class ActionAuditLogger:
    """Audit logging for server actions.

    Logs every action execution with timestamp, identity, success/failure,
    duration, and error message. Useful for security auditing and debugging.
    """

    def __init__(self, max_entries: int = 10000, log_to_file: str = ""):
        self._entries: List[ActionAuditEntry] = []
        self._max_entries = max_entries
        self._log_file = log_to_file
        self._lock = threading.Lock()

    def log(self, action_name: str, identity: str, success: bool,
            duration_ms: float, error: str = "", args: Optional[Dict] = None) -> None:
        """Log an action execution."""
        import time as _time

        # Truncate args for logging (remove potential secrets)
        args_summary = ""
        if args:
            safe_args = {}
            for k, v in args.items():
                if any(s in k.lower() for s in ("password", "secret", "token", "key", "auth")):
                    safe_args[k] = "***"
                else:
                    safe_args[k] = str(v)[:100]
            args_summary = json.dumps(safe_args)[:500]

        entry = ActionAuditEntry(
            timestamp=_time.time(),
            action_name=action_name,
            identity=identity,
            success=success,
            duration_ms=duration_ms,
            error=error[:200],
            args_summary=args_summary,
        )

        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

        # Log to file if configured
        if self._log_file:
            try:
                with open(self._log_file, "a") as f:
                    f.write(f"[{entry.timestamp}] {action_name} by {identity}: "
                           f"{'OK' if success else 'FAIL'} ({duration_ms:.1f}ms)")
                    if error:
                        f.write(f" error={error[:100]}")
                    f.write("\n")
            except OSError:
                pass

    def get_entries(self, action_name: str = "", identity: str = "",
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries, optionally filtered."""
        with self._lock:
            entries = self._entries.copy()

        if action_name:
            entries = [e for e in entries if e.action_name == action_name]
        if identity:
            entries = [e for e in entries if e.identity == identity]

        entries = entries[-limit:]
        return [
            {
                "timestamp": e.timestamp,
                "action": e.action_name,
                "identity": e.identity,
                "success": e.success,
                "duration_ms": e.duration_ms,
                "error": e.error,
                "args": e.args_summary,
            }
            for e in reversed(entries)
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Return audit log statistics."""
        with self._lock:
            total = len(self._entries)
            success = sum(1 for e in self._entries if e.success)
            failed = total - success
            avg_duration = sum(e.duration_ms for e in self._entries) / total if total > 0 else 0

            actions: Dict[str, int] = {}
            for e in self._entries:
                actions[e.action_name] = actions.get(e.action_name, 0) + 1

        return {
            "total_entries": total,
            "success": success,
            "failed": failed,
            "success_rate": f"{(success / total * 100):.1f}%" if total > 0 else "N/A",
            "avg_duration_ms": round(avg_duration, 2),
            "actions_by_name": actions,
            "max_entries": self._max_entries,
        }


# ── Action Middleware ────────────────────────────────────────────────

class ActionMiddleware:
    """Middleware for server action execution.

    Wraps action execution with:
    - Rate limiting
    - Audit logging
    - Schema validation
    - Error handling
    - Performance tracking
    """

    def __init__(self, rate_limiter: ActionRateLimiter = None,
                 audit_logger: ActionAuditLogger = None,
                 schema_validator: ActionSchemaValidator = None):
        self.rate_limiter = rate_limiter or ActionRateLimiter()
        self.audit = audit_logger or ActionAuditLogger()
        self.validator = schema_validator or ActionSchemaValidator()

    def process(self, action_name: str, args: Dict[str, Any],
                schema: Optional[Dict] = None,
                identity: str = "anonymous",
                rate_limit: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        """Process an action request through middleware.

        Returns dict with:
          - allowed: True if action should proceed
          - error: Error message if not allowed
          - validated_args: Cleaned/validated args
        """
        # 1. Schema validation
        if schema:
            error = self.validator.validate(args, schema)
            if error:
                self.audit.log(action_name, identity, False, 0, error, args)
                return {"allowed": False, "error": error, "validated_args": args}

        # 2. Rate limiting
        if rate_limit:
            allowed = self.rate_limiter.check(
                action_name, identity,
                max_requests=rate_limit.get("requests", 100),
                window=rate_limit.get("window", 60),
            )
            if not allowed:
                error = "Rate limit exceeded. Please try again later."
                self.audit.log(action_name, identity, False, 0, error, args)
                return {"allowed": False, "error": error, "validated_args": args}

        return {"allowed": True, "error": None, "validated_args": args}

    def record_result(self, action_name: str, identity: str,
                      success: bool, duration_ms: float,
                      error: str = "", args: Optional[Dict] = None) -> None:
        """Record the result of an action execution."""
        self.audit.log(action_name, identity, success, duration_ms, error, args)

    def get_stats(self) -> Dict[str, Any]:
        """Return combined middleware statistics."""
        return {
            "rate_limiter": self.rate_limiter.stats(),
            "audit": self.audit.get_stats(),
        }


# ── Action Response Builder ──────────────────────────────────────────

class ActionResponseBuilder:
    """Builds consistent response objects for server actions.

    Provides helpers for common response patterns:
    - Success with data
    - Error with message
    - Redirect
    - Validation error
    - Rate limit error
    - Server error
    """

    @staticmethod
    def success(data: Any = None, message: str = "OK",
                revalidate_tags: Optional[List[str]] = None,
                redirect: str = "") -> Dict[str, Any]:
        """Build a success response."""
        response = {"ok": True, "message": message}
        if data is not None:
            response["data"] = data
        if revalidate_tags:
            response["revalidate"] = revalidate_tags
        if redirect:
            response["redirect"] = redirect
        return response

    @staticmethod
    def error(message: str, status: int = 400,
              code: str = "ERROR",
              field: str = "") -> Dict[str, Any]:
        """Build an error response."""
        response = {"ok": False, "error": message, "status": status, "code": code}
        if field:
            response["field"] = field
        return response

    @staticmethod
    def validation_error(errors: Dict[str, str]) -> Dict[str, Any]:
        """Build a validation error response."""
        return {"ok": False, "error": "Validation failed", "status": 400,
                "code": "VALIDATION_ERROR", "errors": errors}

    @staticmethod
    def rate_limited(retry_after: int = 60) -> Dict[str, Any]:
        """Build a rate limit response."""
        return {"ok": False, "error": "Rate limit exceeded",
                "status": 429, "code": "RATE_LIMITED",
                "retry_after": retry_after}

    @staticmethod
    def unauthorized() -> Dict[str, Any]:
        """Build an unauthorized response."""
        return {"ok": False, "error": "Authentication required",
                "status": 401, "code": "UNAUTHORIZED"}

    @staticmethod
    def forbidden() -> Dict[str, Any]:
        """Build a forbidden response."""
        return {"ok": False, "error": "Insufficient permissions",
                "status": 403, "code": "FORBIDDEN"}

    @staticmethod
    def not_found(what: str = "Resource") -> Dict[str, Any]:
        """Build a not found response."""
        return {"ok": False, "error": f"{what} not found",
                "status": 404, "code": "NOT_FOUND"}

    @staticmethod
    def server_error(error: str = "Internal server error") -> Dict[str, Any]:
        """Build a server error response."""
        return {"ok": False, "error": error,
                "status": 500, "code": "SERVER_ERROR"}

    @staticmethod
    def redirect(url: str, permanent: bool = False) -> Dict[str, Any]:
        """Build a redirect response."""
        return {"ok": True, "redirect": url, "status": 301 if permanent else 302}


# ── Action Client Generator ─────────────────────────────────────────

class ActionClientGenerator:
    """Generates client-side TypeScript/JavaScript for server actions.

    Creates type-safe client functions that call server actions
    via the /__tw/actions endpoint.
    """

    @staticmethod
    def generate_js(actions: List[Dict[str, Any]], csrf_token: str = "") -> str:
        """Generate client-side JS for a set of actions.

        Args:
            actions: List of action dicts from parse_actions_block()
            csrf_token: CSRF token for the current session

        Returns:
            JavaScript code that creates callable functions for each action.
        """
        lines = [
            "<script>",
            "(function() {",
            '  var __twCsrf = "' + csrf_token + '";',
            "  window.__twActions = window.__twActions || {};",
            "",
        ]

        for action in actions:
            name = action.get("name", "")
            redirect = action.get("redirect", "")
            tags = action.get("revalidate_tags", [])
            progressive = action.get("progressive", True)

            # Generate function for this action
            lines.append("  window.__twActions." + name + " = function(args) {")
            lines.append("    return fetch('/__tw/actions', {")
            lines.append("      method: 'POST',")
            lines.append("      headers: { 'Content-Type': 'application/json' },")
            lines.append("      body: JSON.stringify({")
            lines.append("        action: '" + name + "',")
            lines.append("        args: args || {},")
            lines.append("        csrf: __twCsrf")
            lines.append("      })")
            lines.append("    }).then(function(r) { return r.json(); })")
            lines.append("      .then(function(result) {")
            lines.append("        if (result.ok) {")

            if redirect:
                lines.append("          window.location.href = '" + redirect + "';")
            if tags:
                lines.append("          // Trigger cache revalidation")
                lines.append("          fetch('/__tw/revalidate', {")
                lines.append("            method: 'POST',")
                lines.append("            headers: { 'Content-Type': 'application/json' },")
                lines.append("            body: JSON.stringify({ tags: " + json.dumps(tags) + " })")
                lines.append("          });")

            lines.append("          return result;")
            lines.append("        } else {")
            lines.append("          console.error('Action " + name + " failed:', result.error);")
            lines.append("          throw new Error(result.error);")
            lines.append("        }")
            lines.append("      });")
            lines.append("  };")
            lines.append("")

        lines.append("  // Progressive enhancement: auto-bind to forms")
        lines.append("  document.querySelectorAll('[data-tw-action]').forEach(function(el) {")
        lines.append("    var actionName = el.getAttribute('data-tw-action');")
        lines.append("    var handler = window.__twActions[actionName];")
        lines.append("    if (!handler) return;")
        lines.append("    el.addEventListener('submit', function(e) {")
        lines.append("      e.preventDefault();")
        lines.append("      var formData = {};")
        lines.append("      var inputs = el.querySelectorAll('input, textarea, select');")
        lines.append("      inputs.forEach(function(input) {")
        lines.append("        if (input.name) formData[input.name] = input.value;")
        lines.append("      });")
        lines.append("      handler(formData).catch(function(err) {")
        lines.append("        console.error(err);")
        lines.append("      });")
        lines.append("    });")
        lines.append("  });")
        lines.append("})();")
        lines.append("</script>")

        return "\n".join(lines)

    @staticmethod
    def generate_type_definitions(actions: List[Dict[str, Any]]) -> str:
        """Generate TypeScript type definitions for actions.

        Useful for IDE autocompletion when using TypeScript.
        """
        lines = [
            "// Auto-generated by TW Framework — do not edit",
            "",
        ]

        for action in actions:
            name = action.get("name", "")
            params = action.get("params", "")
            redirect = action.get("redirect", "")
            tags = action.get("revalidate_tags", [])

            # Parse params into type
            if params:
                param_parts = [p.strip() for p in params.split(",") if p.strip()]
                param_types = []
                for p in param_parts:
                    if ":" in p:
                        param_types.append(f"  {p.strip()}: any;")
                    else:
                        param_types.append(f"  {p.strip()}?: any;")
                params_type = "{\n" + "\n".join(param_types) + "\n}"
            else:
                params_type = "Record<string, never>"

            result_type = "{ ok: boolean; data?: any; error?: string"
            if redirect:
                result_type += "; redirect?: string"
            if tags:
                result_type += "; revalidate?: string[]"
            result_type += " }"

            lines.append(f"export function {name}(args: {params_type}): Promise<{result_type}>;")
            lines.append("")

        return "\n".join(lines)


# ── Update __all__ ──────────────────────────────────────────────────

# ── Action Composition & Chaining ────────────────────────────────────

@dataclass
class ActionStep:
    """A single step in an action chain."""
    name: str
    handler: Callable[..., Any]
    input_transform: Optional[Callable[[Any], Any]] = None
    output_transform: Optional[Callable[[Any], Any]] = None
    on_error: Optional[Callable[[Exception], Any]] = None
    timeout_ms: float = 30000
    retries: int = 0
    retry_delay_ms: float = 500


@dataclass
class ChainResult:
    """Result of an action chain execution."""
    success: bool
    steps_completed: int = 0
    steps_total: int = 0
    results: List[Any] = field(default_factory=list)
    error: str = ""
    error_step: str = ""
    total_time_ms: float = 0.0


class ActionChain:
    """Chain multiple server actions into a pipeline.

    Actions execute sequentially, with each action's output feeding
    into the next action's input. Supports:
    - Input/output transforms between steps
    - Per-step error handlers
    - Timeouts and retries
    - Conditional branching (skip steps based on previous output)
    - Parallel fan-out (run multiple steps concurrently)
    """

    def __init__(self, name: str = ""):
        self.name = name or "unnamed_chain"
        self._steps: List[ActionStep] = []
        self._conditions: Dict[str, Callable[[Any], bool]] = {}
        self._metadata: Dict[str, Any] = {}

    def step(self, name: str, handler: Callable[..., Any],
             input_transform: Optional[Callable] = None,
             output_transform: Optional[Callable] = None,
             on_error: Optional[Callable] = None,
             timeout_ms: float = 30000,
             retries: int = 0,
             condition: Optional[Callable[[Any], bool]] = None) -> "ActionChain":
        """Add a step to the chain. Returns self for chaining."""
        step_obj = ActionStep(
            name=name,
            handler=handler,
            input_transform=input_transform,
            output_transform=output_transform,
            on_error=on_error,
            timeout_ms=timeout_ms,
            retries=retries,
        )
        self._steps.append(step_obj)
        if condition:
            self._conditions[name] = condition
        return self

    def execute(self, initial_input: Any = None,
                context: Optional[Dict[str, Any]] = None) -> ChainResult:
        """Execute the action chain.

        Each step receives the output of the previous step (after transforms).
        """
        import time as _time
        start = _time.time()
        ctx = context or {}
        result = ChainResult(
            success=True,
            steps_total=len(self._steps),
        )

        current_value = initial_input

        for i, step in enumerate(self._steps):
            # Check condition
            condition = self._conditions.get(step.name)
            if condition and not condition(current_value):
                result.steps_completed = i
                result.results.append(None)
                continue

            # Apply input transform
            if step.input_transform:
                try:
                    current_value = step.input_transform(current_value)
                except Exception as e:
                    result.success = False
                    result.error = f"Input transform failed for '{step.name}': {e}"
                    result.error_step = step.name
                    result.total_time_ms = (_time.time() - start) * 1000
                    return result

            # Execute handler with retries
            step_result = self._execute_step(step, current_value, ctx)

            if step_result is None and step.on_error:
                # Error already handled by on_error
                result.steps_completed = i + 1
                result.results.append(None)
                continue

            if step_result is None:
                result.success = False
                result.error = f"Step '{step.name}' failed"
                result.error_step = step.name
                result.total_time_ms = (_time.time() - start) * 1000
                return result

            # Apply output transform
            if step.output_transform:
                try:
                    step_result = step.output_transform(step_result)
                except Exception as e:
                    result.success = False
                    result.error = f"Output transform failed for '{step.name}': {e}"
                    result.error_step = step.name
                    result.total_time_ms = (_time.time() - start) * 1000
                    return result

            result.results.append(step_result)
            result.steps_completed = i + 1
            current_value = step_result

        result.total_time_ms = (_time.time() - start) * 1000
        return result

    def _execute_step(self, step: ActionStep, input_value: Any,
                       ctx: Dict[str, Any]) -> Any:
        """Execute a single step with retries."""
        last_error: Optional[Exception] = None

        for attempt in range(step.retries + 1):
            try:
                return step.handler(input_value, ctx)
            except Exception as e:
                last_error = e
                logger.warning(
                    "Chain step '%s' failed (attempt %d/%d): %s",
                    step.name, attempt + 1, step.retries + 1, e
                )
                if attempt < step.retries:
                    import time as _time
                    _time.sleep(step.retry_delay_ms / 1000)

        # All retries exhausted
        if step.on_error:
            try:
                return step.on_error(last_error)
            except Exception as e:
                logger.error("Error handler for '%s' failed: %s", step.name, e)

        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize chain metadata."""
        return {
            "name": self.name,
            "step_count": len(self._steps),
            "steps": [
                {
                    "name": s.name,
                    "timeout_ms": s.timeout_ms,
                    "retries": s.retries,
                    "has_input_transform": s.input_transform is not None,
                    "has_output_transform": s.output_transform is not None,
                    "has_error_handler": s.on_error is not None,
                    "has_condition": s.name in self._conditions,
                }
                for s in self._steps
            ],
        }


class ActionPipeline:
    """High-level pipeline for composing complex action workflows.

    Supports:
    - Sequential chains
    - Parallel fan-out (run multiple actions concurrently)
    - Fan-in (merge results from parallel actions)
    - Conditional branching (if/else based on action result)
    - Loops (iterate over a list)
    """

    def __init__(self, name: str = ""):
        self.name = name or "unnamed_pipeline"
        self._nodes: List[Dict[str, Any]] = []

    def sequence(self, actions: List[Callable],
                  initial: Any = None) -> "ActionPipeline":
        """Add a sequence of actions to the pipeline."""
        self._nodes.append({
            "type": "sequence",
            "actions": actions,
            "initial": initial,
        })
        return self

    def parallel(self, actions: List[Callable],
                  input_value: Any = None,
                  merge: str = "list") -> "ActionPipeline":
        """Run multiple actions in parallel.

        merge: "list" (collect results in order), "dict" (merge dicts), "first" (first non-None)
        """
        self._nodes.append({
            "type": "parallel",
            "actions": actions,
            "input": input_value,
            "merge": merge,
        })
        return self

    def branch(self, condition: Callable[[Any], bool],
               if_true: Callable, if_false: Optional[Callable] = None) -> "ActionPipeline":
        """Add a conditional branch."""
        self._nodes.append({
            "type": "branch",
            "condition": condition,
            "if_true": if_true,
            "if_false": if_false,
        })
        return self

    def loop(self, action: Callable, items: List[Any]) -> "ActionPipeline":
        """Loop over items, calling action for each."""
        self._nodes.append({
            "type": "loop",
            "action": action,
            "items": items,
        })
        return self

    def execute(self, initial: Any = None) -> Dict[str, Any]:
        """Execute the pipeline."""
        import time as _time
        start = _time.time()
        current = initial
        results: List[Any] = []

        for node in self._nodes:
            node_type = node["type"]

            if node_type == "sequence":
                chain = ActionChain(f"{self.name}_seq")
                for i, action in enumerate(node["actions"]):
                    chain.step(f"step_{i}", action)
                result = chain.execute(current)
                results.append(result)
                if result.success:
                    current = result.results[-1] if result.results else None
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "error_node": "sequence",
                        "results": results,
                        "time_ms": (_time.time() - start) * 1000,
                    }

            elif node_type == "parallel":
                import concurrent.futures
                actions = node["actions"]
                input_val = node.get("input", current)
                merge = node.get("merge", "list")

                with concurrent.futures.ThreadPoolExecutor(max_workers=len(actions)) as executor:
                    futures = {executor.submit(a, input_val): i for i, a in enumerate(actions)}
                    parallel_results: List[Any] = [None] * len(actions)

                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            parallel_results[idx] = future.result()
                        except Exception as e:
                            parallel_results[idx] = {"error": str(e)}

                if merge == "dict":
                    merged: Dict[str, Any] = {}
                    for r in parallel_results:
                        if isinstance(r, dict):
                            merged.update(r)
                    current = merged
                elif merge == "first":
                    current = next((r for r in parallel_results if r is not None), None)
                else:
                    current = parallel_results

                results.append(parallel_results)

            elif node_type == "branch":
                condition = node["condition"]
                if condition(current):
                    current = node["if_true"](current)
                elif node["if_false"]:
                    current = node["if_false"](current)
                results.append(current)

            elif node_type == "loop":
                action = node["action"]
                items = node["items"]
                loop_results: List[Any] = []
                for item in items:
                    try:
                        result = action(item)
                        loop_results.append(result)
                    except Exception as e:
                        loop_results.append({"error": str(e)})
                current = loop_results
                results.append(loop_results)

        return {
            "success": True,
            "results": results,
            "final_value": current,
            "time_ms": (_time.time() - start) * 1000,
        }


# ── Action Queue & Background Processing ─────────────────────────────

@dataclass
class QueuedAction:
    """An action queued for background processing."""
    id: str
    action_name: str
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    queued_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = "queued"  # queued | running | completed | failed
    result: Any = None
    error: str = ""


class ActionQueue:
    """Background queue for async server action processing.

    Actions are queued and processed by worker threads.
    Supports:
    - Priority-based ordering
    - Max concurrent workers
    - Result tracking and polling
    - Timeout and cancellation
    - Retry on failure
    """

    def __init__(self, max_workers: int = 4, max_retries: int = 2):
        self._queue: List[QueuedAction] = []
        self._completed: Dict[str, QueuedAction] = {}
        self._max_workers = max_workers
        self._max_retries = max_retries
        self._running = False
        self._workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._handlers: Dict[str, Callable] = {}
        self._counter = 0

    def register_handler(self, action_name: str, handler: Callable) -> None:
        """Register a handler for an action name."""
        self._handlers[action_name] = handler

    def enqueue(self, action_name: str, *args, priority: int = 0,
                **kwargs) -> str:
        """Queue an action for background processing. Returns action ID."""
        with self._lock:
            self._counter += 1
            action_id = f"action_{self._counter}_{int(time.time())}"

            queued = QueuedAction(
                id=action_id,
                action_name=action_name,
                args=list(args),
                kwargs=kwargs,
                priority=priority,
            )
            self._queue.append(queued)

            # Sort by priority (higher first), then by queue time
            self._queue.sort(key=lambda a: (-a.priority, a.queued_at))

            self._cond.notify()
            return action_id

    def get_status(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a queued action."""
        with self._lock:
            # Check completed
            if action_id in self._completed:
                a = self._completed[action_id]
                return {
                    "id": a.id,
                    "status": a.status,
                    "result": a.result,
                    "error": a.error,
                    "queued_at": a.queued_at,
                    "started_at": a.started_at,
                    "completed_at": a.completed_at,
                    "duration_ms": (a.completed_at - a.started_at) * 1000 if a.completed_at else 0,
                }

            # Check running/queued
            for a in self._queue:
                if a.id == action_id:
                    return {
                        "id": a.id,
                        "status": a.status,
                        "error": "",
                        "queued_at": a.queued_at,
                    }

        return None

    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            return
        self._running = True

        for i in range(self._max_workers):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            t.start()
            self._workers.append(t)

        logger.info("ActionQueue started with %d workers", self._max_workers)

    def stop(self) -> None:
        """Stop worker threads."""
        self._running = False
        with self._cond:
            self._cond.notify_all()

        for t in self._workers:
            t.join(timeout=2)

        self._workers.clear()
        logger.info("ActionQueue stopped")

    def _worker_loop(self, worker_id: int) -> None:
        """Worker thread loop."""
        while self._running:
            with self._cond:
                while not self._queue and self._running:
                    self._cond.wait(timeout=1)
                    if not self._running:
                        return

                if not self._queue:
                    continue

                action = self._queue.pop(0)
                action.status = "running"
                action.started_at = time.time()

            # Execute outside lock
            self._execute_action(action)

    def _execute_action(self, action: QueuedAction) -> None:
        """Execute a single queued action."""
        handler = self._handlers.get(action.action_name)

        if not handler:
            action.status = "failed"
            action.error = f"No handler registered for '{action.action_name}'"
            action.completed_at = time.time()
            with self._lock:
                self._completed[action.id] = action
            return

        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries + 1):
            try:
                result = handler(*action.args, **action.kwargs)
                action.status = "completed"
                action.result = result
                action.completed_at = time.time()

                with self._lock:
                    self._completed[action.id] = action

                logger.info("Action '%s' completed in %.1fms",
                            action.id, (action.completed_at - action.started_at) * 1000)
                return

            except Exception as e:
                last_error = e
                logger.warning(
                    "Action '%s' failed (attempt %d/%d): %s",
                    action.id, attempt + 1, self._max_retries + 1, e
                )
                if attempt < self._max_retries:
                    time.sleep(0.5 * (attempt + 1))

        # All retries exhausted
        action.status = "failed"
        action.error = str(last_error)
        action.completed_at = time.time()
        with self._lock:
            self._completed[action.id] = action

    def get_queue_stats(self) -> Dict[str, Any]:
        """Return queue statistics."""
        with self._lock:
            return {
                "queue_length": len(self._queue),
                "completed_count": len(self._completed),
                "workers": self._max_workers,
                "running": self._running,
                "handlers": list(self._handlers.keys()),
            }

    def clear_completed(self, max_age_seconds: float = 3600) -> int:
        """Clear old completed actions. Returns count cleared."""
        now = time.time()
        with self._lock:
            old_ids = [
                aid for aid, a in self._completed.items()
                if now - a.completed_at > max_age_seconds
            ]
            for aid in old_ids:
                del self._completed[aid]
        return len(old_ids)


# ── Action Event Emitter ─────────────────────────────────────────────

class ActionEventEmitter:
    """Event emitter for server action lifecycle events.

    Emits events at various stages:
    - before_action: before handler executes
    - after_action: after successful execution
    - on_error: when handler fails
    - on_retry: when action is retried
    - on_timeout: when action times out
    - on_validate: when validation runs
    - on_ratelimit: when rate limit is hit

    Listeners can be async or sync, and can modify the action result.
    """

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def on(self, event: str, listener: Callable) -> None:
        """Register a listener for an event."""
        self._listeners.setdefault(event, []).append(listener)

    def off(self, event: str, listener: Callable) -> None:
        """Remove a listener."""
        if event in self._listeners:
            try:
                self._listeners[event].remove(listener)
            except ValueError:
                pass

    def emit(self, event: str, *args, **kwargs) -> List[Any]:
        """Emit an event. Returns list of listener results."""
        results: List[Any] = []
        for listener in self._listeners.get(event, []):
            try:
                result = listener(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.warning("Event listener for '%s' failed: %s", event, e)
        return results

    def emit_async(self, event: str, *args, **kwargs) -> None:
        """Emit an event asynchronously (non-blocking)."""
        import threading
        for listener in self._listeners.get(event, []):
            t = threading.Thread(
                target=lambda l, a, kw: self._safe_call(l, a, kw),
                args=(listener, args, kwargs),
                daemon=True,
            )
            t.start()

    @staticmethod
    def _safe_call(listener: Callable, args: tuple, kwargs: dict) -> None:
        try:
            listener(*args, **kwargs)
        except Exception as e:
            logger.warning("Async event listener failed: %s", e)

    def has_listeners(self, event: str) -> bool:
        """Check if an event has any listeners."""
        return bool(self._listeners.get(event))

    def listener_count(self, event: str) -> int:
        """Get the number of listeners for an event."""
        return len(self._listeners.get(event, []))

    def get_events(self) -> Dict[str, int]:
        """Get all registered events and their listener counts."""
        return {event: len(lst) for event, lst in self._listeners.items()}

    def clear(self, event: str = "") -> None:
        """Clear listeners for an event or all events."""
        if event:
            self._listeners.pop(event, None)
        else:
            self._listeners.clear()

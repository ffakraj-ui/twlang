"""
Server Actions for TW Framework.

Provides a secure invocation boundary for server-side functions
callable from client-side interactions.

Architecture:
  CLIENT → POST /__tw/actions → validate CSRF → authenticate → validate args → execute → response

Server actions are registered server-side only. Never exposed to clients.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ServerAction:
    """A registered server action."""
    name: str
    handler: Callable
    schema: Optional[Dict[str, Any]] = None  # argument validation schema
    require_auth: bool = True
    require_csrf: bool = True
    roles: List[str] = field(default_factory=list)
    rate_limit: Optional[Dict[str, int]] = None  # {requests: N, window: seconds}


class ActionRegistry:
    """Registry of server actions."""

    def __init__(self):
        self._actions: Dict[str, ServerAction] = {}

    def register(
        self,
        name: str,
        handler: Callable,
        *,
        schema: Optional[Dict[str, Any]] = None,
        require_auth: bool = True,
        require_csrf: bool = True,
        roles: Optional[List[str]] = None,
        rate_limit: Optional[Dict[str, int]] = None,
    ) -> None:
        """Register a server action."""
        self._actions[name] = ServerAction(
            name=name,
            handler=handler,
            schema=schema,
            require_auth=require_auth,
            require_csrf=require_csrf,
            roles=roles or [],
            rate_limit=rate_limit,
        )

    def get(self, name: str) -> Optional[ServerAction]:
        return self._actions.get(name)

    def list_actions(self) -> List[str]:
        return sorted(self._actions.keys())

    def validate_args(
        self,
        action: ServerAction,
        args: Dict[str, Any],
    ) -> Optional[str]:
        """Validate action arguments against schema. Returns error message or None."""
        if not action.schema:
            return None

        for field_name, rules in action.schema.items():
            required = rules.get("required", False)
            field_type = rules.get("type", "string")

            if field_name not in args:
                if required:
                    return f"Missing required field: {field_name}"
                continue

            value = args[field_name]

            # Type checking
            if field_type == "string" and not isinstance(value, str):
                return f"Field '{field_name}' must be a string"
            elif field_type == "number" and not isinstance(value, (int, float)):
                return f"Field '{field_name}' must be a number"
            elif field_type == "boolean" and not isinstance(value, bool):
                return f"Field '{field_name}' must be a boolean"
            elif field_type == "array" and not isinstance(value, list):
                return f"Field '{field_name}' must be an array"
            elif field_type == "object" and not isinstance(value, dict):
                return f"Field '{field_name}' must be an object"

            # Custom validation
            if "min" in rules and isinstance(value, (str, list)):
                if len(value) < rules["min"]:
                    return f"Field '{field_name}' must be at least {rules['min']} items"
            if "max" in rules and isinstance(value, (str, list)):
                if len(value) > rules["max"]:
                    return f"Field '{field_name}' must be at most {rules['max']} items"
            if "pattern" in rules and isinstance(value, str):
                import re
                if not re.match(rules["pattern"], value):
                    return f"Field '{field_name}' has invalid format"

        return None

    def execute(
        self,
        name: str,
        args: Dict[str, Any],
        session=None,
        csrf_token: str = "",
    ) -> Dict[str, Any]:
        """
        Execute a server action securely.

        Returns:
          {ok: True, data: ...} on success
          {ok: False, error: "..."} on failure
        """
        action = self.get(name)
        if not action:
            return {"ok": False, "error": f"Unknown action: {name}", "status": 404}

        # Auth check
        if action.require_auth and not session:
            return {"ok": False, "error": "Authentication required", "status": 401}

        # Role check
        if action.roles and session:
            if not any(session.has_role(r) for r in action.roles):
                return {"ok": False, "error": "Insufficient permissions", "status": 403}

        # CSRF check (would be done by caller, but we validate the token exists)
        if action.require_csrf and not csrf_token:
            return {"ok": False, "error": "CSRF token required", "status": 403}

        # Validate args
        error = self.validate_args(action, args)
        if error:
            return {"ok": False, "error": error, "status": 400}

        # Execute
        try:
            result = action.handler(args, session=session)
            if isinstance(result, dict) and "ok" in result:
                return result
            return {"ok": True, "data": result}
        except Exception as err:
            logger.exception("Server action '%s' failed", name)
            return {"ok": False, "error": str(err), "status": 500}


# Global registry
_action_registry = ActionRegistry()


def register_action(
    name: str,
    handler: Callable,
    **kwargs,
) -> None:
    """Register a server action."""
    _action_registry.register(name, handler, **kwargs)


def get_action_registry() -> ActionRegistry:
    return _action_registry


def handle_action_request(
    body: Dict[str, Any],
    cookies: Dict[str, str],
    session=None,
) -> Dict[str, Any]:
    """
    Handle an incoming server action request.

    Expected body format:
      {
        "action": "createPost",
        "args": { "title": "Hello", "content": "..." },
        "csrf": "token.signature"
      }
    """
    action_name = body.get("action", "")
    args = body.get("args", {})
    csrf_token = body.get("csrf", "")

    if not action_name:
        return {
            "status": 400,
            "body": json.dumps({"ok": False, "error": "Missing action name"}).encode(),
            "content_type": "application/json",
        }

    result = _action_registry.execute(action_name, args, session=session, csrf_token=csrf_token)

    status = result.get("status", 200)
    if "status" in result:
        del result["status"]

    return {
        "status": status,
        "body": json.dumps(result, ensure_ascii=False).encode("utf-8"),
        "content_type": "application/json",
    }


__all__ = [
    "ServerAction", "ActionRegistry",
    "register_action", "get_action_registry", "handle_action_request",
]

"""
TW Framework — Middleware utilities.

Provides auth middleware helpers and middleware chain utilities.
Actual middleware.tw parsing is handled in framework.py.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any, Callable, Dict, List, Optional


class AuthMiddleware:
    """Simple session-based auth middleware."""

    def __init__(self, secret: str = ""):
        self._secret = secret or secrets.token_hex(32)
        self._sessions: Dict[str, dict] = {}

    def create_session(self, user_id: str, roles: Optional[List[str]] = None) -> str:
        """Create a session token for a user."""
        token = secrets.token_urlsafe(32)
        self._sessions[token] = {
            "user_id": user_id,
            "roles": roles or [],
            "created": time.time(),
            "expires": time.time() + 3600,  # 1 hour
        }
        return token

    def verify_session(self, token: str) -> Optional[dict]:
        """Verify a session token. Returns session data or None."""
        session = self._sessions.get(token)
        if not session:
            return None
        if time.time() > session["expires"]:
            del self._sessions[token]
            return None
        return session

    def destroy_session(self, token: str) -> bool:
        """Destroy a session."""
        return self._sessions.pop(token, None) is not None


def require_auth(handler: Callable) -> Callable:
    """Decorator: require authenticated session for a handler."""
    def wrapper(request: dict, *args, **kwargs):
        session = request.get("session")
        if not session:
            return {"status": 401, "body": {"error": "Authentication required"}}
        return handler(request, *args, **kwargs)
    return wrapper


def require_role(role: str) -> Callable:
    """Decorator factory: require a specific role for a handler."""
    def decorator(handler: Callable) -> Callable:
        def wrapper(request: dict, *args, **kwargs):
            session = request.get("session")
            if not session:
                return {"status": 401, "body": {"error": "Authentication required"}}
            roles = session.get("roles", []) if isinstance(session, dict) else []
            if role not in roles:
                return {"status": 403, "body": {"error": f"Role '{role}' required"}}
            return handler(request, *args, **kwargs)
        return wrapper
    return decorator


class MiddlewareChain:
    """Chain of middleware functions executed in order."""

    def __init__(self):
        self._middlewares: List[Callable] = []

    def use(self, middleware: Callable) -> None:
        """Add a middleware to the chain."""
        self._middlewares.append(middleware)

    def execute(self, request: dict) -> dict:
        """Run all middleware in order. Each can modify the request."""
        for mw in self._middlewares:
            result = mw(request)
            if result is not None:
                return result
        return request


__all__ = ["AuthMiddleware", "require_auth", "require_role", "MiddlewareChain"]

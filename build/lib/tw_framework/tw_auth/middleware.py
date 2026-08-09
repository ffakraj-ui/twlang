"""
Auth middleware for tw/auth.

Provides route protection, role-based access control, and CSRF protection.
Integrates with the existing middleware system in framework.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .session import SessionManager, Session


@dataclass
class AuthRule:
    """A route protection rule."""
    match: str = "/**"
    required: bool = True
    redirect: str = "/login"
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)


class AuthMiddleware:
    """Middleware for authentication and authorization."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._rules: List[AuthRule] = []

    def add_rule(self, rule: AuthRule) -> None:
        self._rules.append(rule)

    def _match_path(self, path: str, pattern: str) -> bool:
        """Match a URL path against a pattern, supporting /** wildcards."""
        import fnmatch
        # Handle /** patterns (match path and all subpaths)
        if pattern.endswith("/**"):
            prefix = pattern[:-3]
            if path == prefix or path.startswith(prefix + "/"):
                return True
            return False
        # Also handle /* patterns (match direct children only)
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if not path.startswith(prefix + "/"):
                return False
            remainder = path[len(prefix) + 1:]
            return "/" not in remainder
        # Standard fnmatch for other patterns
        return fnmatch.fnmatch(path, pattern)

    def check(
        self,
        path: str,
        cookies: Dict[str, str],
        method: str = "GET",
    ) -> Dict[str, Any]:
        """
        Check if a request is authorized.

        Returns dict with:
          - authorized: bool
          - redirect: str (if unauthorized)
          - session: Session (if authorized)
          - error: str (if unauthorized)
        """
        import fnmatch

        # Find the first matching rule
        matched_rule = None
        for rule in self._rules:
            if self._match_path(path, rule.match):
                matched_rule = rule
                break

        if matched_rule is None:
            # No matching rule — allow by default
            return {"authorized": True, "session": None, "error": None}

        rule = matched_rule
        session = self.session_manager.get_session_from_cookies(cookies)

        if rule.required and not session:
            return {
                "authorized": False,
                "redirect": rule.redirect,
                "error": "Authentication required",
            }

        if session:
            if rule.roles:
                if not any(session.has_role(r) for r in rule.roles):
                    return {
                        "authorized": False,
                        "redirect": rule.redirect,
                        "error": "Insufficient role",
                    }

            if rule.permissions:
                if not any(session.can(p) for p in rule.permissions):
                    return {
                        "authorized": False,
                        "redirect": rule.redirect,
                        "error": "Insufficient permissions",
                    }

        return {
            "authorized": True,
            "session": session,
            "error": None,
        }

    def verify_csrf(
        self,
        token: str,
        cookies: Dict[str, str],
    ) -> bool:
        """Verify a CSRF token against the session."""
        session = self.session_manager.get_session_from_cookies(cookies)
        if not session:
            return False
        return self.session_manager.verify_csrf_token(token, session)


def require_auth(session_manager: SessionManager):
    """Decorator: require authentication for a handler."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cookies = kwargs.get("cookies", {})
            session = session_manager.get_session_from_cookies(cookies)
            if not session:
                return {
                    "status": 302,
                    "headers": [("Location", "/login")],
                    "body": b"",
                }
            kwargs["session"] = session
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(session_manager: SessionManager, role: str):
    """Decorator: require a specific role for a handler."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            cookies = kwargs.get("cookies", {})
            session = session_manager.get_session_from_cookies(cookies)
            if not session:
                return {
                    "status": 302,
                    "headers": [("Location", "/login")],
                    "body": b"",
                }
            if not session.has_role(role):
                return {
                    "status": 403,
                    "body": b"Forbidden",
                }
            kwargs["session"] = session
            return func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = ["AuthRule", "AuthMiddleware", "require_auth", "require_role"]

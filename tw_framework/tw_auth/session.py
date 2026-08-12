"""
Session management for tw/auth.

Provides secure session creation, verification, and destruction.
Sessions are stored server-side and referenced via secure HTTP-only cookies.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


@dataclass
class Session:
    """A user session."""
    session_id: str
    user_id: str = ""
    user_data: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    created_at: float = 0.0
    expires_at: float = 0.0
    csrf_token: str = ""

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return time.time() > self.expires_at

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def to_client_safe(self) -> Dict[str, Any]:
        """Return client-safe session data (no secrets)."""
        return {
            "user": self.user_data,
            "roles": self.roles,
            "permissions": self.permissions,
            "loggedIn": True,
        }


class SessionManager:
    """Server-side session management with secure cookies."""

    COOKIE_NAME = "tw_session"
    CSRF_COOKIE_NAME = "tw_csrf"
    DEFAULT_TTL = 86400 * 7  # 7 days

    def __init__(self, secret: str = ""):
        self._secret = secret or os.environ.get("TW_SESSION_SECRET", secrets.token_hex(32))
        self._sessions: Dict[str, Session] = {}
        self._store_callback: Optional[Callable] = None

    def create_session(
        self,
        user_id: str,
        user_data: Optional[Dict[str, Any]] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        ttl: float = 0,
    ) -> Session:
        """Create a new session."""
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        now = time.time()
        session = Session(
            session_id=session_id,
            user_id=user_id,
            user_data=user_data or {},
            roles=roles or [],
            permissions=permissions or [],
            created_at=now,
            expires_at=now + (ttl or self.DEFAULT_TTL),
            csrf_token=csrf_token,
        )
        self._sessions[session_id] = session
        return session

    def verify_session(self, session_id: str) -> Optional[Session]:
        """Verify a session ID. Returns the session if valid, None otherwise."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        if session.is_expired():
            self.destroy_session(session_id)
            return None
        return session

    def destroy_session(self, session_id: str) -> None:
        """Destroy a session."""
        self._sessions.pop(session_id, None)

    def get_session_from_cookies(self, cookies: Dict[str, str]) -> Optional[Session]:
        """Extract and verify session from cookies."""
        session_id = cookies.get(self.COOKIE_NAME, "")
        if not session_id:
            return None
        return self.verify_session(session_id)

    def generate_csrf_token(self, session: Session) -> str:
        """Generate a CSRF token for a session."""
        msg = f"{session.session_id}:{session.csrf_token}"
        sig = hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return f"{session.csrf_token}.{sig}"

    def verify_csrf_token(self, token: str, session: Session) -> bool:
        """Verify a CSRF token against a session."""
        if not token or "." not in token:
            return False
        provided_csrf, provided_sig = token.split(".", 1)
        msg = f"{session.session_id}:{provided_csrf}"
        expected_sig = hmac.new(self._secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided_sig, expected_sig)

    def get_cookie_header(self, session: Session, secure: bool = True) -> str:
        """Generate Set-Cookie header value for session."""
        flags = [
            "HttpOnly",
            "SameSite=Lax",
        ]
        if secure:
            flags.append("Secure")
        return f"{self.COOKIE_NAME}={session.session_id}; Path=/; {'; '.join(flags)}"

    def get_clear_cookie_header(self) -> str:
        """Generate Set-Cookie header to clear session."""
        return f"{self.COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count removed."""
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            self._sessions.pop(sid, None)
        return len(expired)


__all__ = ["Session", "SessionManager"]

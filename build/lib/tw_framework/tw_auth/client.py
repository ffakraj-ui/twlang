"""
Client-side auth state for tw/auth.

Provides a Python-side representation of client auth state
for SSR. The actual client-side auth runtime is in runtime.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .session import Session


@dataclass
class AuthClient:
    """Client-side auth state representation."""
    user: Dict[str, Any] = field(default_factory=dict)
    logged_in: bool = False
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: Optional[Session]) -> "AuthClient":
        """Create client auth state from a server session."""
        if not session:
            return cls()
        return cls(
            user=session.user_data,
            logged_in=True,
            roles=session.roles,
            permissions=session.permissions,
        )

    def to_client_config(self) -> Dict[str, Any]:
        """Serialize for client-side hydration."""
        return {
            "user": self.user,
            "loggedIn": self.logged_in,
            "roles": self.roles,
            "permissions": self.permissions,
        }


__all__ = ["AuthClient"]

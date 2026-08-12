"""Tests for tw/auth authentication system."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_auth.session import SessionManager, Session
from tw_framework.tw_auth.middleware import AuthMiddleware, AuthRule
from tw_framework.tw_auth.client import AuthClient


class TestSessionManager:
    def test_create_session(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123", {"name": "John"})
        assert session.user_id == "user123"
        assert session.user_data == {"name": "John"}
        assert session.session_id != ""

    def test_verify_session(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        verified = mgr.verify_session(session.session_id)
        assert verified is not None
        assert verified.user_id == "user123"

    def test_verify_invalid_session(self):
        mgr = SessionManager(secret="testkey")
        assert mgr.verify_session("invalid-id") is None

    def test_destroy_session(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        mgr.destroy_session(session.session_id)
        assert mgr.verify_session(session.session_id) is None

    def test_csrf_token(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        token = mgr.generate_csrf_token(session)
        assert mgr.verify_csrf_token(token, session) is True

    def test_invalid_csrf_token(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        assert mgr.verify_csrf_token("invalid.token", session) is False

    def test_get_session_from_cookies(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        cookies = {SessionManager.COOKIE_NAME: session.session_id}
        result = mgr.get_session_from_cookies(cookies)
        assert result is not None
        assert result.user_id == "user123"

    def test_get_session_from_empty_cookies(self):
        mgr = SessionManager(secret="testkey")
        assert mgr.get_session_from_cookies({}) is None

    def test_cookie_header(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        header = mgr.get_cookie_header(session, secure=True)
        assert "HttpOnly" in header
        assert "SameSite=Lax" in header
        assert "Secure" in header

    def test_clear_cookie_header(self):
        mgr = SessionManager(secret="testkey")
        header = mgr.get_clear_cookie_header()
        assert "Max-Age=0" in header


class TestSession:
    def test_has_role(self):
        session = Session(
            session_id="test", user_id="u1",
            roles=["admin", "user"],
        )
        assert session.has_role("admin") is True
        assert session.has_role("superadmin") is False

    def test_can(self):
        session = Session(
            session_id="test", user_id="u1",
            permissions=["read", "write"],
        )
        assert session.can("read") is True
        assert session.can("delete") is False

    def test_to_client_safe(self):
        session = Session(
            session_id="ref-001", user_id="u1",
            user_data={"name": "John"},
            roles=["user"],
            permissions=["read"],
        )
        safe = session.to_client_safe()
        assert safe["loggedIn"] is True
        assert safe["user"] == {"name": "John"}
        assert safe["roles"] == ["user"]
        assert "session_id" not in safe


class TestAuthMiddleware:
    def test_unauthorized_request(self):
        mgr = SessionManager(secret="testkey")
        mw = AuthMiddleware(mgr)
        mw.add_rule(AuthRule(match="/dashboard/**", required=True, redirect="/login"))
        result = mw.check("/dashboard", {})
        assert result["authorized"] is False
        assert result["redirect"] == "/login"

    def test_authorized_request(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123")
        mw = AuthMiddleware(mgr)
        mw.add_rule(AuthRule(match="/dashboard/**", required=True))
        result = mw.check("/dashboard", {SessionManager.COOKIE_NAME: session.session_id})
        assert result["authorized"] is True

    def test_no_matching_rule_allows(self):
        mgr = SessionManager(secret="testkey")
        mw = AuthMiddleware(mgr)
        result = mw.check("/public", {})
        assert result["authorized"] is True

    def test_role_check(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123", roles=["user"])
        mw = AuthMiddleware(mgr)
        mw.add_rule(AuthRule(match="/admin/**", required=True, roles=["admin"]))
        result = mw.check("/admin", {SessionManager.COOKIE_NAME: session.session_id})
        assert result["authorized"] is False

    def test_role_check_pass(self):
        mgr = SessionManager(secret="testkey")
        session = mgr.create_session("user123", roles=["admin"])
        mw = AuthMiddleware(mgr)
        mw.add_rule(AuthRule(match="/admin/**", required=True, roles=["admin"]))
        result = mw.check("/admin", {SessionManager.COOKIE_NAME: session.session_id})
        assert result["authorized"] is True


class TestAuthClient:
    def test_from_session(self):
        session = Session(
            session_id="test", user_id="u1",
            user_data={"name": "John"},
            roles=["user"],
            permissions=["read"],
        )
        client = AuthClient.from_session(session)
        assert client.logged_in is True
        assert client.user == {"name": "John"}

    def test_from_no_session(self):
        client = AuthClient.from_session(None)
        assert client.logged_in is False

    def test_to_client_config(self):
        client = AuthClient(
            user={"name": "John"},
            logged_in=True,
            roles=["user"],
        )
        config = client.to_client_config()
        assert config["loggedIn"] is True
        assert config["user"] == {"name": "John"}


class TestAuthRuntime:
    def test_get_auth_client_runtime_js(self):
        from tw_framework.tw_auth.runtime import get_auth_client_runtime_js
        js = get_auth_client_runtime_js()
        assert "__tw.auth" in js
        assert "login" in js
        assert "logout" in js
        assert "hasRole" in js

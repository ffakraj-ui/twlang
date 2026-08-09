"""Tests for server actions."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.server_actions import (
    ActionRegistry, ServerAction, handle_action_request,
    get_action_registry, register_action,
)


class TestActionRegistry:
    def test_register_action(self):
        registry = ActionRegistry()
        registry.register("test_action", lambda args, session=None: {"ok": True})
        assert "test_action" in registry.list_actions()

    def test_get_action(self):
        registry = ActionRegistry()
        registry.register("test_action", lambda args, session=None: {"ok": True})
        action = registry.get("test_action")
        assert action is not None
        assert action.name == "test_action"

    def test_get_unknown_action(self):
        registry = ActionRegistry()
        assert registry.get("nonexistent") is None

    def test_execute_action(self):
        registry = ActionRegistry()
        registry.register(
            "create_post",
            lambda args, session=None: {"id": 1, "title": args.get("title")},
            require_auth=False,
            require_csrf=False,
        )
        result = registry.execute("create_post", {"title": "Hello"}, session=None, csrf_token="")
        assert result["ok"] is True
        assert result["data"]["title"] == "Hello"

    def test_execute_unknown_action(self):
        registry = ActionRegistry()
        result = registry.execute("unknown", {}, session=None, csrf_token="")
        assert result["ok"] is False
        assert result["status"] == 404

    def test_execute_requires_auth(self):
        registry = ActionRegistry()
        registry.register("secret", lambda args, session=None: "data", require_auth=True, require_csrf=False)
        result = registry.execute("secret", {}, session=None, csrf_token="")
        assert result["ok"] is False
        assert result["status"] == 401

    def test_execute_requires_csrf(self):
        registry = ActionRegistry()
        registry.register("protected", lambda args, session=None: "data", require_auth=False, require_csrf=True)
        result = registry.execute("protected", {}, session=None, csrf_token="")
        assert result["ok"] is False
        assert result["status"] == 403

    def test_validate_args(self):
        registry = ActionRegistry()
        registry.register(
            "create_user",
            lambda args, session=None: {"created": True},
            schema={"name": {"required": True, "type": "string"}},
            require_auth=False,
            require_csrf=False,
        )
        result = registry.execute("create_user", {}, session=None, csrf_token="")
        assert result["ok"] is False
        assert "Missing required field" in result["error"]

    def test_validate_args_type(self):
        registry = ActionRegistry()
        registry.register(
            "set_age",
            lambda args, session=None: {"ok": True},
            schema={"age": {"required": True, "type": "number"}},
            require_auth=False,
            require_csrf=False,
        )
        result = registry.execute("set_age", {"age": "not-a-number"}, session=None, csrf_token="")
        assert result["ok"] is False
        assert "must be a number" in result["error"]


class TestHandleActionRequest:
    def test_missing_action_name(self):
        result = handle_action_request({"args": {}}, {})
        assert result["status"] == 400

    def test_unknown_action(self):
        result = handle_action_request(
            {"action": "unknown", "args": {}, "csrf": "token"},
            {},
        )
        import json
        data = json.loads(result["body"])
        assert data["ok"] is False


class TestActionRegistration:
    def teardown_method(self):
        """Clean up global registry."""
        registry = get_action_registry()
        registry._actions.clear()

    def test_global_register(self):
        register_action(
            "global_test",
            lambda args, session=None: {"ok": True},
            require_auth=False,
            require_csrf=False,
        )
        registry = get_action_registry()
        assert "global_test" in registry.list_actions()

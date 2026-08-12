"""Tests for tw/state global state management."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_state.store import (
    Store, create_store, get_store, get_all_stores,
    get_client_stores, clear_stores, derived,
)


class TestStore:
    def setup_method(self):
        clear_stores()

    def test_create_store(self):
        store = create_store("user", {"name": "", "loggedIn": False})
        assert store.name == "user"
        assert store.get() == {"name": "", "loggedIn": False}

    def test_store_set(self):
        store = create_store("counter", {"count": 0})
        store.set({"count": 5})
        assert store.get()["count"] == 5

    def test_store_update(self):
        store = create_store("counter", {"count": 0})
        store.update(lambda s: {**s, "count": s["count"] + 1})
        assert store.get()["count"] == 1

    def test_store_subscribe(self):
        store = create_store("counter", {"count": 0})
        received = []
        unsub = store.subscribe(lambda s: received.append(s["count"]))
        store.set({"count": 42})
        assert len(received) == 1
        assert received[0] == 42

    def test_store_unsubscribe(self):
        store = create_store("counter", {"count": 0})
        received = []
        unsub = store.subscribe(lambda s: received.append(s["count"]))
        unsub()
        store.set({"count": 99})
        assert len(received) == 0

    def test_store_to_client_config(self):
        store = create_store("user", {"name": "John"}, persist=True)
        config = store.to_client_config()
        assert config["name"] == "user"
        assert config["initialState"] == {"name": "John"}
        assert config["persist"] is True

    def test_get_store(self):
        store = create_store("test", {"value": 1})
        assert get_store("test") is store

    def test_get_all_stores(self):
        create_store("a", {"x": 1})
        create_store("b", {"y": 2})
        all_stores = get_all_stores()
        assert "a" in all_stores
        assert "b" in all_stores

    def test_get_client_stores_excludes_server_only(self):
        create_store("client_store", {"x": 1})
        create_store("server_store", {"y": 2})
        get_store("server_store")._server_only = True
        client_stores = get_client_stores()
        names = [s["name"] for s in client_stores]
        assert "client_store" in names
        assert "server_store" not in names


class TestDerived:
    def setup_method(self):
        clear_stores()

    def test_derived_state(self):
        store1 = create_store("a", {"value": 10})
        store2 = create_store("b", {"value": 20})
        d = derived([store1, store2], lambda a, b: a["value"] + b["value"])
        assert d.get() == 30

    def test_derived_updates_on_change(self):
        store = create_store("counter", {"count": 5})
        d = derived([store], lambda s: s["count"] * 2)
        assert d.get() == 10
        store.set({"count": 7})
        assert d.get() == 14

    def test_derived_subscribe(self):
        store = create_store("counter", {"count": 1})
        d = derived([store], lambda s: s["count"] * 3)
        received = []
        d.subscribe(lambda v: received.append(v))
        store.set({"count": 2})
        assert len(received) == 1
        assert received[0] == 6


class TestStateRuntime:
    def test_get_state_runtime_js(self):
        from tw_framework.tw_state.runtime import get_state_runtime_js
        js = get_state_runtime_js()
        assert "__tw.store" in js
        assert "__tw.derived" in js

    def test_generate_state_init_script(self):
        from tw_framework.tw_state.runtime import generate_state_init_script
        stores = [
            {"name": "user", "initialState": {"name": "John"}, "persist": False},
        ]
        js = generate_state_init_script(stores)
        assert "var user = __tw.store" in js
        assert "John" in js

"""Tests for tw/fetch data fetching."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tw_framework.tw_fetch.fetch import FetchCache, fetch_server, deduplicate


class TestFetchCache:
    def test_set_and_get(self):
        cache = FetchCache()
        cache.set("key1", {"data": "hello"})
        assert cache.get("key1") == {"data": "hello"}

    def test_get_missing(self):
        cache = FetchCache()
        assert cache.get("nonexistent") is None

    def test_invalidate(self):
        cache = FetchCache()
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_all(self):
        cache = FetchCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_ttl_expiry(self):
        cache = FetchCache()
        cache.set("key1", "value1")
        # With TTL=0.001, should expire quickly
        import time
        time.sleep(0.01)
        assert cache.get("key1", ttl=0.001) is None

    def test_deduplication(self):
        cache = FetchCache()
        assert cache.is_pending("key1") is False
        cache.set_pending("key1", None)
        assert cache.is_pending("key1") is True
        cache.clear_pending("key1")
        assert cache.is_pending("key1") is False


class TestFetchServer:
    def test_fetch_server_error(self):
        # Fetching a non-existent URL should return error
        result = fetch_server("http://localhost:1/nonexistent", timeout=1)
        assert result["ok"] is False
        assert result["data"] is None


class TestDeduplicate:
    def test_deduplicate(self):
        call_count = [0]
        def fetch_fn():
            call_count[0] += 1
            return {"data": "hello"}
        result1 = deduplicate("url1", fetch_fn)
        assert result1 == {"data": "hello"}
        assert call_count[0] == 1


class TestFetchRuntime:
    def test_get_fetch_runtime_js(self):
        from tw_framework.tw_fetch.runtime import get_fetch_runtime_js
        js = get_fetch_runtime_js()
        assert "__tw.fetch" in js
        assert "invalidate" in js

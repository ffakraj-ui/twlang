"""
Four-Tier Caching System for TW Framework.

Inspired by Next.js caching architecture — four independent cache layers
that work together to minimize redundant work:

1. Request Memoization (per-request)
   - Deduplicates identical fetch() calls within a single request
   - Lifespan: single request (cleared after response sent)
   - Purpose: avoid double-fetching same URL in one request

2. Data Cache (persistent)
   - Caches fetch() responses across requests
   - Lifespan: persistent (until revalidated/expired)
   - Purpose: avoid re-fetching same URL across requests
   - Invalidation: TTL, on-demand via tags, manual purge

3. Full Route Cache (persistent)
   - Caches fully rendered HTML for static/SSR routes
   - Lifespan: persistent (until revalidated)
   - Purpose: serve prerendered pages instantly
   - Invalidation: on-demand revalidation, deploy, content change

4. Router Cache (client-side, in-memory)
   - Caches route components in browser memory for instant back/forward
   - Lifespan: browser session (30s default, refreshed on navigation)
   - Purpose: instant navigation to previously visited routes

Each tier is independent — invalidating one does not invalidate others
unless explicitly configured.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import gzip
import urllib
import urllib

logger = logging.getLogger(__name__)


# ── Tier 1: Request Memoization ─────────────────────────────────────

class RequestMemoization:
    """Tier 1 — per-request deduplication of fetch() calls.

    Within a single HTTP request, if the same URL is fetched multiple times,
    only the first fetch executes — subsequent calls return the cached result.

    Cleared automatically at the end of each request.
    """

    _thread_local = threading.local()

    @classmethod
    def _get_store(cls) -> Dict[str, Any]:
        """Get the per-request memo store (thread-local)."""
        if not hasattr(cls._thread_local, "store"):
            cls._thread_local.store = {}
        return cls._thread_local.store

    @classmethod
    def memoize(cls, key: str, fetch_fn: Callable[[], Any]) -> Any:
        """Execute fetch_fn only if key not already memoized."""
        store = cls._get_store()
        if key in store:
            logger.debug("Request memoization hit: %s", key)
            return store[key]
        result = fetch_fn()
        store[key] = result
        return result

    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        """Get a memoized value."""
        return cls._get_store().get(key)

    @classmethod
    def has(cls, key: str) -> bool:
        return key in cls._get_store()

    @classmethod
    def clear(cls) -> None:
        """Clear all memoized values — called at end of request."""
        cls._thread_local.store = {}

    @classmethod
    def start_request(cls) -> None:
        """Initialize a fresh memo store for a new request."""
        cls._thread_local.store = {}

    @classmethod
    def end_request(cls) -> None:
        """Clear memo store after request completes."""
        cls._thread_local.store = {}


# ── Tier 2: Data Cache (persistent fetch cache) ──────────────────────

@dataclass
class DataCacheEntry:
    """A single data cache entry."""
    data: Any
    cached_at: float
    revalidate: int = 0  # 0 = no revalidation, >0 = seconds
    tags: List[str] = field(default_factory=list)


class DataCache:
    """Tier 2 — persistent cache for fetch() responses.

    Caches HTTP responses across requests. Supports:
    - TTL-based expiration (revalidate)
    - Tag-based invalidation (on-demand revalidation)
    - Disk-backed persistence
    """

    def __init__(self, cache_dir: str = ""):
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".tw", "data-cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._memory_cache: Dict[str, DataCacheEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}  # tag → set of cache keys
        self._lock = threading.Lock()

    def _make_key(self, url: str, options: Optional[dict] = None) -> str:
        """Create a cache key from URL and options."""
        raw = url + json.dumps(options or {}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, url: str, options: Optional[dict] = None) -> Optional[Any]:
        """Get cached response if fresh."""
        key = self._make_key(url, options)

        with self._lock:
            # Check memory cache
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if entry.revalidate > 0 and (time.time() - entry.cached_at) > entry.revalidate:
                    # Stale — need revalidation
                    return None
                logger.debug("Data cache hit (memory): %s", url)
                return entry.data

        # Check disk cache
        disk_path = os.path.join(self.cache_dir, key + ".json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r") as f:
                    data = json.load(f)
                entry = DataCacheEntry(
                    data=data.get("data"),
                    cached_at=data.get("cached_at", 0),
                    revalidate=data.get("revalidate", 0),
                    tags=data.get("tags", []),
                )
                if entry.revalidate > 0 and (time.time() - entry.cached_at) > entry.revalidate:
                    return None  # Stale
                # Promote to memory cache
                with self._lock:
                    self._memory_cache[key] = entry
                    for tag in entry.tags:
                        self._tag_index.setdefault(tag, set()).add(key)
                logger.debug("Data cache hit (disk): %s", url)
                return entry.data
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def set(self, url: str, data: Any, options: Optional[dict] = None,
            revalidate: int = 0, tags: Optional[List[str]] = None) -> None:
        """Store a response in the cache."""
        key = self._make_key(url, options)
        entry = DataCacheEntry(
            data=data,
            cached_at=time.time(),
            revalidate=revalidate,
            tags=tags or [],
        )

        with self._lock:
            self._memory_cache[key] = entry
            for tag in entry.tags:
                self._tag_index.setdefault(tag, set()).add(key)

        # Persist to disk
        disk_path = os.path.join(self.cache_dir, key + ".json")
        try:
            with open(disk_path, "w") as f:
                json.dump({
                    "data": data,
                    "cached_at": entry.cached_at,
                    "revalidate": revalidate,
                    "tags": tags or [],
                }, f)
        except OSError:
            pass

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a given tag.

        For on-demand revalidation.
        Returns number of invalidated entries.
        """
        count = 0
        with self._lock:
            keys = self._tag_index.pop(tag, set())
            for key in keys:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    count += 1
        # Also remove from disk
        for key in keys:
            disk_path = os.path.join(self.cache_dir, key + ".json")
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                    count += 1
                except OSError:
                    pass
        logger.info("Data cache: invalidated %d entries for tag '%s'", count, tag)
        return count

    def clear(self) -> None:
        """Clear all data cache entries."""
        with self._lock:
            self._memory_cache.clear()
            self._tag_index.clear()
        # Clear disk
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self.cache_dir, fname))
                except OSError:
                    pass

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            return {
                "memory_entries": len(self._memory_cache),
                "tag_count": len(self._tag_index),
                "disk_entries": len([f for f in os.listdir(self.cache_dir) if f.endswith(".json")]),
            }


# ── Tier 3: Full Route Cache (prerendered HTML cache) ────────────────

@dataclass
class RouteCacheEntry:
    """A single route cache entry."""
    html: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    cached_at: float = field(default_factory=time.time)
    revalidate: int = 0
    tags: List[str] = field(default_factory=list)


class FullRouteCache:
    """Tier 3 — caches fully rendered HTML for routes.

    For static (SSG) and ISR routes, the entire HTML output is cached
    so it can be served instantly without re-rendering.

    Supports:
    - TTL-based revalidation (ISR)
    - Tag-based on-demand revalidation
    - Stale-while-revalidate (serve stale, refresh in background)
    """

    def __init__(self, cache_dir: str = ""):
        self.cache_dir = cache_dir or os.path.join(os.getcwd(), ".tw", "route-cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._memory_cache: Dict[str, RouteCacheEntry] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def _make_key(self, route_path: str, params: Optional[dict] = None) -> str:
        raw = route_path + json.dumps(params or {}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, route_path: str, params: Optional[dict] = None) -> Optional[RouteCacheEntry]:
        """Get cached route HTML if fresh."""
        key = self._make_key(route_path, params)

        with self._lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if entry.revalidate > 0 and (time.time() - entry.cached_at) > entry.revalidate:
                    # Stale — return for stale-while-revalidate, but mark as stale
                    logger.debug("Route cache stale: %s", route_path)
                    return entry  # Caller can decide to revalidate
                return entry

        # Check disk
        disk_path = os.path.join(self.cache_dir, key + ".json")
        if os.path.exists(disk_path):
            try:
                with open(disk_path, "r") as f:
                    data = json.load(f)
                entry = RouteCacheEntry(
                    html=data.get("html", ""),
                    status_code=data.get("status_code", 200),
                    headers=data.get("headers", {}),
                    cached_at=data.get("cached_at", 0),
                    revalidate=data.get("revalidate", 0),
                    tags=data.get("tags", []),
                )
                with self._lock:
                    self._memory_cache[key] = entry
                    for tag in entry.tags:
                        self._tag_index.setdefault(tag, set()).add(key)
                return entry
            except (json.JSONDecodeError, OSError):
                pass

        return None

    def set(self, route_path: str, html: str, status_code: int = 200,
            headers: Optional[dict] = None, revalidate: int = 0,
            tags: Optional[List[str]] = None, params: Optional[dict] = None) -> None:
        """Store rendered HTML in route cache."""
        key = self._make_key(route_path, params)
        entry = RouteCacheEntry(
            html=html,
            status_code=status_code,
            headers=headers or {},
            revalidate=revalidate,
            tags=tags or [],
        )

        with self._lock:
            self._memory_cache[key] = entry
            for tag in entry.tags:
                self._tag_index.setdefault(tag, set()).add(key)

        # Persist to disk
        disk_path = os.path.join(self.cache_dir, key + ".json")
        try:
            with open(disk_path, "w") as f:
                json.dump({
                    "html": html,
                    "status_code": status_code,
                    "headers": headers or {},
                    "cached_at": entry.cached_at,
                    "revalidate": revalidate,
                    "tags": tags or [],
                }, f)
        except OSError:
            pass

    def is_stale(self, route_path: str, params: Optional[dict] = None) -> bool:
        """Check if a cached route is stale (needs revalidation)."""
        key = self._make_key(route_path, params)
        with self._lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]
                if entry.revalidate > 0 and (time.time() - entry.cached_at) > entry.revalidate:
                    return True
        return False

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all route cache entries with a given tag."""
        count = 0
        with self._lock:
            keys = self._tag_index.pop(tag, set())
            for key in keys:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    count += 1
        for key in keys:
            disk_path = os.path.join(self.cache_dir, key + ".json")
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    pass
        logger.info("Route cache: invalidated %d entries for tag '%s'", count, tag)
        return count

    def clear(self) -> None:
        with self._lock:
            self._memory_cache.clear()
            self._tag_index.clear()
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self.cache_dir, fname))
                except OSError:
                    pass

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "memory_entries": len(self._memory_cache),
                "tag_count": len(self._tag_index),
                "disk_entries": len([f for f in os.listdir(self.cache_dir) if f.endswith(".json")]),
            }


# ── Tier 4: Router Cache (client-side) ───────────────────────────────

class RouterCache:
    """Tier 4 — client-side route component cache.

    Caches rendered route components in browser memory for instant
    back/forward navigation. This is implemented as JavaScript that
    runs in the browser — the Python class generates the JS runtime.

    Features:
    - LRU eviction (max 10 routes cached)
    - 30s stale timer (configurable)
    - Prefetch on hover/viewport
    - Refreshed on navigation
    """

    @staticmethod
    def get_runtime_js(max_entries: int = 10, stale_ms: int = 30000) -> str:
        """Generate the client-side router cache JavaScript.

        This JS is injected into pages that use client-side routing.
        """
        return f"""<script>
(function() {{
  var _twRouterCache = {{}};
  var _twRouterKeys = [];
  var _maxEntries = {max_entries};
  var _staleMs = {stale_ms};

  window.__twRouterCache = {{
    get: function(path) {{
      var entry = _twRouterCache[path];
      if (!entry) return null;
      if (Date.now() - entry.cachedAt > _staleMs) {{
        delete _twRouterCache[path];
        _twRouterKeys = _twRouterKeys.filter(function(k) {{ return k !== path; }});
        return null;
      }}
      return entry.html;
    }},
    set: function(path, html) {{
      if (_twRouterCache[path]) {{
        _twRouterKeys = _twRouterKeys.filter(function(k) {{ return k !== path; }});
      }}
      _twRouterCache[path] = {{ html: html, cachedAt: Date.now() }};
      _twRouterKeys.push(path);
      // LRU eviction
      while (_twRouterKeys.length > _maxEntries) {{
        var oldest = _twRouterKeys.shift();
        delete _twRouterCache[oldest];
      }}
    }},
    has: function(path) {{
      var entry = _twRouterCache[path];
      if (!entry) return false;
      if (Date.now() - entry.cachedAt > _staleMs) {{
        delete _twRouterCache[path];
        _twRouterKeys = _twRouterKeys.filter(function(k) {{ return k !== path; }});
        return false;
      }}
      return true;
    }},
    clear: function() {{
      _twRouterCache = {{}};
      _twRouterKeys = [];
    }},
    size: function() {{
      return _twRouterKeys.length;
    }}
  }};
}})();
</script>"""


# ── Unified Cache Manager ────────────────────────────────────────────

class CacheManager:
    """Unified manager for all four cache tiers.

    Provides a single interface to interact with all cache layers:
    - Request Memoization (Tier 1)
    - Data Cache (Tier 2)
    - Full Route Cache (Tier 3)
    - Router Cache (Tier 4, JS generation only)

    Also provides on-demand revalidation via tags.
    """

    def __init__(self, project_root: str = ""):
        base_dir = os.path.join(project_root or os.getcwd(), ".tw")
        self.memo = RequestMemoization()
        self.data_cache = DataCache(os.path.join(base_dir, "data-cache"))
        self.route_cache = FullRouteCache(os.path.join(base_dir, "route-cache"))
        self.router_cache = RouterCache()

    def start_request(self) -> None:
        """Initialize per-request caches."""
        self.memo.start_request()

    def end_request(self) -> None:
        """Clean up per-request caches."""
        self.memo.end_request()

    def fetch_cached(self, url: str, fetch_fn: Callable[[], Any],
                     options: Optional[dict] = None,
                     revalidate: int = 0,
                     tags: Optional[List[str]] = None) -> Any:
        """Fetch with full cache hierarchy.

        1. Check Request Memoization (deduplicate within request)
        2. Check Data Cache (persistent, with revalidation)
        3. If not cached or stale, execute fetch_fn and cache result
        """
        # Tier 1: Request Memoization
        memo_key = f"fetch:{url}:{json.dumps(options or {}, sort_keys=True)}"

        def _do_fetch():
            # Tier 2: Data Cache
            cached = self.data_cache.get(url, options)
            if cached is not None:
                return cached

            # Execute actual fetch
            result = fetch_fn()

            # Cache result
            self.data_cache.set(url, result, options, revalidate=revalidate, tags=tags)

            return result

        return self.memo.memoize(memo_key, _do_fetch)

    def get_route(self, route_path: str, params: Optional[dict] = None) -> Optional[RouteCacheEntry]:
        """Get cached route HTML (Tier 3)."""
        return self.route_cache.get(route_path, params)

    def set_route(self, route_path: str, html: str, **kwargs) -> None:
        """Store route HTML in cache (Tier 3)."""
        self.route_cache.set(route_path, html, **kwargs)

    def revalidate_tag(self, tag: str) -> Dict[str, int]:
        """On-demand revalidation — invalidate entries with a tag across all tiers.

        Returns a dict of {tier: count} showing how many entries were invalidated.
        """
        data_count = self.data_cache.invalidate_tag(tag)
        route_count = self.route_cache.invalidate_tag(tag)
        logger.info("Revalidation tag '%s': data=%d, routes=%d", tag, data_count, route_count)
        return {"data_cache": data_count, "route_cache": route_count}

    def clear_all(self) -> None:
        """Clear all cache tiers."""
        self.memo.clear()
        self.data_cache.clear()
        self.route_cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Return statistics for all cache tiers."""
        return {
            "tier_1_request_memo": "active" if hasattr(self.memo._thread_local, "store") else "inactive",
            "tier_2_data_cache": self.data_cache.stats(),
            "tier_3_route_cache": self.route_cache.stats(),
            "tier_4_router_cache": "client-side (JS runtime)",
        }


__all__ = [
    "RequestMemoization", "DataCache", "RedisDataCache", "FullRouteCache", "RouterCache",
    "CacheManager", "DataCacheEntry", "RouteCacheEntry",
    "SSRCacheIntegration", "CacheInvalidationAPI", "CacheKeyBuilder",
    "CacheWarmingManager", "CacheMiddleware", "create_cache_manager_with_redis",
    "CacheMetric", "CacheMetricsCollector", "CacheCompression",
    "CacheMigrationManager", "CacheHealthMonitor", "CacheGarbageCollector",
]


# ── Redis-backed Data Cache Extension ────────────────────────────────

class RedisDataCache(DataCache):
    """Redis-backed Data Cache with automatic fallback to disk.

    If Redis is unavailable, falls back to the parent DataCache
    (memory + disk). This provides distributed caching across
    multiple server instances.
    """

    def __init__(self, cache_dir: str = "", redis_url: str = "",
                 redis_prefix: str = "tw:data:"):
        super().__init__(cache_dir)
        self._redis = None
        self._redis_prefix = redis_prefix
        self._redis_available = False

        if redis_url:
            try:
                import redis as _redis
                self._redis = _redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                self._redis_available = True
                logger.info("Redis Data Cache connected: %s", redis_url)
            except ImportError:
                logger.warning("redis package not installed — falling back to disk cache")
            except Exception as e:
                logger.warning("Redis connection failed: %s — falling back to disk cache", e)

    def _redis_key(self, url: str, options: Optional[dict] = None) -> str:
        """Create Redis key from URL and options."""
        raw = url + json.dumps(options or {}, sort_keys=True)
        return self._redis_prefix + hashlib.sha256(raw.encode()).hexdigest()

    def get(self, url: str, options: Optional[dict] = None) -> Optional[Any]:
        """Get from Redis first, then fall back to disk."""
        # Try Redis
        if self._redis_available:
            try:
                redis_key = self._redis_key(url, options)
                raw = self._redis.get(redis_key)
                if raw:
                    data = json.loads(raw)
                    cached_at = data.get("cached_at", 0)
                    revalidate = data.get("revalidate", 0)
                    if revalidate > 0 and (time.time() - cached_at) > revalidate:
                        # Stale — remove from Redis
                        self._redis.delete(redis_key)
                    else:
                        return data.get("data")
            except Exception as e:
                logger.warning("Redis get failed: %s — falling back to disk", e)

        # Fall back to parent (disk + memory)
        return super().get(url, options)

    def set(self, url: str, data: Any, options: Optional[dict] = None,
            revalidate: int = 0, tags: Optional[List[str]] = None) -> None:
        """Store in both Redis and disk."""
        # Store in Redis
        if self._redis_available:
            try:
                redis_key = self._redis_key(url, options)
                payload = {
                    "data": data,
                    "cached_at": time.time(),
                    "revalidate": revalidate,
                    "tags": tags or [],
                    "url": url,
                }
                ttl = revalidate if revalidate > 0 else None
                self._redis.setex(redis_key, ttl or 86400, json.dumps(payload))

                # Index tags in Redis
                if tags:
                    for tag in tags:
                        tag_key = f"{self._redis_prefix}tag:{tag}"
                        self._redis.sadd(tag_key, redis_key)
                        if ttl:
                            self._redis.expire(tag_key, ttl)
            except Exception as e:
                logger.warning("Redis set failed: %s — using disk only", e)

        # Also store in disk (parent)
        super().set(url, data, options, revalidate, tags)

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate by tag in Redis and disk."""
        count = 0

        # Redis invalidation
        if self._redis_available:
            try:
                tag_key = f"{self._redis_prefix}tag:{tag}"
                keys = self._redis.smembers(tag_key)
                if keys:
                    for key in keys:
                        self._redis.delete(key)
                        count += 1
                    self._redis.delete(tag_key)
                logger.info("Redis: invalidated %d entries for tag '%s'", count, tag)
            except Exception as e:
                logger.warning("Redis tag invalidation failed: %s", e)

        # Disk invalidation
        count += super().invalidate_tag(tag)
        return count

    def clear(self) -> None:
        """Clear Redis and disk caches."""
        if self._redis_available:
            try:
                for key in self._redis.scan_iter(f"{self._redis_prefix}*"):
                    self._redis.delete(key)
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)
        super().clear()

    def stats(self) -> Dict[str, Any]:
        """Return combined Redis + disk stats."""
        s = super().stats()
        s["redis"] = {
            "available": self._redis_available,
            "prefix": self._redis_prefix,
        }
        if self._redis_available:
            try:
                info = self._redis.info()
                s["redis"]["connected"] = True
                s["redis"]["used_memory_human"] = info.get("used_memory_human", "?")
                s["redis"]["keys"] = len(self._redis.keys(f"{self._redis_prefix}*"))
            except Exception:
                s["redis"]["connected"] = False
        return s


# ── SSR Cache Integration ────────────────────────────────────────────

class SSRCacheIntegration:
    """Integrates the 4-tier cache with the SSR server.

    Provides a clean interface for the production server to:
    1. Check route cache before rendering
    2. Render and cache if not cached
    3. Serve stale-while-revalidate
    4. Revalidate on-demand via tags
    5. Integrate with PPR for component-level caching
    """

    def __init__(self, cache_manager: "CacheManager"):
        self.cm = cache_manager
        self._revalidation_lock = threading.Lock()
        self._active_revalidations: Set[str] = set()

    def serve_route(self, route_path: str, render_fn: Callable[[], str],
                    params: Optional[dict] = None,
                    revalidate: int = 0,
                    tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Serve a route with full cache hierarchy.

        1. Check Full Route Cache (Tier 3)
        2. If cached and fresh → return immediately
        3. If cached and stale → return stale, trigger background revalidation
        4. If not cached → render, cache, return

        Returns dict with html, status, from_cache, revalidated.
        """
        # Check cache
        entry = self.cm.route_cache.get(route_path, params)

        if entry is not None:
            is_stale = self.cm.route_cache.is_stale(route_path, params)
            if not is_stale:
                # Fresh cache hit
                return {
                    "html": entry.html,
                    "status": entry.status_code,
                    "headers": entry.headers,
                    "from_cache": True,
                    "revalidated": False,
                }
            else:
                # Stale — serve stale, trigger background revalidation
                # Stale-while-revalidate pattern
                if route_path not in self._active_revalidations:
                    threading.Thread(
                        target=self._background_revalidate,
                        args=(route_path, render_fn, params, revalidate, tags),
                        daemon=True,
                    ).start()

                return {
                    "html": entry.html,
                    "status": entry.status_code,
                    "headers": entry.headers,
                    "from_cache": True,
                    "revalidated": False,
                    "stale": True,
                }

        # Not cached — render and cache
        html = render_fn()
        self.cm.route_cache.set(
            route_path, html, status_code=200,
            revalidate=revalidate, tags=tags, params=params,
        )

        return {
            "html": html,
            "status": 200,
            "from_cache": False,
            "revalidated": False,
        }

    def _background_revalidate(self, route_path: str, render_fn: Callable,
                                params: Optional[dict], revalidate: int,
                                tags: Optional[List[str]]) -> None:
        """Background revalidation — render and update cache."""
        with self._revalidation_lock:
            if route_path in self._active_revalidations:
                return
            self._active_revalidations.add(route_path)

        try:
            html = render_fn()
            self.cm.route_cache.set(
                route_path, html, status_code=200,
                revalidate=revalidate, tags=tags, params=params,
            )
            logger.info("Background revalidation complete: %s", route_path)
        except Exception as e:
            logger.error("Background revalidation failed for %s: %s", route_path, e)
        finally:
            self._active_revalidations.discard(route_path)

    def revalidate_path(self, route_path: str) -> bool:
        """Force revalidation of a specific route.

        Removes the route from cache so it's re-rendered on next request.
        """
        # Find and remove the cache key
        key = self.cm.route_cache._make_key(route_path)
        with self.cm.route_cache._lock:
            if key in self.cm.route_cache._memory_cache:
                del self.cm.route_cache._memory_cache[key]
                # Remove from disk
                disk_path = os.path.join(
                    self.cm.route_cache.cache_dir,
                    hashlib.sha256(key.encode()).hexdigest() + ".json"
                )
                if os.path.exists(disk_path):
                    try:
                        os.remove(disk_path)
                    except OSError:
                        pass
                logger.info("Route revalidated: %s", route_path)
                return True
        return False

    def revalidate_tags(self, tags: List[str]) -> Dict[str, int]:
        """Revalidate all cache entries with given tags."""
        results: Dict[str, int] = {}
        for tag in tags:
            results[tag] = self.cm.revalidate_tag(tag).get("route_cache", 0)
        return results

    def warm_route_cache(self, route_path: str, render_fn: Callable,
                         revalidate: int = 0, tags: Optional[List[str]] = None) -> None:
        """Pre-render and cache a route (cache warming)."""
        html = render_fn()
        self.cm.route_cache.set(
            route_path, html, revalidate=revalidate, tags=tags
        )
        logger.info("Route cache warmed: %s", route_path)

    def get_stats(self) -> Dict[str, Any]:
        """Return comprehensive cache stats."""
        return {
            "cache_tiers": self.cm.stats(),
            "active_revalidations": len(self._active_revalidations),
            "revalidating_routes": list(self._active_revalidations),
        }


# ── Cache Invalidation API ──────────────────────────────────────────

class CacheInvalidationAPI:
    """HTTP API for on-demand cache invalidation.

    Endpoints:
      POST /__tw/revalidate       — revalidate by tag or path
      POST /__tw/revalidate/path   — revalidate a specific path
      POST /__tw/revalidate/tag    — revalidate by tag
      POST /__tw/revalidate/all    — clear all caches
      GET  /__tw/cache/stats       — get cache statistics
    """

    def __init__(self, cache_manager: "CacheManager"):
        self.cm = cache_manager
        self.ssr = SSRCacheIntegration(cache_manager)

    def handle_request(self, method: str, path: str,
                       body: Optional[dict] = None) -> Dict[str, Any]:
        """Handle a cache invalidation API request.

        Returns a response dict with status, body, content_type.
        """
        if method == "GET" and path == "/__tw/cache/stats":
            return self._stats_response()

        if method != "POST":
            return self._error(405, "Method not allowed")

        body = body or {}

        if path == "/__tw/revalidate":
            # Support both tag and path revalidation
            tags = body.get("tags", [])
            paths = body.get("paths", [])

            invalidated = {"tags": {}, "paths": {}}
            for tag in tags:
                invalidated["tags"][tag] = self.cm.revalidate_tag(tag)
            for p in paths:
                invalidated["paths"][p] = self.ssr.revalidate_path(p)

            return self._json(200, {"ok": True, "invalidated": invalidated})

        elif path == "/__tw/revalidate/tag":
            tags = body.get("tags", [])
            results = {}
            for tag in tags:
                results[tag] = self.cm.revalidate_tag(tag)
            return self._json(200, {"ok": True, "invalidated": results})

        elif path == "/__tw/revalidate/path":
            route_path = body.get("path", "")
            if not route_path:
                return self._error(400, "Missing 'path' in body")
            success = self.ssr.revalidate_path(route_path)
            return self._json(200, {"ok": True, "revalidated": success, "path": route_path})

        elif path == "/__tw/revalidate/all":
            self.cm.clear_all()
            return self._json(200, {"ok": True, "message": "All caches cleared"})

        elif path == "/__tw/cache/warm":
            # Cache warming — caller provides route_path and render_fn
            # (render_fn can't be serialized, so this is typically called internally)
            return self._error(501, "Cache warming must be called internally, not via HTTP")

        return self._error(404, f"Unknown cache API endpoint: {path}")

    def _stats_response(self) -> Dict[str, Any]:
        """Return cache statistics."""
        stats = self.ssr.get_stats()
        return self._json(200, stats)

    def _json(self, status: int, data: dict) -> Dict[str, Any]:
        return {
            "status": status,
            "body": json.dumps(data, ensure_ascii=False).encode("utf-8"),
            "content_type": "application/json",
            "headers": {"Cache-Control": "no-store"},
        }

    def _error(self, status: int, message: str) -> Dict[str, Any]:
        return self._json(status, {"ok": False, "error": message})


# ── Cache Key Builder ───────────────────────────────────────────────

class CacheKeyBuilder:
    """Builds cache keys for various cache tiers.

    Provides consistent key generation across all tiers:
    - Route cache keys (path + params)
    - Data cache keys (URL + options)
    - Component cache keys (name + params)
    - PPR cache keys (component + params + tags)
    """

    @staticmethod
    def route_key(path: str, params: Optional[dict] = None) -> str:
        """Build a route cache key."""
        raw = f"route:{path}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def data_key(url: str, options: Optional[dict] = None) -> str:
        """Build a data cache key."""
        raw = f"data:{url}:{json.dumps(options or {}, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def component_key(name: str, params: Optional[dict] = None) -> str:
        """Build a component cache key."""
        raw = f"comp:{name}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def ppr_key(name: str, params: Optional[dict] = None,
                tags: Optional[List[str]] = None) -> str:
        """Build a PPR boundary cache key."""
        tag_str = ",".join(sorted(tags or []))
        raw = f"ppr:{name}:{json.dumps(params or {}, sort_keys=True)}:{tag_str}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def fetch_key(url: str, method: str = "GET",
                  body: Optional[str] = None) -> str:
        """Build a request memoization key."""
        raw = f"fetch:{method}:{url}:{body or ''}"
        return hashlib.sha256(raw.encode()).hexdigest()


# ── Cache Warming Manager ───────────────────────────────────────────

class CacheWarmingManager:
    """Manages cache warming — pre-rendering routes and components.

    Called at build time or deploy time to pre-populate caches:
    - Warm route cache for all static routes
    - Warm component cache for all PPR boundaries
    - Warm data cache for known API calls
    - Warm PPR cache for cached/streaming components
    """

    def __init__(self, cache_manager: "CacheManager"):
        self.cm = cache_manager
        self.ssr = SSRCacheIntegration(cache_manager)
        self._warmed: Dict[str, bool] = {}

    def warm_routes(self, routes: List[Dict[str, Any]],
                    render_fn: Callable[[str], str]) -> Dict[str, Any]:
        """Warm route cache for multiple routes.

        Args:
            routes: List of route dicts with path, revalidate, tags
            render_fn: Callable that takes route_path and returns HTML

        Returns:
            Summary dict with warmed count, errors, timing
        """
        import time as _time
        start = _time.time()
        warmed = 0
        errors = 0
        error_details: List[str] = []

        for route in routes:
            path = route.get("path", "")
            if not path or path in self._warmed:
                continue

            revalidate = route.get("revalidate", 0)
            tags = route.get("tags", [])

            try:
                self.ssr.warm_route_cache(path, lambda p=path: render_fn(p),
                                        revalidate=revalidate, tags=tags)
                self._warmed[path] = True
                warmed += 1
            except Exception as e:
                errors += 1
                error_details.append(f"{path}: {e}")
                logger.warning("Cache warming failed for %s: %s", path, e)

        elapsed = _time.time() - start
        return {
            "warmed": warmed,
            "errors": errors,
            "error_details": error_details[:10],  # First 10 errors
            "total_routes": len(routes),
            "elapsed_ms": round(elapsed * 1000, 2),
        }

    def warm_data_cache(self, fetch_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Warm data cache by pre-fetching URLs.

        Args:
            fetch_tasks: List of dicts with url, options, revalidate, tags
        """
        import time as _time
        start = _time.time()
        warmed = 0
        errors = 0

        for task in fetch_tasks:
            url = task.get("url", "")
            if not url:
                continue
            try:
                # Execute actual fetch
                import urllib.request
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                    data = text
                    ct = resp.headers.get("Content-Type", "")
                    if "application/json" in ct:
                        try:
                            data = json.loads(text)
                        except Exception:
                            pass

                    self.cm.data_cache.set(
                        url, data,
                        options=task.get("options"),
                        revalidate=task.get("revalidate", 0),
                        tags=task.get("tags", []),
                    )
                    warmed += 1
            except Exception as e:
                errors += 1
                logger.warning("Data cache warming failed for %s: %s", url, e)

        elapsed = _time.time() - start
        return {
            "warmed": warmed,
            "errors": errors,
            "total_urls": len(fetch_tasks),
            "elapsed_ms": round(elapsed * 1000, 2),
        }

    def get_warming_summary(self) -> Dict[str, Any]:
        """Return summary of warming status."""
        return {
            "routes_warmed": sum(1 for v in self._warmed.values() if v),
            "warmed_routes": [r for r, v in self._warmed.items() if v],
            "cache_stats": self.cm.stats(),
        }


# ── Cache Middleware ─────────────────────────────────────────────────

class CacheMiddleware:
    """Middleware that integrates caching into the request pipeline.

    Automatically:
    1. Starts request memoization at request start
    2. Checks route cache before rendering
    3. Serves cached content if fresh
    4. Triggers background revalidation if stale
    5. Caches rendered output
    6. Clears request memoization at request end
    """

    def __init__(self, cache_manager: "CacheManager"):
        self.cm = cache_manager
        self.ssr = SSRCacheIntegration(cache_manager)
        self._bypass_paths: Set[str] = set()

    def bypass(self, path: str) -> None:
        """Mark a path to bypass caching."""
        self._bypass_paths.add(path)

    def process_request(self, request: dict) -> Optional[dict]:
        """Process incoming request — returns cached response or None.

        If None is returned, the request continues to the handler.
        If a dict is returned, it's served as the response.
        """
        path = request.get("path", "")

        # Start request memoization
        self.cm.start_request()

        # Skip caching for bypassed paths
        if path in self._bypass_paths:
            return None

        # Skip caching for API routes (unless explicitly cached)
        if path.startswith("/api/") or path.startswith("/__tw/"):
            return None

        # Skip caching for non-GET requests
        if request.get("method", "GET") != "GET":
            return None

        # Check route cache
        entry = self.cm.route_cache.get(path)
        if entry is not None:
            is_stale = self.cm.route_cache.is_stale(path)
            if not is_stale:
                # Fresh cache hit
                return {
                    "status": entry.status_code,
                    "body": entry.html.encode("utf-8") if isinstance(entry.html, str) else entry.html,
                    "content_type": "text/html; charset=utf-8",
                    "headers": {**entry.headers, "X-Cache": "HIT"},
                }
            # Stale — continue to handler, will be re-cached

        return None

    def process_response(self, request: dict, response: dict) -> dict:
        """Process response — cache if appropriate."""
        path = request.get("path", "")
        method = request.get("method", "GET")

        # End request memoization
        self.cm.end_request()

        # Only cache GET requests
        if method != "GET":
            return response

        # Only cache successful responses
        status = response.get("status", 200)
        if status != 200:
            return response

        # Skip API routes
        if path.startswith("/api/") or path.startswith("/__tw/"):
            return response

        # Skip already-cached responses
        headers = response.get("headers", {})
        if isinstance(headers, dict) and headers.get("X-Cache") == "HIT":
            return response

        # Cache the response
        body = response.get("body", b"")
        if isinstance(body, bytes):
            html = body.decode("utf-8", errors="replace")
        else:
            html = str(body)

        response_headers = {}
        if isinstance(headers, dict):
            response_headers = {k: v for k, v in headers.items()
                              if k.lower() not in ("content-length", "transfer-encoding")}
        elif isinstance(headers, list):
            response_headers = {k: v for k, v in headers
                              if k.lower() not in ("content-length", "transfer-encoding")}

        self.cm.route_cache.set(path, html, status_code=status,
                                headers=response_headers)

        # Add X-Cache header
        if isinstance(response.get("headers"), dict):
            response["headers"]["X-Cache"] = "MISS"
        elif isinstance(response.get("headers"), list):
            response["headers"].append(("X-Cache", "MISS"))

        return response


# ── Update CacheManager with new features ───────────────────────────

# Extend CacheManager class with Redis support
def create_cache_manager_with_redis(project_root: str = "",
                                     redis_url: str = "") -> "CacheManager":
    """Create a CacheManager with Redis-backed data cache.

    Args:
        project_root: Project root directory
        redis_url: Redis connection URL (e.g. "redis://localhost:6379/0")

    Returns:
        CacheManager with RedisDataCache if Redis is available,
        falls back to standard DataCache otherwise.
    """
    cm = CacheManager(project_root)
    if redis_url:
        cm.data_cache = RedisDataCache(
            cache_dir=cm.data_cache.cache_dir,
            redis_url=redis_url,
        )
    return cm


# Update __all__


# ── Cache Metrics Collector ──────────────────────────────────────────

@dataclass
class CacheMetric:
    """A single cache metric data point."""
    timestamp: float
    tier: str               # "request_memo" | "data_cache" | "route_cache" | "router_cache"
    operation: str          # "get" | "set" | "invalidate" | "clear"
    hit: bool
    duration_ms: float
    key: str = ""
    tags: List[str] = field(default_factory=list)


class CacheMetricsCollector:
    """Collects detailed metrics across all cache tiers.

    Provides insights into:
    - Hit/miss rates per tier
    - Average operation latency
    - Most accessed keys
    - Tag invalidation frequency
    - Memory usage over time
    - TTL effectiveness
    """

    def __init__(self, max_entries: int = 50000):
        self._metrics: List[CacheMetric] = []
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}  # "tier_op_hit" → count
        self._latency_sum: Dict[str, float] = {}  # "tier_op" → total ms
        self._latency_count: Dict[str, int] = {}

    def record(self, tier: str, operation: str, hit: bool,
               duration_ms: float, key: str = "",
               tags: Optional[List[str]] = None) -> None:
        """Record a cache operation."""
        metric = CacheMetric(
            timestamp=time.time(),
            tier=tier,
            operation=operation,
            hit=hit,
            duration_ms=duration_ms,
            key=key[:200],  # Truncate for memory
            tags=tags or [],
        )

        with self._lock:
            self._metrics.append(metric)
            if len(self._metrics) > self._max_entries:
                self._metrics = self._metrics[-self._max_entries:]

            # Update counters
            counter_key = f"{tier}_{operation}_{'hit' if hit else 'miss'}"
            self._counters[counter_key] = self._counters.get(counter_key, 0) + 1

            # Update latency
            latency_key = f"{tier}_{operation}"
            self._latency_sum[latency_key] = self._latency_sum.get(latency_key, 0) + duration_ms
            self._latency_count[latency_key] = self._latency_count.get(latency_key, 0) + 1

    def get_hit_rate(self, tier: str = "") -> Dict[str, float]:
        """Get hit rate per tier."""
        results: Dict[str, float] = {}
        with self._lock:
            tiers = set(m.tier for m in self._metrics) if not tier else {tier}
            for t in tiers:
                hits = sum(1 for m in self._metrics if m.tier == t and m.hit)
                total = sum(1 for m in self._metrics if m.tier == t and m.operation == "get")
                results[t] = (hits / total * 100) if total > 0 else 0.0
        return results

    def get_avg_latency(self, tier: str = "") -> Dict[str, float]:
        """Get average latency per tier+operation."""
        results: Dict[str, float] = {}
        with self._lock:
            keys = [k for k in self._latency_sum if not tier or k.startswith(tier)]
            for k in keys:
                count = self._latency_count.get(k, 0)
                if count > 0:
                    results[k] = self._latency_sum[k] / count
        return results

    def get_top_keys(self, tier: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """Get most accessed keys."""
        with self._lock:
            key_counts: Dict[str, int] = {}
            for m in self._metrics:
                if tier and m.tier != tier:
                    continue
                if m.key:
                    key_counts[m.key] = key_counts.get(m.key, 0) + 1

        sorted_keys = sorted(key_counts.items(), key=lambda x: -x[1])[:limit]
        return [{"key": k, "count": v} for k, v in sorted_keys]

    def get_summary(self) -> Dict[str, Any]:
        """Return comprehensive metrics summary."""
        with self._lock:
            total_ops = len(self._metrics)
            tier_stats: Dict[str, Any] = {}

            for m in self._metrics:
                if m.tier not in tier_stats:
                    tier_stats[m.tier] = {"gets": 0, "sets": 0, "hits": 0, "misses": 0}
                if m.operation == "get":
                    tier_stats[m.tier]["gets"] += 1
                    if m.hit:
                        tier_stats[m.tier]["hits"] += 1
                    else:
                        tier_stats[m.tier]["misses"] += 1
                elif m.operation == "set":
                    tier_stats[m.tier]["sets"] += 1

            for t in tier_stats:
                gets = tier_stats[t]["gets"]
                tier_stats[t]["hit_rate"] = (
                    f"{tier_stats[t]['hits'] / gets * 100:.1f}%" if gets > 0 else "N/A"
                )

            return {
                "total_operations": total_ops,
                "counters": dict(self._counters),
                "tier_stats": tier_stats,
                "avg_latency_ms": self.get_avg_latency(),
                "top_keys": self.get_top_keys(limit=10),
                "metrics_stored": total_ops,
                "max_entries": self._max_entries,
            }

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._latency_sum.clear()
            self._latency_count.clear()

    def export_json(self, output_path: str = "") -> str:
        """Export metrics to JSON file."""
        import json as _json
        summary = self.get_summary()
        output_path = output_path or os.path.join(os.getcwd(), ".tw", "cache-metrics.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            with open(output_path, "w") as f:
                _json.dump(summary, f, indent=2, default=str)
        except OSError:
            pass
        return output_path


# ── Cache Compression Layer ──────────────────────────────────────────

class CacheCompression:
    """Compresses cache entries to save memory and disk space.

    Supports:
    - gzip compression (stdlib)
    -zlib compression (stdlib)
    - Automatic compression for entries above threshold
    - Transparent decompression on read
    """

    def __init__(self, algorithm: str = "gzip", min_size: int = 1024,
                 compression_level: int = 6):
        self.algorithm = algorithm
        self.min_size = min_size
        self.level = compression_level

    def compress(self, data: str) -> bytes:
        """Compress data if it exceeds the minimum size."""
        raw = data.encode("utf-8") if isinstance(data, str) else data

        if len(raw) < self.min_size:
            return raw  # Too small to benefit from compression

        if self.algorithm == "gzip":
            import gzip
            return gzip.compress(raw, compresslevel=self.level)
        elif self.algorithm == "zlib":
            import zlib
            return zlib.compress(raw, self.level)
        else:
            return raw

    def decompress(self, data: bytes) -> str:
        """Decompress data."""
        if not data:
            return ""

        # Try to detect if data is compressed
        if data[:2] == b"\x1f\x8b":  # gzip magic number
            import gzip
            try:
                return gzip.decompress(data).decode("utf-8", errors="replace")
            except Exception:
                pass

        if data[:2] == b"\x78\x9c" or data[:2] == b"\x78\x01":  # zlib header
            import zlib
            try:
                return zlib.decompress(data).decode("utf-8", errors="replace")
            except Exception:
                pass

        # Not compressed — return as-is
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return str(data)

    def get_compression_ratio(self, original: str) -> Dict[str, Any]:
        """Get compression ratio for a given string."""
        raw_size = len(original.encode("utf-8"))
        compressed = self.compress(original)
        compressed_size = len(compressed)

        ratio = (1 - compressed_size / raw_size) * 100 if raw_size > 0 else 0

        return {
            "algorithm": self.algorithm,
            "original_size": raw_size,
            "compressed_size": compressed_size,
            "ratio_pct": round(ratio, 1),
            "saved_bytes": raw_size - compressed_size,
            "was_compressed": compressed[:2] in (b"\x1f\x8b", b"\x78\x9c", b"\x78\x01"),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return compression configuration."""
        return {
            "algorithm": self.algorithm,
            "min_size": self.min_size,
            "level": self.level,
        }


# ── Cache Migration Manager ─────────────────────────────────────────

class CacheMigrationManager:
    """Manages cache schema migrations between versions.

    When the cache format changes (e.g. new fields added to cache entries),
    this manager handles:
    1. Detecting old-format cache entries
    2. Migrating them to the new format
    3. Cleaning up incompatible entries
    4. Versioning cache keys to prevent conflicts
    """

    def __init__(self, current_version: int = 2):
        self.current_version = current_version
        self._migrations: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_builtin_migrations()

    def _register_builtin_migrations(self) -> None:
        """Register built-in migrations."""
        # Migration from v1 → v2: add "tags" and "revalidate" fields
        def _v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
            if "tags" not in data:
                data["tags"] = []
            if "revalidate" not in data:
                data["revalidate"] = 0
            data["_cache_version"] = 2
            return data

        self._migrations[1] = _v1_to_v2

        # Future migrations can be added here
        # self._migrations[2] = _v2_to_v3

    def register_migration(self, from_version: int,
                            migration_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register a custom migration."""
        self._migrations[from_version] = migration_fn

    def migrate_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate a single cache entry to the current version."""
        entry_version = data.get("_cache_version", 1)

        while entry_version < self.current_version:
            migration = self._migrations.get(entry_version)
            if not migration:
                logger.warning("No migration from v%d — skipping", entry_version)
                break
            try:
                data = migration(data)
                entry_version = data.get("_cache_version", entry_version + 1)
            except Exception as e:
                logger.error("Migration failed: %s", e)
                break

        return data

    def migrate_directory(self, cache_dir: str) -> Dict[str, Any]:
        """Migrate all cache entries in a directory."""
        migrated = 0
        errors = 0
        skipped = 0

        if not os.path.isdir(cache_dir):
            return {"migrated": 0, "errors": 0, "skipped": 0}

        for fname in os.listdir(cache_dir):
            if not fname.endswith(".json"):
                continue

            fpath = os.path.join(cache_dir, fname)
            try:
                with open(fpath, "r") as f:
                    data = json.load(f)

                entry_version = data.get("_cache_version", 1)
                if entry_version >= self.current_version:
                    skipped += 1
                    continue

                migrated_data = self.migrate_entry(data)

                with open(fpath, "w") as f:
                    json.dump(migrated_data, f)
                migrated += 1
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to migrate %s: %s", fname, e)
                errors += 1

        logger.info("Cache migration: %d migrated, %d skipped, %d errors",
                     migrated, skipped, errors)
        return {"migrated": migrated, "skipped": skipped, "errors": errors}

    def get_version_info(self) -> Dict[str, Any]:
        """Return version information."""
        return {
            "current_version": self.current_version,
            "available_migrations": sorted(self._migrations.keys()),
            "migration_count": len(self._migrations),
        }


# ── Cache Health Monitor ─────────────────────────────────────────────

class CacheHealthMonitor:
    """Monitors cache health and raises alerts.

    Checks:
    - Hit rate degradation (alert if below threshold)
    - Memory usage (alert if approaching limit)
    - Disk usage (alert if cache dir is too large)
    - Stale entry ratio (alert if too many stale entries)
    - Tag invalidation frequency (alert if too frequent = cache thrashing)
    """

    def __init__(self, cache_manager: "CacheManager",
                 metrics: Optional[CacheMetricsCollector] = None):
        self.cm = cache_manager
        self.metrics = metrics or CacheMetricsCollector()
        self.alerts: List[Dict[str, Any]] = []
        self.thresholds: Dict[str, Any] = {
            "min_hit_rate": 50.0,        # Alert if hit rate < 50%
            "max_memory_entries": 450,   # Alert if memory cache > 450 entries
            "max_disk_size_mb": 100,     # Alert if disk cache > 100MB
            "max_stale_ratio": 0.3,      # Alert if >30% entries are stale
            "max_invalidation_rate": 100, # Alert if >100 invalidations per hour
        }
        self._invalidation_times: List[float] = []

    def set_threshold(self, name: str, value: Any) -> None:
        """Set a monitoring threshold."""
        self.thresholds[name] = value

    def check_health(self) -> Dict[str, Any]:
        """Run all health checks and return results."""
        self.alerts.clear()

        stats = self.cm.stats()
        hit_rates = self.metrics.get_hit_rate()
        avg_latency = self.metrics.get_avg_latency()

        # Check 1: Hit rate
        for tier, rate in hit_rates.items():
            if rate < self.thresholds["min_hit_rate"]:
                self.alerts.append({
                    "level": "warning",
                    "check": "hit_rate",
                    "tier": tier,
                    "value": f"{rate:.1f}%",
                    "threshold": f"{self.thresholds['min_hit_rate']}%",
                    "message": f"Cache hit rate for {tier} is below threshold",
                })

        # Check 2: Memory usage
        for tier_name in ("tier_2_data_cache", "tier_3_route_cache"):
            tier_stats = stats.get(tier_name, {})
            if isinstance(tier_stats, dict):
                mem_entries = tier_stats.get("memory_entries", 0)
                if mem_entries > self.thresholds["max_memory_entries"]:
                    self.alerts.append({
                        "level": "warning",
                        "check": "memory_usage",
                        "tier": tier_name,
                        "value": mem_entries,
                        "threshold": self.thresholds["max_memory_entries"],
                        "message": f"{tier_name} has too many entries in memory",
                    })

        # Check 3: Disk usage
        for tier_name in ("tier_2_data_cache", "tier_3_route_cache"):
            tier_stats = stats.get(tier_name, {})
            if isinstance(tier_stats, dict):
                disk_entries = tier_stats.get("disk_entries", 0)
                # Estimate ~2KB per entry
                disk_mb = disk_entries * 2 / 1024
                if disk_mb > self.thresholds["max_disk_size_mb"]:
                    self.alerts.append({
                        "level": "warning",
                        "check": "disk_usage",
                        "tier": tier_name,
                        "value": f"{disk_mb:.1f}MB",
                        "threshold": f"{self.thresholds['max_disk_size_mb']}MB",
                        "message": f"{tier_name} disk usage exceeds threshold",
                    })

        # Check 4: Invalidation rate
        now = time.time()
        recent = [t for t in self._invalidation_times if now - t < 3600]
        self._invalidation_times = recent
        if len(recent) > self.thresholds["max_invalidation_rate"]:
            self.alerts.append({
                "level": "critical",
                "check": "invalidation_rate",
                "value": len(recent),
                "threshold": self.thresholds["max_invalidation_rate"],
                "message": "Cache invalidation rate too high — possible cache thrashing",
            })

        # Check 5: Latency
        for key, latency in avg_latency.items():
            if latency > 100:  # >100ms per operation
                self.alerts.append({
                    "level": "warning",
                    "check": "latency",
                    "operation": key,
                    "value": f"{latency:.1f}ms",
                    "threshold": "100ms",
                    "message": f"Cache operation {key} is slow",
                })

        healthy = len(self.alerts) == 0
        return {
            "healthy": healthy,
            "alert_count": len(self.alerts),
            "alerts": self.alerts,
            "stats": stats,
            "hit_rates": hit_rates,
            "avg_latency_ms": avg_latency,
            "thresholds": self.thresholds,
        }

    def record_invalidation(self) -> None:
        """Record a cache invalidation event."""
        self._invalidation_times.append(time.time())

    def get_alerts(self, level: str = "") -> List[Dict[str, Any]]:
        """Get alerts, optionally filtered by level."""
        if level:
            return [a for a in self.alerts if a.get("level") == level]
        return self.alerts

    def get_health_report(self) -> str:
        """Generate a human-readable health report."""
        health = self.check_health()
        lines = [
            "=" * 60,
            "  TW Framework — Cache Health Report",
            "=" * 60,
            "",
            f"  Status: {'✅ HEALTHY' if health['healthy'] else '⚠️ ISSUES FOUND'}",
            f"  Alerts: {health['alert_count']}",
            "",
        ]

        if health["alerts"]:
            lines.append("  Alerts:")
            for alert in health["alerts"]:
                icon = "🔴" if alert["level"] == "critical" else "🟡"
                lines.append(f"    {icon} [{alert['check']}] {alert['message']}")
                lines.append(f"       Value: {alert.get('value', '?')}, Threshold: {alert.get('threshold', '?')}")
            lines.append("")

        lines.append("  Hit Rates:")
        for tier, rate in health.get("hit_rates", {}).items():
            lines.append(f"    {tier}: {rate:.1f}%")
        lines.append("")

        lines.append("  Average Latency:")
        for op, latency in health.get("avg_latency_ms", {}).items():
            lines.append(f"    {op}: {latency:.1f}ms")
        lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


# ── Cache Garbage Collector ──────────────────────────────────────────

class CacheGarbageCollector:
    """Garbage collection for cache entries.

    Periodically:
    - Removes expired entries (stale)
    - Compacts disk cache files
    - Removes orphaned tag index entries
    - Frees memory by evicting cold entries
    - Reports on collected garbage
    """

    def __init__(self, cache_manager: "CacheManager"):
        self.cm = cache_manager
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval: float = 300  # 5 minutes default
        self._collected: Dict[str, int] = {
            "stale_entries": 0,
            "orphaned_tags": 0,
            "disk_files": 0,
            "memory_entries": 0,
        }

    def collect(self) -> Dict[str, int]:
        """Run garbage collection on all cache tiers."""
        collected = {
            "stale_entries": 0,
            "orphaned_tags": 0,
            "disk_files": 0,
            "memory_entries": 0,
        }

        # Tier 2: Data Cache
        try:
            stale = self.cm.data_cache._memory_cache
            now = time.time()
            stale_keys = [
                k for k, v in stale.items()
                if hasattr(v, "revalidate") and v.revalidate > 0
                and (now - v.cached_at) > v.revalidate
            ]
            for key in stale_keys:
                del stale[key]
                collected["stale_entries"] += 1
        except Exception:
            pass

        # Tier 3: Route Cache
        try:
            stale = self.cm.route_cache._memory_cache
            now = time.time()
            stale_keys = [
                k for k, v in stale.items()
                if hasattr(v, "revalidate") and v.revalidate > 0
                and (now - v.cached_at) > v.revalidate
            ]
            for key in stale_keys:
                del stale[key]
                collected["stale_entries"] += 1
        except Exception:
            pass

        # Clean orphaned tag index entries
        for cache_obj in (self.cm.data_cache, self.cm.route_cache):
            try:
                with cache_obj._lock:
                    for tag, keys in list(cache_obj._tag_index.items()):
                        alive_keys = {k for k in keys if k in cache_obj._memory_cache}
                        if not alive_keys:
                            del cache_obj._tag_index[tag]
                            collected["orphaned_tags"] += 1
                        elif len(alive_keys) < len(keys):
                            cache_obj._tag_index[tag] = alive_keys
            except Exception:
                pass

        # Clean disk cache files that are stale
        for cache_obj in (self.cm.data_cache, self.cm.route_cache):
            cache_dir = getattr(cache_obj, "cache_dir", "")
            if cache_dir and os.path.isdir(cache_dir):
                for fname in os.listdir(cache_dir):
                    if not fname.endswith(".json"):
                        continue
                    fpath = os.path.join(cache_dir, fname)
                    try:
                        with open(fpath, "r") as f:
                            data = json.load(f)
                        cached_at = data.get("cached_at", 0)
                        revalidate = data.get("revalidate", 0)
                        if revalidate > 0 and (time.time() - cached_at) > revalidate:
                            os.remove(fpath)
                            collected["disk_files"] += 1
                    except (json.JSONDecodeError, OSError):
                        # Corrupted file — remove it
                        try:
                            os.remove(fpath)
                            collected["disk_files"] += 1
                        except OSError:
                            pass

        self._collected = {k: self._collected.get(k, 0) + v for k, v in collected.items()}

        logger.info("Cache GC: collected %d stale, %d orphaned tags, %d disk files",
                     collected["stale_entries"], collected["orphaned_tags"],
                     collected["disk_files"])
        return collected

    def start(self, interval: float = 300) -> None:
        """Start periodic garbage collection."""
        self._interval = interval
        self._running = True

        def _loop():
            while self._running:
                time.sleep(self._interval)
                if self._running:
                    self.collect()

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        logger.info("Cache GC started (interval: %ds)", interval)

    def stop(self) -> None:
        """Stop garbage collection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Cache GC stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Return GC statistics."""
        return {
            "running": self._running,
            "interval_seconds": self._interval,
            "total_collected": dict(self._collected),
        }


# ── Update __all__ ──────────────────────────────────────────────────


# ── Cache Components Integration (#14) ──────────────────────────────
# Fine-grained, opt-in caching model with use cache directive


class CacheComponentTier:
    """Cache component tier — integrates with the 4-layer cache.

    Cache Components are a higher-level abstraction on top of the
    Data Cache tier. They provide:

    1. Component-level caching (not just data)
    2. Automatic cache key generation from props
    3. Tag-based invalidation (revalidateTag)
    4. Stale-while-revalidate at component level
    5. Integration with PPR boundaries
    """

    def __init__(self, data_cache):
        self.data_cache = data_cache
        self._component_cache: Dict[str, dict] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = __import__("threading").Lock()

    def cache_component(self, name: str, props: dict,
                        html: str, revalidate: int = 0,
                        tags: Optional[List[str]] = None) -> str:
        """Cache a component's rendered HTML."""
        import hashlib, json
        props_str = json.dumps(props, sort_keys=True, default=str)
        cache_key = name + ":" + hashlib.sha256(props_str.encode()).hexdigest()[:16]

        with self._lock:
            self._component_cache[cache_key] = {
                "name": name,
                "html": html,
                "revalidate": revalidate,
                "tags": tags or [],
                "cached_at": __import__("time").time(),
            }

            for tag in (tags or []):
                self._tag_index.setdefault(tag, set()).add(cache_key)

        return cache_key

    def get_cached(self, name: str, props: dict) -> Optional[str]:
        """Get cached component HTML."""
        import hashlib, json
        props_str = json.dumps(props, sort_keys=True, default=str)
        cache_key = name + ":" + hashlib.sha256(props_str.encode()).hexdigest()[:16]

        with self._lock:
            entry = self._component_cache.get(cache_key)
            if not entry:
                return None

            # Check TTL
            if entry["revalidate"] > 0:
                age = __import__("time").time() - entry["cached_at"]
                if age > entry["revalidate"]:
                    return None  # Expired

            return entry["html"]

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all components with a given tag."""
        with self._lock:
            keys = self._tag_index.get(tag, set())
            for key in keys:
                if key in self._component_cache:
                    del self._component_cache[key]
            if tag in self._tag_index:
                del self._tag_index[tag]
            return len(keys)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_components": len(self._component_cache),
                "total_tags": len(self._tag_index),
                "tag_names": list(self._tag_index.keys()),
            }


# ── Incremental Prefetching Cache Layer (#17) ───────────────────────

class IncrementalPrefetchCache:
    """Cache layer for incremental prefetching.

    Tracks which route segments have been prefetched and cached,
    so only uncached segments are fetched on navigation.
    """

    def __init__(self):
        self._cached_segments: Dict[str, float] = {}  # segment_key -> timestamp
        self._segment_ttl: float = 300  # 5 minutes
        self._lock = __import__("threading").Lock()

    def is_cached(self, route: str, segment: str = "") -> bool:
        """Check if a segment is cached and not expired."""
        key = route + "/" + segment if segment else route
        with self._lock:
            if key not in self._cached_segments:
                return False
            age = __import__("time").time() - self._cached_segments[key]
            return age < self._segment_ttl

    def mark_cached(self, route: str, segment: str = "") -> None:
        """Mark a segment as cached."""
        key = route + "/" + segment if segment else route
        with self._lock:
            self._cached_segments[key] = __import__("time").time()

    def get_uncached(self, route: str, segments: List[str]) -> List[str]:
        """Get list of uncached segments for a route."""
        return [s for s in segments if not self.is_cached(route, s)]

    def invalidate_route(self, route: str) -> int:
        """Invalidate all cached segments for a route."""
        with self._lock:
            keys = [k for k in self._cached_segments if k.startswith(route)]
            for k in keys:
                del self._cached_segments[k]
            return len(keys)

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        now = __import__("time").time()
        with self._lock:
            expired = [k for k, t in self._cached_segments.items()
                       if now - t > self._segment_ttl]
            for k in expired:
                del self._cached_segments[k]
            return len(expired)

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_cached": len(self._cached_segments),
                "ttl_seconds": self._segment_ttl,
            }


# ── Layout Deduplication Cache (#18) ────────────────────────────────

class LayoutDeduplicationCache:
    """Cache for layout deduplication.

    When navigating between routes that share a layout:
    - The layout HTML is cached and reused
    - Only the content area is fetched
    - Reduces bandwidth and improves navigation speed
    """

    def __init__(self):
        self._layout_cache: Dict[str, dict] = {}
        self._active_layout: str = ""
        self._lock = __import__("threading").Lock()

    def cache_layout(self, layout_name: str, html: str,
                     route_pattern: str = "") -> None:
        """Cache a layout's HTML."""
        with self._lock:
            self._layout_cache[layout_name] = {
                "html": html,
                "route_pattern": route_pattern,
                "cached_at": __import__("time").time(),
            }

    def get_layout(self, layout_name: str) -> Optional[str]:
        """Get cached layout HTML."""
        with self._lock:
            entry = self._layout_cache.get(layout_name)
            return entry["html"] if entry else None

    def set_active_layout(self, layout_name: str) -> None:
        """Set the currently active layout."""
        with self._lock:
            self._active_layout = layout_name

    def should_reuse_layout(self, new_route: str) -> bool:
        """Check if the current layout can be reused for new_route."""
        with self._lock:
            if not self._active_layout:
                return False
            entry = self._layout_cache.get(self._active_layout)
            if not entry:
                return False
            pattern = entry.get("route_pattern", "")
            if pattern:
                return new_route.startswith(pattern)
            return False

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_layouts": len(self._layout_cache),
                "active_layout": self._active_layout,
                "cached_layouts": list(self._layout_cache.keys()),
            }

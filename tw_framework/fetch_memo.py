"""
Request Memoization for tw.http.fetch().

Integrates the RequestMemoization tier from cache_tiers.py into the
runtime fetch() functions. This automatically deduplicates identical
fetch() calls within a single request — if the same URL is fetched
multiple times in one request, only the first call executes.

Usage (automatic — no code changes needed in user handlers):
  // In a .twm handler:
  const data1 = tw.http.fetch("https://api.com/users");  // Executes
  const data2 = tw.http.fetch("https://api.com/users");  // Deduplicated! Returns cached result

  // Both data1 and data2 contain the same response, but only one HTTP request was made.

This is equivalent to Next.js Request Memoization.

Integration:
  - Call start_request() at the beginning of each HTTP request
  - Call end_request() at the end of each HTTP request
  - Use memoized_fetch() instead of raw fetch() in runtime adapters
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .cache_tiers import RequestMemoization

logger = logging.getLogger(__name__)


def _make_fetch_key(url: str, options: Optional[dict] = None) -> str:
    """Create a deduplication key from URL and options.

    Two fetch calls with the same URL, method, and body are considered
    identical and will be deduplicated.
    """
    opts = options or {}
    method = opts.get("method", "GET").upper()
    body = opts.get("body")
    # Normalize body to string for hashing
    if body is not None:
        if isinstance(body, (dict, list)):
            body_str = json.dumps(body, sort_keys=True)
        elif isinstance(body, str):
            body_str = body
        else:
            body_str = str(body)
    else:
        body_str = ""
    raw = f"{method}:{url}:{body_str}"
    return hashlib.sha256(raw.encode()).hexdigest()


def memoized_fetch(url: str, fetch_fn: Callable[[], Any], options: Optional[dict] = None) -> Any:
    """Execute a fetch with automatic request-level deduplication.

    If the same URL+method+body has already been fetched in this request,
    return the cached result instead of executing fetch_fn again.

    Args:
        url: The URL being fetched
        fetch_fn: A callable that performs the actual HTTP request
        options: Fetch options (method, headers, body, etc.)

    Returns:
        The fetch result (cached or fresh)

    Example:
        result = memoized_fetch(
            "https://api.com/users",
            lambda: tw.http.fetch("https://api.com/users"),
            {"method": "GET"}
        )
    """
    key = _make_fetch_key(url, options)
    return RequestMemoization.memoize(key, fetch_fn)


class FetchWrapper:
    """Wraps an existing HTTP fetch function with request memoization.

    Drop-in replacement for any tw.http.fetch() implementation:

        original_fetch = rt.http.fetch
        rt.http.fetch = FetchWrapper(original_fetch).wrapped_fetch

    Now all calls to rt.http.fetch() are automatically deduplicated.
    """

    def __init__(self, original_fetch: Callable):
        self._original = original_fetch

    def wrapped_fetch(self, url: str, options: Optional[dict] = None) -> Any:
        """Fetch with automatic deduplication."""
        def _do_fetch():
            return self._original(url, options)
        return memoized_fetch(url, _do_fetch, options)


def patch_runtime_fetch(runtime) -> None:
    """Patch a runtime's http.fetch with request memoization.

    Call this once per runtime instance to enable automatic
    fetch deduplication for all tw.http.fetch() calls.

    Args:
        runtime: A runtime instance (NodeRuntime, PythonRuntime, etc.)
    """
    if not hasattr(runtime, 'http') or not hasattr(runtime.http, 'fetch'):
        return

    http = runtime.http
    if hasattr(http, '_memoized'):
        return  # Already patched

    original = http.fetch
    wrapper = FetchWrapper(original)
    http.fetch = wrapper.wrapped_fetch
    http._memoized = True
    logger.debug("Patched %s http.fetch with request memoization", type(runtime).__name__)


def start_request() -> None:
    """Initialize per-request memoization. Call at the start of each HTTP request."""
    RequestMemoization.start_request()


def end_request() -> None:
    """Clear per-request memoization. Call at the end of each HTTP request."""
    RequestMemoization.end_request()


def get_memoization_stats() -> Dict[str, Any]:
    """Return current request memoization statistics."""
    store = RequestMemoization._get_store()
    return {
        "active": len(store) > 0,
        "deduplicated_calls": len(store),
        "cache_keys": list(store.keys())[:10],  # First 10 for debugging
    }


__all__ = [
    "memoized_fetch",
    "FetchWrapper",
    "patch_runtime_fetch",
    "start_request",
    "end_request",
    "get_memoization_stats",
    "FetchDeduplicationStats",
    "EnhancedFetchWrapper",
    "FetchRequestContext",
    "FetchCacheConfig",
    "ConfigurableFetchWrapper",
    "RetryConfig",
    "FetchRetryHandler",
    "FetchTimeoutManager",
    "BatchFetchRequest",
    "BatchFetchResponse",
    "BatchFetchManager",
    "QueuedFetch",
    "FetchRequestQueue",
    "FetchCircuitBreaker",
]


# ── Fetch Deduplication Stats Tracker ────────────────────────────────

class FetchDeduplicationStats:
    """Tracks deduplication statistics across requests.

    Provides insights into how many fetch calls were deduplicated,
    which URLs are most commonly duplicated, and potential savings.
    """

    def __init__(self):
        self._total_calls = 0
        self._deduplicated_calls = 0
        self._actual_calls = 0
        self._url_stats: Dict[str, Dict[str, int]] = {}  # url → {called, deduplicated}
        self._lock = threading.Lock()

    def record_call(self, url: str, deduplicated: bool) -> None:
        """Record a fetch call."""
        with self._lock:
            self._total_calls += 1
            if deduplicated:
                self._deduplicated_calls += 1
            else:
                self._actual_calls += 1

            if url not in self._url_stats:
                self._url_stats[url] = {"called": 0, "deduplicated": 0}
            self._url_stats[url]["called"] += 1
            if deduplicated:
                self._url_stats[url]["deduplicated"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Return deduplication statistics."""
        with self._lock:
            savings_pct = 0
            if self._total_calls > 0:
                savings_pct = (self._deduplicated_calls / self._total_calls) * 100

            # Top duplicated URLs
            top_duplicated = sorted(
                [
                    {"url": url, "calls": stats["called"],
                     "deduplicated": stats["deduplicated"]}
                    for url, stats in self._url_stats.items()
                    if stats["deduplicated"] > 0
                ],
                key=lambda x: x["deduplicated"],
                reverse=True,
            )[:20]

            return {
                "total_calls": self._total_calls,
                "actual_calls": self._actual_calls,
                "deduplicated_calls": self._deduplicated_calls,
                "savings_pct": round(savings_pct, 1),
                "urls_tracked": len(self._url_stats),
                "top_duplicated": top_duplicated,
            }

    def reset(self) -> None:
        """Reset all statistics."""
        with self._lock:
            self._total_calls = 0
            self._deduplicated_calls = 0
            self._actual_calls = 0
            self._url_stats.clear()


# ── Global stats instance ────────────────────────────────────────────
_global_stats = FetchDeduplicationStats()


# ── Enhanced Fetch Wrapper with Stats ────────────────────────────────

class EnhancedFetchWrapper:
    """Enhanced fetch wrapper with stats tracking and cache chaining.

    Wraps an existing fetch function with:
    1. Request memoization (Tier 1 — per-request dedup)
    2. Optional data cache (Tier 2 — persistent cache)
    3. Stats tracking
    4. Configurable dedup keys
    5. Selective dedup (skip certain URLs/methods)
    """

    def __init__(self, original_fetch: Callable,
                 data_cache=None,
                 skip_methods: Optional[Set[str]] = None,
                 skip_urls: Optional[Set[str]] = None,
                 stats: Optional[FetchDeduplicationStats] = None):
        self._original = original_fetch
        self._data_cache = data_cache
        self._skip_methods = skip_methods or {"POST", "PUT", "DELETE", "PATCH"}
        self._skip_urls = skip_urls or set()
        self._stats = stats or _global_stats

    def wrapped_fetch(self, url: str, options: Optional[dict] = None) -> Any:
        """Fetch with memoization, optional caching, and stats tracking."""
        opts = options or {}
        method = opts.get("method", "GET").upper()

        # Skip dedup for mutating methods
        if method in self._skip_methods:
            self._stats.record_call(url, False)
            return self._original(url, options)

        # Skip specific URLs
        for skip_url in self._skip_urls:
            if skip_url in url:
                self._stats.record_call(url, False)
                return self._original(url, options)

        # Check data cache (Tier 2)
        if self._data_cache:
            cached = self._data_cache.get(url, opts)
            if cached is not None:
                self._stats.record_call(url, True)
                return cached

        # Check request memoization (Tier 1)
        key = _make_fetch_key(url, opts)

        def _do_fetch():
            result = self._original(url, options)
            # Store in data cache
            if self._data_cache:
                revalidate = opts.get("revalidate", 0)
                tags = opts.get("tags")
                self._data_cache.set(url, result, opts, revalidate=revalidate, tags=tags)
            return result

        # Check if already memoized
        already_memoized = RequestMemoization.has(key)
        result = RequestMemoization.memoize(key, _do_fetch)

        if already_memoized:
            self._stats.record_call(url, True)
        else:
            self._stats.record_call(url, False)

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return fetch deduplication stats."""
        return self._stats.get_stats()

    def reset_stats(self) -> None:
        """Reset stats."""
        self._stats.reset()


# ── Fetch Request Context ────────────────────────────────────────────

class FetchRequestContext:
    """Context manager for request-scoped fetch memoization.

    Usage:
        with FetchRequestContext():
            # All fetch calls within this block are memoized
            data1 = fetch("https://api.com/users")
            data2 = fetch("https://api.com/users")  # Deduplicated!
        # Memoization cleared after the block

    Can be nested — inner context inherits outer memoization.
    """

    def __init__(self, stats: Optional[FetchDeduplicationStats] = None):
        self._stats = stats
        self._call_count = 0
        self._dedup_count = 0

    def __enter__(self):
        RequestMemoization.start_request()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        RequestMemoization.end_request()
        return False

    def record_fetch(self, url: str, deduplicated: bool) -> None:
        """Record a fetch call within this context."""
        self._call_count += 1
        if deduplicated:
            self._dedup_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Return per-request dedup summary."""
        return {
            "total_fetches": self._call_count,
            "deduplicated": self._dedup_count,
            "actual_requests": self._call_count - self._dedup_count,
            "savings": f"{(self._dedup_count / self._call_count * 100):.1f}%" if self._call_count > 0 else "N/A",
        }


# ── Fetch Cache Configuration ────────────────────────────────────────

@dataclass
class FetchCacheConfig:
    """Configuration for fetch memoization and caching.

    Controls which requests are memoized, cached, and for how long.
    """
    # Request memoization
    enable_memoization: bool = True
    skip_methods: Set[str] = field(default_factory=lambda: {"POST", "PUT", "DELETE", "PATCH"})

    # Data cache
    enable_data_cache: bool = True
    default_revalidate: int = 0  # 0 = no caching by default
    default_tags: List[str] = field(default_factory=list)

    # URL patterns
    always_cache_urls: Set[str] = field(default_factory=set)
    never_cache_urls: Set[str] = field(default_factory=set)
    cache_url_patterns: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Options per URL pattern
    # {"/api/users": {"revalidate": 60, "tags": ["users"]}}

    def get_config_for_url(self, url: str) -> Dict[str, Any]:
        """Get cache configuration for a specific URL."""
        # Check exact matches first
        if url in self.never_cache_urls:
            return {"cache": False, "memoize": False}

        if url in self.always_cache_urls:
            return {"cache": True, "revalidate": self.default_revalidate,
                    "tags": self.default_tags}

        # Check patterns
        for pattern, config in self.cache_url_patterns.items():
            if pattern in url or url.startswith(pattern):
                return {"cache": True, **config}

        # Default
        return {
            "cache": self.enable_data_cache,
            "memoize": self.enable_memoization,
            "revalidate": self.default_revalidate,
            "tags": self.default_tags,
        }


# ── Configurable Fetch Wrapper ──────────────────────────────────────

class ConfigurableFetchWrapper:
    """Fetch wrapper with configurable caching per URL.

    Uses a FetchCacheConfig to determine caching behavior per URL.
    """

    def __init__(self, original_fetch: Callable,
                 config: FetchCacheConfig,
                 data_cache=None,
                 stats: Optional[FetchDeduplicationStats] = None):
        self._original = original_fetch
        self._config = config
        self._data_cache = data_cache
        self._stats = stats or _global_stats
        self._enhanced = EnhancedFetchWrapper(
            original_fetch, data_cache,
            config.skip_methods, config.never_cache_urls, stats
        )

    def wrapped_fetch(self, url: str, options: Optional[dict] = None) -> Any:
        """Fetch with per-URL configuration."""
        opts = options or {}
        url_config = self._config.get_config_for_url(url)

        # Merge URL config into options
        if url_config.get("cache"):
            opts.setdefault("revalidate", url_config.get("revalidate", 0))
            if url_config.get("tags"):
                opts.setdefault("tags", url_config["tags"])

        if not url_config.get("memoize"):
            # Skip memoization
            self._stats.record_call(url, False)
            return self._original(url, opts)

        return self._enhanced.wrapped_fetch(url, opts)

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.get_stats()


# ── Update __all__ ──────────────────────────────────────────────────

# ── Fetch Retry & Timeout Handler ────────────────────────────────────

@dataclass
class RetryConfig:
    """Configuration for fetch retry behavior."""
    max_retries: int = 3
    base_delay_ms: float = 500
    max_delay_ms: float = 10000
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.25
    retry_on_status: List[int] = field(default_factory=lambda: [502, 503, 504])
    retry_on_exceptions: List[str] = field(default_factory=lambda: [
        "ConnectionError", "TimeoutError", "OSError",
    ])


class FetchRetryHandler:
    """Retry handler for fetch operations.

    Wraps a fetch function with:
    - Exponential backoff with jitter
    - Configurable retry conditions (status codes, exception types)
    - Max retry limit
    - Per-attempt timeout
    - Retry statistics tracking
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._stats: Dict[str, Dict[str, int]] = {}

    def execute(self, fetch_fn: Callable[..., Any],
                url: str, *args, **kwargs) -> Any:
        """Execute a fetch function with retry logic.

        The fetch_fn should return an object with a 'status' attribute
        (or be a plain value). Raises the last exception if all retries fail.
        """
        import random as _random
        import time as _time

        url_key = url[:100]  # Truncate for stats key
        if url_key not in self._stats:
            self._stats[url_key] = {"attempts": 0, "retries": 0, "successes": 0, "failures": 0}

        last_error: Optional[Exception] = None
        last_result: Any = None

        for attempt in range(self.config.max_retries + 1):
            self._stats[url_key]["attempts"] += 1

            try:
                result = fetch_fn(url, *args, **kwargs)
                last_result = result

                # Check if result has a status code
                status = getattr(result, "status", None) or getattr(result, "status_code", None)

                if status and status in self.config.retry_on_status:
                    if attempt < self.config.max_retries:
                        self._stats[url_key]["retries"] += 1
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            "Fetch %s returned %d, retrying in %.0fms (attempt %d/%d)",
                            url[:50], status, delay, attempt + 1, self.config.max_retries + 1,
                        )
                        _time.sleep(delay / 1000)
                        continue

                # Success
                self._stats[url_key]["successes"] += 1
                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                should_retry = error_type in self.config.retry_on_exceptions
                # Also check parent class names
                if not should_retry:
                    for cls in type(e).__mro__:
                        if cls.__name__ in self.config.retry_on_exceptions:
                            should_retry = True
                            break

                if should_retry and attempt < self.config.max_retries:
                    self._stats[url_key]["retries"] += 1
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "Fetch %s raised %s, retrying in %.0fms (attempt %d/%d)",
                        url[:50], error_type, delay, attempt + 1, self.config.max_retries + 1,
                    )
                    _time.sleep(delay / 1000)
                else:
                    self._stats[url_key]["failures"] += 1
                    raise

        # Should not reach here, but just in case
        self._stats[url_key]["failures"] += 1
        if last_error:
            raise last_error
        return last_result

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        import random as _random

        delay = self.config.base_delay_ms * (self.config.backoff_multiplier ** attempt)
        delay = min(delay, self.config.max_delay_ms)

        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            delay = delay + _random.uniform(-jitter_amount, jitter_amount)

        return max(delay, 0)

    def get_stats(self) -> Dict[str, Any]:
        """Return retry statistics."""
        total_attempts = sum(s["attempts"] for s in self._stats.values())
        total_retries = sum(s["retries"] for s in self._stats.values())
        total_successes = sum(s["successes"] for s in self._stats.values())
        total_failures = sum(s["failures"] for s in self._stats.values())

        return {
            "total_urls": len(self._stats),
            "total_attempts": total_attempts,
            "total_retries": total_retries,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "retry_rate_pct": round(total_retries / total_attempts * 100, 1) if total_attempts else 0,
            "success_rate_pct": round(total_successes / total_attempts * 100, 1) if total_attempts else 0,
            "per_url": dict(self._stats),
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        self._stats.clear()


# ── Fetch Timeout Manager ────────────────────────────────────────────

class FetchTimeoutManager:
    """Manages timeouts for fetch operations.

    Provides:
    - Per-request timeout configuration
    - Global default timeout
    - Timeout override by URL pattern
    - Slow request detection (warn if > threshold)
    - Timeout statistics
    """

    def __init__(self, default_timeout_ms: float = 30000):
        self.default_timeout_ms = default_timeout_ms
        self._per_url: Dict[str, float] = {}
        self._pattern_timeouts: List[Tuple[str, float]] = []
        self._slow_threshold_ms: float = 5000
        self._slow_requests: List[Dict[str, Any]] = []
        self._timeout_count: int = 0
        self._total_requests: int = 0

    def set_timeout(self, url: str, timeout_ms: float) -> None:
        """Set a per-URL timeout."""
        self._per_url[url] = timeout_ms

    def set_pattern_timeout(self, pattern: str, timeout_ms: float) -> None:
        """Set timeout for URLs matching a pattern (regex)."""
        self._pattern_timeouts.append((pattern, timeout_ms))

    def get_timeout(self, url: str) -> float:
        """Get the timeout for a URL."""
        # Check exact match first
        if url in self._per_url:
            return self._per_url[url]

        # Check patterns
        import re
        for pattern, timeout in self._pattern_timeouts:
            if re.search(pattern, url):
                return timeout

        return self.default_timeout_ms

    def set_slow_threshold(self, threshold_ms: float) -> None:
        """Set the threshold for slow request detection."""
        self._slow_threshold_ms = threshold_ms

    def record_request(self, url: str, duration_ms: float,
                        timed_out: bool = False) -> None:
        """Record a fetch request for statistics."""
        self._total_requests += 1

        if timed_out:
            self._timeout_count += 1

        if duration_ms > self._slow_threshold_ms:
            self._slow_requests.append({
                "url": url[:200],
                "duration_ms": round(duration_ms, 1),
                "timed_out": timed_out,
                "timestamp": time.time(),
            })

            # Keep only last 100 slow requests
            if len(self._slow_requests) > 100:
                self._slow_requests = self._slow_requests[-100:]

    def execute_with_timeout(self, fetch_fn: Callable[..., Any],
                              url: str, *args, **kwargs) -> Any:
        """Execute a fetch function with timeout.

        Uses signal.SIGALRM (Unix) for timeout enforcement.
        The fetch_fn is called with a 'timeout' keyword argument.
        """
        import signal
        timeout_ms = self.get_timeout(url)
        timeout_s = timeout_ms / 1000

        start_time = time.time()

        def _alarm_handler(signum, frame):
            raise TimeoutError(f"Fetch to {url[:50]} timed out after {timeout_ms}ms")

        try:
            old_handler = signal.signal(signal.SIGALRM, _alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_s)

            kwargs["timeout"] = timeout_s
            result = fetch_fn(url, *args, **kwargs)

            duration_ms = (time.time() - start_time) * 1000
            self.record_request(url, duration_ms, timed_out=False)
            return result

        except TimeoutError as e:
            duration_ms = (time.time() - start_time) * 1000
            self.record_request(url, duration_ms, timed_out=True)
            logger.warning("Fetch timeout: %s (%.0fms)", url[:50], duration_ms)
            raise

        finally:
            signal.signal(signal.SIGALRM, old_handler)
            signal.setitimer(signal.ITIMER_REAL, 0)

    def get_stats(self) -> Dict[str, Any]:
        """Return timeout statistics."""
        return {
            "default_timeout_ms": self.default_timeout_ms,
            "total_requests": self._total_requests,
            "timeout_count": self._timeout_count,
            "timeout_rate_pct": round(self._timeout_count / self._total_requests * 100, 1) if self._total_requests else 0,
            "slow_request_count": len(self._slow_requests),
            "slow_threshold_ms": self._slow_threshold_ms,
            "slow_requests": self._slow_requests[-10:],  # Last 10
            "per_url_timeouts": len(self._per_url),
            "pattern_timeouts": len(self._pattern_timeouts),
        }


# ── Batch Fetch Manager ──────────────────────────────────────────────

@dataclass
class BatchFetchRequest:
    """A single request in a batch."""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchFetchResponse:
    """Response for a single batch request."""
    id: str
    url: str
    status: int = 0
    data: Any = None
    error: str = ""
    duration_ms: float = 0.0


class BatchFetchManager:
    """Batch multiple fetch requests for efficient processing.

    Features:
    - Concurrent fetching (configurable max workers)
    - Request deduplication (skip duplicate URLs in same batch)
    - Result aggregation and transformation
    - Partial failure handling (some requests succeed, some fail)
    - Batch caching (cache entire batch results)
    - Priority ordering within batch
    """

    def __init__(self, max_concurrent: int = 10,
                 dedup: bool = True,
                 cache_results: bool = True,
                 cache_ttl_seconds: float = 300):
        self.max_concurrent = max_concurrent
        self.dedup = dedup
        self.cache_results = cache_results
        self.cache_ttl = cache_ttl_seconds
        self._batch_cache: Dict[str, Tuple[Any, float]] = {}
        self._stats: Dict[str, int] = {
            "batches_processed": 0,
            "total_requests": 0,
            "deduplicated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "successes": 0,
            "failures": 0,
        }

    def fetch_batch(self, requests: List[BatchFetchRequest],
                     fetch_fn: Optional[Callable[[BatchFetchRequest], BatchFetchResponse]] = None
                     ) -> List[BatchFetchResponse]:
        """Fetch multiple URLs in parallel.

        Args:
            requests: List of batch fetch requests
            fetch_fn: Function to fetch a single URL (receives BatchFetchRequest)
                      If None, uses urllib

        Returns:
            List of BatchFetchResponse in the same order as requests
        """
        import concurrent.futures
        import time as _time

        batch_start = _time.time()
        self._stats["batches_processed"] += 1
        self._stats["total_requests"] += len(requests)

        if not requests:
            return []

        # Deduplicate
        if self.dedup:
            unique_requests: List[BatchFetchRequest] = []
            seen_urls: Set[str] = set()
            url_to_first_idx: Dict[str, int] = {}

            for i, req in enumerate(requests):
                url_key = f"{req.method}:{req.url}"
                if url_key in seen_urls:
                    self._stats["deduplicated"] += 1
                    url_to_first_idx[url_key] = url_to_first_idx.get(url_key, i)
                else:
                    seen_urls.add(url_key)
                    unique_requests.append(req)
                    url_to_first_idx[url_key] = i

            fetch_targets = unique_requests
        else:
            fetch_targets = requests

        # Check cache
        results_map: Dict[str, BatchFetchResponse] = {}
        uncached: List[BatchFetchRequest] = []

        for req in fetch_targets:
            cache_key = f"{req.method}:{req.url}"
            if self.cache_results and cache_key in self._batch_cache:
                cached_data, cached_at = self._batch_cache[cache_key]
                if _time.time() - cached_at < self.cache_ttl:
                    results_map[cache_key] = BatchFetchResponse(
                        id=req.id, url=req.url,
                        status=200, data=cached_data,
                        duration_ms=0.0,
                    )
                    self._stats["cache_hits"] += 1
                    continue

            self._stats["cache_misses"] += 1
            uncached.append(req)

        # Fetch uncached in parallel
        if uncached:
            default_fn = fetch_fn or self._default_fetch

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                future_to_req = {
                    executor.submit(default_fn, req): req for req in uncached
                }

                for future in concurrent.futures.as_completed(future_to_req):
                    req = future_to_req[future]
                    cache_key = f"{req.method}:{req.url}"

                    try:
                        response = future.result()
                        results_map[cache_key] = response

                        if response.status == 200:
                            self._stats["successes"] += 1
                            if self.cache_results:
                                self._batch_cache[cache_key] = (response.data, _time.time())
                        else:
                            self._stats["failures"] += 1
                    except Exception as e:
                        results_map[cache_key] = BatchFetchResponse(
                            id=req.id, url=req.url,
                            status=0, error=str(e),
                        )
                        self._stats["failures"] += 1

        # Build results in original order
        all_results: List[BatchFetchResponse] = []
        for req in requests:
            cache_key = f"{req.method}:{req.url}"
            response = results_map.get(cache_key)
            if response:
                all_results.append(response)
            else:
                all_results.append(BatchFetchResponse(
                    id=req.id, url=req.url,
                    status=0, error="No response",
                ))

        batch_duration = (_time.time() - batch_start) * 1000
        logger.info(
            "Batch fetch: %d requests (%d unique, %d cached) in %.1fms",
            len(requests), len(fetch_targets), len(results_map) - len(uncached),
            batch_duration,
        )

        return all_results

    @staticmethod
    def _default_fetch(request: BatchFetchRequest) -> BatchFetchResponse:
        """Default fetch implementation using urllib."""
        import urllib.request
        import time as _time

        start = _time.time()

        try:
            req = urllib.request.Request(
                request.url,
                headers=request.headers or {},
                method=request.method,
            )
            if request.body:
                req.data = request.body.encode("utf-8") if isinstance(request.body, str) else request.body

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8", errors="replace")
                duration = (_time.time() - start) * 1000

                return BatchFetchResponse(
                    id=request.id,
                    url=request.url,
                    status=resp.status,
                    data=data,
                    duration_ms=duration,
                )
        except Exception as e:
            duration = (_time.time() - start) * 1000
            return BatchFetchResponse(
                id=request.id,
                url=request.url,
                status=0,
                error=str(e),
                duration_ms=duration,
            )

    def clear_cache(self) -> None:
        """Clear the batch cache."""
        self._batch_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return batch fetch statistics."""
        return {
            **self._stats,
            "cache_size": len(self._batch_cache),
            "cache_ttl_seconds": self.cache_ttl,
            "max_concurrent": self.max_concurrent,
        }


# ── Fetch Request Queue ─────────────────────────────────────────────

@dataclass
class QueuedFetch:
    """A queued fetch request."""
    id: str
    url: str
    method: str = "GET"
    priority: int = 0
    queued_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = "queued"
    response: Any = None
    error: str = ""


class FetchRequestQueue:
    """Priority queue for fetch requests.

    Processes fetch requests in priority order with:
    - Max concurrent requests (rate limiting)
    - Priority-based ordering
    - Request deduplication
    - Result caching
    - Queue statistics
    """

    def __init__(self, max_concurrent: int = 5,
                 rate_limit_per_second: float = 0):
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit_per_second
        self._queue: List[QueuedFetch] = []
        self._completed: Dict[str, QueuedFetch] = {}
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._running = False
        self._workers: List[threading.Thread] = []
        self._active_count = 0
        self._counter = 0
        self._last_fetch_times: List[float] = []  # For rate limiting
        self._fetch_fn: Optional[Callable] = None

    def set_fetch_fn(self, fn: Callable[[QueuedFetch], Any]) -> None:
        """Set the function used to execute fetches."""
        self._fetch_fn = fn

    def enqueue(self, url: str, method: str = "GET",
                priority: int = 0) -> str:
        """Queue a fetch request. Returns request ID."""
        with self._lock:
            self._counter += 1
            req_id = f"fetch_{self._counter}_{int(time.time())}"

            self._queue.append(QueuedFetch(
                id=req_id,
                url=url,
                method=method,
                priority=priority,
            ))

            # Sort by priority (higher first), then by queue time
            self._queue.sort(key=lambda f: (-f.priority, f.queued_at))
            self._cond.notify()
            return req_id

    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            return
        self._running = True

        for i in range(self.max_concurrent):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            t.start()
            self._workers.append(t)

        logger.info("FetchRequestQueue started with %d workers", self.max_concurrent)

    def stop(self) -> None:
        """Stop worker threads."""
        self._running = False
        with self._cond:
            self._cond.notify_all()

        for t in self._workers:
            t.join(timeout=2)
        self._workers.clear()
        logger.info("FetchRequestQueue stopped")

    def _worker_loop(self, worker_id: int) -> None:
        """Worker thread loop."""
        while self._running:
            with self._cond:
                while not self._queue and self._running:
                    self._cond.wait(timeout=1)
                    if not self._running:
                        return

                if not self._queue:
                    continue

                # Rate limiting
                if self.rate_limit > 0:
                    now = time.time()
                    self._last_fetch_times = [t for t in self._last_fetch_times if now - t < 1.0]
                    if len(self._last_fetch_times) >= self.rate_limit:
                        self._cond.wait(timeout=0.1)
                        continue
                    self._last_fetch_times.append(now)

                fetch_req = self._queue.pop(0)
                fetch_req.status = "running"
                fetch_req.started_at = time.time()
                self._active_count += 1

            # Execute fetch
            try:
                if self._fetch_fn:
                    result = self._fetch_fn(fetch_req)
                else:
                    result = self._default_fetch(fetch_req)

                fetch_req.status = "completed"
                fetch_req.response = result
                fetch_req.completed_at = time.time()
            except Exception as e:
                fetch_req.status = "failed"
                fetch_req.error = str(e)
                fetch_req.completed_at = time.time()
                logger.warning("Fetch '%s' failed: %s", fetch_req.id, e)

            with self._lock:
                self._completed[fetch_req.id] = fetch_req
                self._active_count -= 1

    @staticmethod
    def _default_fetch(request: QueuedFetch) -> Any:
        """Default fetch implementation."""
        import urllib.request

        req = urllib.request.Request(request.url, method=request.method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def get_result(self, req_id: str, timeout: float = 30) -> Any:
        """Wait for and return the result of a queued fetch."""
        import time as _time
        start = _time.time()

        while _time.time() - start < timeout:
            with self._lock:
                if req_id in self._completed:
                    return self._completed[req_id].response
            _time.sleep(0.1)

        raise TimeoutError(f"Fetch {req_id} did not complete within {timeout}s")

    def get_status(self, req_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a queued fetch."""
        with self._lock:
            if req_id in self._completed:
                f = self._completed[req_id]
                return {
                    "id": f.id,
                    "status": f.status,
                    "url": f.url,
                    "queued_at": f.queued_at,
                    "started_at": f.started_at,
                    "completed_at": f.completed_at,
                    "duration_ms": (f.completed_at - f.started_at) * 1000 if f.completed_at else 0,
                    "error": f.error,
                }

            for f in self._queue:
                if f.id == req_id:
                    return {
                        "id": f.id,
                        "status": f.status,
                        "url": f.url,
                        "queued_at": f.queued_at,
                    }

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Return queue statistics."""
        with self._lock:
            return {
                "queue_length": len(self._queue),
                "completed_count": len(self._completed),
                "active_workers": self._active_count,
                "max_concurrent": self.max_concurrent,
                "rate_limit": self.rate_limit,
                "running": self._running,
            }

    def clear_completed(self, max_age_seconds: float = 3600) -> int:
        """Clear old completed fetches."""
        now = time.time()
        with self._lock:
            old_ids = [
                rid for rid, f in self._completed.items()
                if now - f.completed_at > max_age_seconds
            ]
            for rid in old_ids:
                del self._completed[rid]
        return len(old_ids)


# ── Fetch Circuit Breaker ────────────────────────────────────────────

class FetchCircuitBreaker:
    """Circuit breaker pattern for fetch operations.

    Prevents cascading failures by:
    - Tracking failure rate per host
    - Opening circuit when failure rate exceeds threshold
    - Blocking requests when circuit is open
    - Half-open state: allow limited test requests
    - Closing circuit when test requests succeed

    States:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: All requests blocked (failures exceeded threshold)
    - HALF_OPEN: Limited test requests allowed to check recovery
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout_s: float = 30,
                 half_open_max_requests: int = 3,
                 success_threshold: int = 3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_s
        self.half_open_max = half_open_max_requests
        self.success_threshold = success_threshold

        self._circuits: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _get_host(self, url: str) -> str:
        """Extract host from URL."""
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc or url[:50]
        except Exception:
            return url[:50]

    def can_request(self, url: str) -> bool:
        """Check if a request to this URL is allowed."""
        host = self._get_host(url)

        with self._lock:
            circuit = self._circuits.get(host, {
                "state": self.CLOSED,
                "failures": 0,
                "successes": 0,
                "last_failure": 0,
                "half_open_count": 0,
            })

            self._circuits[host] = circuit

            if circuit["state"] == self.CLOSED:
                return True

            if circuit["state"] == self.OPEN:
                # Check if recovery timeout has passed
                if time.time() - circuit["last_failure"] > self.recovery_timeout:
                    circuit["state"] = self.HALF_OPEN
                    circuit["half_open_count"] = 0
                    circuit["successes"] = 0
                    logger.info("Circuit %s: OPEN -> HALF_OPEN", host)
                    return True
                return False

            if circuit["state"] == self.HALF_OPEN:
                if circuit["half_open_count"] < self.half_open_max:
                    circuit["half_open_count"] += 1
                    return True
                return False

        return True

    def record_success(self, url: str) -> None:
        """Record a successful request."""
        host = self._get_host(url)

        with self._lock:
            circuit = self._circuits.get(host)
            if not circuit:
                return

            if circuit["state"] == self.HALF_OPEN:
                circuit["successes"] += 1
                if circuit["successes"] >= self.success_threshold:
                    circuit["state"] = self.CLOSED
                    circuit["failures"] = 0
                    logger.info("Circuit %s: HALF_OPEN -> CLOSED", host)
            elif circuit["state"] == self.CLOSED:
                circuit["failures"] = max(0, circuit["failures"] - 1)

    def record_failure(self, url: str) -> None:
        """Record a failed request."""
        host = self._get_host(url)

        with self._lock:
            circuit = self._circuits.get(host, {
                "state": self.CLOSED,
                "failures": 0,
                "successes": 0,
                "last_failure": 0,
                "half_open_count": 0,
            })
            self._circuits[host] = circuit

            circuit["failures"] += 1
            circuit["last_failure"] = time.time()

            if circuit["state"] == self.HALF_OPEN:
                circuit["state"] = self.OPEN
                logger.warning("Circuit %s: HALF_OPEN -> OPEN (test request failed)", host)
            elif circuit["state"] == self.CLOSED:
                if circuit["failures"] >= self.failure_threshold:
                    circuit["state"] = self.OPEN
                    logger.warning(
                        "Circuit %s: CLOSED -> OPEN (failures: %d)",
                        host, circuit["failures"]
                    )

    def get_state(self, url: str = "") -> Dict[str, Any]:
        """Get circuit state for a host or all hosts."""
        with self._lock:
            if url:
                host = self._get_host(url)
                circuit = self._circuits.get(host, {})
                return {"host": host, **circuit}
            else:
                return {
                    host: {k: v for k, v in c.items()}
                    for host, c in self._circuits.items()
                }

    def reset(self, url: str = "") -> None:
        """Reset circuit(s) to closed state."""
        with self._lock:
            if url:
                host = self._get_host(url)
                if host in self._circuits:
                    self._circuits[host] = {
                        "state": self.CLOSED,
                        "failures": 0,
                        "successes": 0,
                        "last_failure": 0,
                        "half_open_count": 0,
                    }
            else:
                for host in self._circuits:
                    self._circuits[host] = {
                        "state": self.CLOSED,
                        "failures": 0,
                        "successes": 0,
                        "last_failure": 0,
                        "half_open_count": 0,
                    }

    def get_stats(self) -> Dict[str, Any]:
        """Return circuit breaker statistics."""
        with self._lock:
            states = [c["state"] for c in self._circuits.values()]
            return {
                "total_hosts": len(self._circuits),
                "closed": states.count(self.CLOSED),
                "open": states.count(self.OPEN),
                "half_open": states.count(self.HALF_OPEN),
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_s": self.recovery_timeout,
            }

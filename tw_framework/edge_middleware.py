"""
TW Framework - Edge Middleware

Implements:
29. Edge-based Middleware (proxy.ts) - Edge Runtime middleware
30. Middleware + Edge Runtime - Request interception at edge
"""

from __future__ import annotations

import time
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EdgeRequest:
    """Represents an incoming request at the edge."""
    method: str = "GET"
    path: str = "/"
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    query: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    ip: str = ""
    country: str = ""
    user_agent: str = ""
    timestamp: float = field(default_factory=time.time)

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), self.headers.get(name, default))

    def cookie(self, name: str, default: str = "") -> str:
        return self.cookies.get(name, default)

    def query_param(self, name: str, default: str = "") -> str:
        return self.query.get(name, default)

    def is_get(self) -> bool: return self.method == "GET"
    def is_post(self) -> bool: return self.method == "POST"
    def is_api(self) -> bool: return self.path.startswith("/api/")


@dataclass
class EdgeResponse:
    """Represents an edge response."""
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = ""
    redirect_url: str = ""
    is_redirect: bool = False
    is_rewrite: bool = False
    rewrite_url: str = ""

    @staticmethod
    def json(data: Any, status: int = 200, headers: Optional[Dict] = None) -> "EdgeResponse":
        import json as _json
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        return EdgeResponse(status=status, headers=h, body=_json.dumps(data))

    @staticmethod
    def redirect(url: str, status: int = 307) -> "EdgeResponse":
        return EdgeResponse(status=status, redirect_url=url, is_redirect=True)

    @staticmethod
    def rewrite(url: str) -> "EdgeResponse":
        return EdgeResponse(is_rewrite=True, rewrite_url=url)

    @staticmethod
    def text(body: str, status: int = 200) -> "EdgeResponse":
        return EdgeResponse(status=status, headers={"Content-Type": "text/plain"}, body=body)

    @staticmethod
    def html(body: str, status: int = 200) -> "EdgeResponse":
        return EdgeResponse(status=status, headers={"Content-Type": "text/html"}, body=body)

    @staticmethod
    def not_found(body: str = "Not Found") -> "EdgeResponse":
        return EdgeResponse(status=404, headers={"Content-Type": "text/plain"}, body=body)

    @staticmethod
    def unauthorized(body: str = "Unauthorized") -> "EdgeResponse":
        return EdgeResponse(status=401, headers={"Content-Type": "text/plain"}, body=body)


@dataclass
class MiddlewareConfig:
    """Configuration for edge middleware."""
    matcher: List[str] = field(default_factory=list)  # Path patterns to match
    excluded_paths: List[str] = field(default_factory=list)
    runtime: str = "edge"  # edge | nodejs
    max_duration_ms: float = 30000
    geo_blocking: Dict[str, bool] = field(default_factory=dict)  # country -> blocked
    rate_limit_per_minute: int = 0
    cors_origins: List[str] = field(default_factory=list)
    security_headers: bool = True


class EdgeMiddleware:
    """Edge runtime middleware for request interception.

    Runs at the edge (close to the user) before the request reaches
    the origin server. Supports:
    - Request matching and filtering
    - Authentication and authorization
    - Rate limiting
    - Geo-blocking
    - A/B testing
    - Bot detection
    - Request rewriting and redirecting
    - Response header injection
    - CORS handling
    """

    def __init__(self, config: Optional[MiddlewareConfig] = None):
        self.config = config or MiddlewareConfig()
        self._handlers: List[Callable[[EdgeRequest], Optional[EdgeResponse]]] = []
        self._request_log: List[Dict[str, Any]] = []
        self._rate_limiter: Dict[str, List[float]] = {}

    def use(self, handler: Callable[[EdgeRequest], Optional[EdgeResponse]]) -> None:
        """Register a middleware handler."""
        self._handlers.append(handler)

    def match(self, path: str) -> bool:
        """Check if a path matches the middleware config."""
        # Check exclusions first
        for excluded in self.config.excluded_paths:
            if path.startswith(excluded):
                return False

        # If no matchers, match everything
        if not self.config.matcher:
            return True

        # Check each matcher
        for pattern in self.config.matcher:
            if self._match_pattern(pattern, path):
                return True

        return False

    @staticmethod
    def _match_pattern(pattern: str, path: str) -> bool:
        """Match a path against a pattern."""
        if pattern == "/":
            return True
        if pattern.endswith("/*"):
            return path.startswith(pattern[:-2])
        if pattern.endswith("/(.*)"):
            return path.startswith(pattern[:-5])
        if "[" in pattern and "]" in pattern:
            regex = re.escape(pattern)
            regex = re.sub(r"\\\[([^]]+)\\\]", r"([^/]+)", regex)
            return bool(re.match(f"^{regex}$", path))
        return pattern == path

    def process(self, request: EdgeRequest) -> EdgeResponse:
        """Process a request through all middleware handlers."""
        # Check if path matches
        if not self.match(request.path):
            return EdgeResponse(status=200)

        # Log request
        self._log_request(request)

        # Rate limiting
        if self.config.rate_limit_per_minute > 0:
            if not self._check_rate_limit(request.ip):
                return EdgeResponse(
                    status=429,
                    headers={"Retry-After": "60"},
                    body="Rate limit exceeded"
                )

        # Geo-blocking
        if request.country and self.config.geo_blocking.get(request.country, False):
            return EdgeResponse(
                status=403,
                body="Access denied from your region"
            )

        # Run handlers
        for handler in self._handlers:
            try:
                result = handler(request)
                if result is not None:
                    # Add security headers if enabled
                    if self.config.security_headers:
                        result.headers.update(self._security_headers())
                    # Add CORS headers if configured
                    if self.config.cors_origins:
                        result.headers.update(self._cors_headers(request))
                    return result
            except Exception as e:
                logger.error("Middleware handler error: %s", e)
                return EdgeResponse(status=500, body="Internal Server Error")

        # Default response (pass through)
        response = EdgeResponse(status=200)
        if self.config.security_headers:
            response.headers.update(self._security_headers())
        if self.config.cors_origins:
            response.headers.update(self._cors_headers(request))
        return response

    def _check_rate_limit(self, ip: str) -> bool:
        """Check if IP is within rate limit."""
        now = time.time()
        if ip not in self._rate_limiter:
            self._rate_limiter[ip] = [now]
            return True

        # Remove entries older than 1 minute
        self._rate_limiter[ip] = [t for t in self._rate_limiter[ip] if now - t < 60]

        if len(self._rate_limiter[ip]) >= self.config.rate_limit_per_minute:
            return False

        self._rate_limiter[ip].append(now)
        return True

    @staticmethod
    def _security_headers() -> Dict[str, str]:
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }

    def _cors_headers(self, request: EdgeRequest) -> Dict[str, str]:
        origin = request.header("origin")
        if origin in self.config.cors_origins:
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "86400",
            }
        return {}

    def _log_request(self, request: EdgeRequest) -> None:
        self._request_log.append({
            "method": request.method,
            "path": request.path,
            "ip": request.ip,
            "country": request.country,
            "timestamp": request.timestamp,
        })
        # Keep only last 1000 entries
        if len(self._request_log) > 1000:
            self._request_log = self._request_log[-1000:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_requests": len(self._request_log),
            "handlers": len(self._handlers),
            "rate_limited_ips": len(self._rate_limiter),
            "config": {
                "runtime": self.config.runtime,
                "matchers": self.config.matcher,
                "rate_limit": self.config.rate_limit_per_minute,
                "security_headers": self.config.security_headers,
            },
        }


class ProxyHandler:
    """Proxy handler for edge middleware (proxy.ts equivalent).

    Handles:
    - Request forwarding to origin servers
    - Load balancing across multiple origins
    - Health checking of upstream servers
    - Request/response transformation
    """

    def __init__(self):
        self._upstreams: List[Dict[str, Any]] = []
        self._health_status: Dict[str, bool] = {}
        self._round_robin_idx: int = 0

    def add_upstream(self, name: str, url: str, weight: int = 1,
                     health_check_path: str = "/health") -> None:
        self._upstreams.append({
            "name": name, "url": url, "weight": weight,
            "health_check_path": health_check_path,
        })
        self._health_status[name] = True

    def get_upstream(self) -> Optional[Dict[str, Any]]:
        """Get next healthy upstream (round-robin with weight)."""
        healthy = [u for u in self._upstreams if self._health_status.get(u["name"], True)]
        if not healthy:
            return None

        # Simple round-robin
        upstream = healthy[self._round_robin_idx % len(healthy)]
        self._round_robin_idx += 1
        return upstream

    def process_proxy(self, request: EdgeRequest) -> EdgeResponse:
        """Proxy a request to an upstream server."""
        upstream = self.get_upstream()
        if not upstream:
            return EdgeResponse(status=503, body="No upstream available")

        # In a real implementation, this would make an HTTP request
        # to the upstream URL. Here we return a placeholder.
        return EdgeResponse.json({
            "proxied": True,
            "upstream": upstream["name"],
            "original_path": request.path,
        })

    def check_health(self) -> Dict[str, bool]:
        """Check health of all upstreams."""
        return dict(self._health_status)


__all__ = [
    "EdgeRequest", "EdgeResponse", "MiddlewareConfig",
    "EdgeMiddleware", "ProxyHandler",
]

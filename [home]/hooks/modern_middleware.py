import base64
import hashlib
import hmac
import json
import os
import re
import time
from urllib.parse import urlparse


# Project-side "modern middleware" for TW.
# Runs via the new `beforeRequest` extension hook (see tw_framework/server.py + tw_framework/framework.py).
#
# It can:
# - Block/allow bots via User-Agent
# - Block known malicious scanner paths (return 404)
# - Rate limit
# - Protect /admin and /api/admin via HS256 JWT cookie
# - Enforce allowed origins for /api/*
#
# NOTE: This is in-memory and per-process; for multi-process production you’d use Redis.


SECRET = os.environ.get("JWT_SECRET") or "TwModsFallbackSecret2026!!"


ALLOWED_BOT_PATTERNS = [
    "googlebot", "google-inspectiontool", "adsbot-google",
    "mediapartners-google", "apis-google", "google-safety",
    "googleweblight", "storebot-google", "google-read-aloud",
    "googleother", "feedfetcher-google",
    "bingbot", "bingpreview", "msnbot",
    "gptbot", "chatgpt-user", "oai-searchbot",
    "claudebot", "anthropic-ai", "claude-web",
    "deepseekbot", "perplexitybot", "duckduckbot",
    "facebookexternalhit", "facebookbot",
    "twitterbot", "whatsapp", "telegrambot",
]

BLOCKED_UA_PATTERNS = [
    "marqvision", "markmonitor", "brandprotect", "dtecnet", "digimarc",
    "netnames", "opsec", "attributor", "tracer", "rivendell",
    "brandshield", "redpoints", "corsearch", "phishlabs",
    "riskiq", "appdetex", "smartprotection", "linkbusters",
    "websheriff", "zerofox", "khronoguard", "yellowbrand",
    "pointerbp", "rapidshield",
    "python-requests", "python-urllib", "scrapy",
    "wget/", "curl/", "httrack", "libwww", "lwp-", "mechanize",
    "go-http-client", "java/", "okhttp",
    "phantomjs", "slimerjs", "zgrab", "masscan",
    "semrushbot", "ahrefsbot", "mj12bot", "dotbot", "petalbot",
    "seznambot", "yandexbot", "baiduspider",
    "ccbot", "cohere-ai", "bytespider", "amazonbot",
    "diffbot", "omgilibot", "piplbot",
]

MALICIOUS_PATH_PATTERNS = [
    "/wp-login", "/wp-admin", "/wp-content", "/wp-includes", "/wordpress",
    "/xmlrpc", "/phpmyadmin", "/pma", "/.env", "/.git",
    "/config.php", "/setup.php", "/install.php", "/admin.php",
    "/shell", "/backdoor", "/eval", "/base64",
    "/cgi-bin", "/boaform", "/gponform",
    "/owa/", "/autodiscover", "/ecp/",
    "/actuator", "/manager/html", "/console",
]

MALICIOUS_EXTENSIONS = [
    ".php", ".asp", ".aspx", ".jsp", ".cgi", ".pl", ".py",
    ".env", ".sql", ".bak", ".config", ".xml.bak",
    ".htaccess", ".htpasswd",
]

SUPPORTED_LANGS = ["ar", "de", "fr", "es", "pt", "hi", "ur", "id", "tr"]

BLOCKED_HTML = b"<!DOCTYPE html><html><head><title>Access Denied</title></head><body><h1>403 Forbidden</h1></body></html>"
RATE_HTML = b"<!DOCTYPE html><html><head><title>Too Many Requests</title></head><body><h1>429 Too Many Requests</h1></body></html>"


def _lower(s: str) -> str:
    return (s or "").lower()


def is_allowed_bot(ua: str) -> bool:
    u = _lower(ua)
    return any(p in u for p in ALLOWED_BOT_PATTERNS)


def is_blocked_bot(ua: str) -> bool:
    if not ua:
        return True
    u = _lower(ua)
    if is_allowed_bot(u):
        return False
    return any(p in u for p in BLOCKED_UA_PATTERNS)


def parse_cookie_header(raw: str) -> dict:
    cookies = {}
    if not raw:
        return cookies
    for part in raw.split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        cookies[k.strip()] = v.strip()
    return cookies


def b64url_decode(data: str) -> bytes:
    data = data.replace("-", "+").replace("_", "/")
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.b64decode(data + padding)


def verify_jwt_hs256(token: str) -> bool:
    try:
        parts = (token or "").split(".")
        if len(parts) != 3:
            return False
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected = hmac.new(SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        got = b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, got):
            return False
        payload = json.loads(b64url_decode(payload_b64).decode("utf-8", errors="replace") or "{}")
        exp = payload.get("exp")
        if exp and time.time() > float(exp):
            return False
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────
# Rate limiting (in-memory)
# ──────────────────────────────────────────────
_rate_map = {}

RATE_LIMITS = {
    "/api/download": {"max": 5, "window_s": 60},
    "/api/search": {"max": 20, "window_s": 60},
    "/api/telegram": {"max": 3, "window_s": 60},
    "/api/": {"max": 60, "window_s": 60},
    "default": {"max": 120, "window_s": 60},
}


def get_rate_limit(path: str) -> dict:
    for prefix, limit in RATE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return limit
    return RATE_LIMITS["default"]


def check_rate_limit(ip: str, path: str) -> tuple[bool, float]:
    limit = get_rate_limit(path)
    max_req = int(limit["max"])
    window_s = float(limit["window_s"])
    bucket = "/".join(path.split("/")[:3])  # similar to next example: /api/x
    key = f"{ip}:{bucket}"
    now = time.time()
    entry = _rate_map.get(key)
    if not entry or now > entry["reset_at"]:
        _rate_map[key] = {"count": 1, "reset_at": now + window_s}
        return True, now + window_s
    entry["count"] += 1
    if entry["count"] > max_req:
        return False, float(entry["reset_at"])
    return True, float(entry["reset_at"])


def get_ip(headers: dict, request_meta: dict) -> str:
    # user can pass x-user-ip from proxy
    for key in ["x-user-ip", "cf-connecting-ip", "x-vercel-forwarded-for", "x-forwarded-for", "x-real-ip"]:
        val = headers.get(key) or headers.get(key.title())
        if not val:
            continue
        return str(val).split(",")[0].replace("::ffff:", "").strip()
    return (request_meta or {}).get("client_ip") or "127.0.0.1"


def _is_asset_path(path: str) -> bool:
    return bool(re.search(r"\.(ico|png|jpg|jpeg|gif|webp|avif|svg|css|js|woff2?)$", path, re.I))


def _resp(status: int, body: bytes, content_type: str, headers=None, cookies=None) -> dict:
    return {
        "status": int(status),
        "body": body,
        "content_type": content_type,
        "headers": list(headers or []),
        "cookies": list(cookies or []),
    }


def before_request(payload: dict) -> dict:
    method = str(payload.get("method") or "GET")
    url_path = str(payload.get("url_path") or "/")
    headers = dict(payload.get("request_headers") or {})
    request_meta = dict(payload.get("request_meta") or {})
    ua = str(headers.get("User-Agent") or headers.get("user-agent") or "")
    ip = get_ip(headers, request_meta)

    url_lower = url_path.lower()

    # ✅ Allowed bots: block /admin except /admin/login
    if is_allowed_bot(ua):
        if url_lower.startswith("/admin") and url_lower != "/admin/login":
            return {"response": _resp(403, BLOCKED_HTML, "text/html; charset=utf-8")}
        return {}

    # 🚫 Blocked bots / missing UA
    if is_blocked_bot(ua):
        return {"response": _resp(403, BLOCKED_HTML, "text/html; charset=utf-8")}

    # 🚫 malicious scanner paths -> 404
    if any(url_lower.startswith(p) or p in url_lower for p in MALICIOUS_PATH_PATTERNS):
        return {"response": _resp(404, b"Not Found", "text/plain; charset=utf-8")}
    if any(url_lower.endswith(ext) for ext in MALICIOUS_EXTENSIONS):
        return {"response": _resp(404, b"Not Found", "text/plain; charset=utf-8")}

    # 🚫 slug sanity check (single segment)
    m = re.match(r"^/([^/?#]+)$", url_path)
    if m:
        slug = m.group(1)
        if (
            len(slug) > 100
            or ".." in slug
            or "%00" in slug.lower()
            or re.search(r"[<>{}|\^`\[\]]", slug)
            or re.match(r"^\*+$", slug)
            or re.match(r"^[a-z]{1,3}[0-9]{5,}$", slug, re.I)
        ):
            return {"response": _resp(404, b"Not Found", "text/plain; charset=utf-8")}

    # ✅ Language prefix rewrite (no redirect)
    parts = [p for p in url_path.split("/") if p]
    if parts and parts[0] in SUPPORTED_LANGS:
        rest = parts[1:]
        rewritten = "/" + "/".join(rest) if rest else "/"
        # Keep public URL same, rewrite internal routing target
        return {"rewrite": rewritten}

    # Rate limit (skip static)
    if not url_path.startswith("/_tw/") and not _is_asset_path(url_path):
        allowed, reset_at = check_rate_limit(ip, url_path)
        if not allowed:
            retry_after = str(max(1, int(reset_at - time.time())))
            if url_lower.startswith("/api/"):
                body = json.dumps({"error": "Too many requests", "retryAfter": retry_after}).encode("utf-8")
                return {"response": _resp(429, body, "application/json; charset=utf-8", headers=[("Retry-After", retry_after)])}
            return {"response": _resp(429, RATE_HTML, "text/html; charset=utf-8", headers=[("Retry-After", retry_after)])}

    # Admin routes (/admin/*): cookie JWT
    if url_lower.startswith("/admin") and url_lower != "/admin/login":
        token = parse_cookie_header(str(headers.get("Cookie") or headers.get("cookie") or "")).get("admin_token")
        if not token or not verify_jwt_hs256(token):
            return {"redirect": "/admin/login"}

    # API: origin check + /api/admin JWT
    if url_lower.startswith("/api/"):
        if url_lower.startswith("/api/admin/") and url_lower != "/api/admin/login":
            token = parse_cookie_header(str(headers.get("Cookie") or headers.get("cookie") or "")).get("admin_token")
            if not token:
                body = json.dumps({"error": "Unauthorized"}).encode("utf-8")
                return {"response": _resp(401, body, "application/json; charset=utf-8")}
            if not verify_jwt_hs256(token):
                body = json.dumps({"error": "Invalid token"}).encode("utf-8")
                return {"response": _resp(401, body, "application/json; charset=utf-8")}
            return {}

        allowed_origins = {
            "https://twmods.in",
            "https://twmods-next.vercel.app",
            "https://twmods.vercel.app",
            "http://localhost:3000",
        }
        origin = str(headers.get("Origin") or headers.get("origin") or "")
        referer = str(headers.get("Referer") or headers.get("referer") or "")
        parsed = urlparse(referer) if referer else None
        ref_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed and parsed.scheme and parsed.netloc else ""
        if origin and origin not in allowed_origins and ref_origin and ref_origin not in allowed_origins:
            body = json.dumps({"error": "Access Denied"}).encode("utf-8")
            return {"response": _resp(403, body, "application/json; charset=utf-8")}

    return {}


hooks = {
    "beforeRequest": before_request,
}


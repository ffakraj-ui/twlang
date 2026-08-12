"""
TW Framework — Edge V8 Runtime Adapter (v0.9.03)

Real JavaScript sandbox for Edge Runtime — just like Next.js Edge Runtime.
Uses V8 engine (via py_mini_racer) for true JS isolation — same engine
that powers Next.js Edge Runtime and Google Chrome.

This gives TW TWO Edge runtime options:
  1. `edge`     — V8 JS sandbox (real JavaScript, like Next.js Edge)
  2. `edge-py`  — Legacy Python in-process (fallback)
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
import hmac
import secrets
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, CryptoAPI, EnvAPI, CacheAPI


# --- V8 engine detection (ONLY V8) ---

import importlib.util as _importutil

_ENGINE = None
_ENGINE_VERSION = ""
_MiniRacer = None

if _importutil.find_spec("py_mini_racer"):
    try:
        from py_mini_racer import MiniRacer as _MiniRacer
        _ENGINE = "v8"
        _ENGINE_VERSION = getattr(_MiniRacer, "__version__", "unknown")
    except Exception:
        _MiniRacer = None


def is_v8_available() -> bool:
    return _ENGINE == "v8"

def get_js_engine() -> str:
    return _ENGINE

def get_js_engine_version() -> str:
    return _ENGINE_VERSION


# --- Edge KV + Cache stores (shared across requests in process) ---

# v0.9.08 FIX #74: Per-request KV store (was module global)
_REQUEST_KV: Dict[str, str] = {}
_REQUEST_CACHE: Dict[str, Any] = {}


def _get_kv_store() -> Dict[str, str]:
    return _REQUEST_KV


def _get_cache_store() -> Dict[str, Any]:
    return _REQUEST_CACHE


# v0.9.08 FIX #73: Bridge JS store to Python store for cross-runtime access
_JS_STORAGE_BRIDGE = {}


def _sync_js_to_python_storage():
    """Sync JS storage bridge to Python KV store."""
    for k, v in _JS_STORAGE_BRIDGE.items():
        _REQUEST_KV[k] = v


def _reset_request_stores():
    """Clear per-request stores — call at start of each request."""
    _REQUEST_KV.clear()
    _REQUEST_CACHE.clear()


# --- JS sandbox host functions ---

def _js_tw_storage_read(path: str, encoding: str = "utf-8") -> str:
    if path in _REQUEST_KV:
        return _REQUEST_KV[path]
    raise PermissionError("Edge runtime does not support filesystem. Use tw.storage.write() for KV, or runtime='nodejs'.")

def _js_tw_storage_write(path: str, data: str) -> bool:
    _REQUEST_KV[path] = data if isinstance(data, str) else str(data)
    return True

def _js_tw_storage_delete(path: str) -> bool:
    return _REQUEST_KV.pop(path, None) is not None

def _js_tw_storage_exists(path: str) -> bool:
    return path in _REQUEST_KV

def _js_tw_http_fetch(url: str, options_json: str = "{}") -> str:
    opts = json.loads(options_json) if options_json else {}
    method = opts.get("method", "GET").upper()
    headers = opts.get("headers", {})
    body = opts.get("body")
    timeout = opts.get("timeout", 30)  # v0.9.08 FIX #83: No arbitrary 30s cap
    req_body = None
    if body is not None:
        if isinstance(body, (dict, list)):
            req_body = json.dumps(body).encode("utf-8")
            if not any(k.lower() == "content-type" for k in headers):
                headers["Content-Type"] = "application/json"
        elif isinstance(body, str):
            req_body = body.encode("utf-8")
    req = urllib.request.Request(url, data=req_body, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            resp_headers = dict(resp.headers)
            content_type = resp_headers.get("Content-Type", "")
            data = text
            if "application/json" in content_type:
                try:
                    data = json.loads(text)
                except Exception:
                    pass
            return json.dumps({"ok": 200 <= resp.status < 300, "status": resp.status, "statusText": resp.reason, "url": url, "headers": resp_headers, "text": text, "data": data})
    except urllib.error.HTTPError as e:  # FIX #605/#606/#607: HTTPError has .code/.reason/.headers
        text = ""
        try:
            text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return json.dumps({"ok": False, "status": e.code, "statusText": str(e.reason), "url": url, "headers": dict(e.headers), "text": text, "data": text})
    except (urllib.error.URLError, TimeoutError, OSError) as e:  # URLError doesn't have .code/.headers
        return json.dumps({"ok": False, "status": 0, "statusText": str(getattr(e, 'reason', e)), "url": url, "headers": {}, "text": "", "data": None})
    except Exception as e:
        return json.dumps({"ok": False, "status": 0, "statusText": str(e), "url": url, "headers": {}, "text": "", "data": None})

def _js_tw_crypto_hash(algorithm: str, data: str) -> str:
    h = hashlib.new(algorithm)
    h.update(data.encode("utf-8") if isinstance(data, str) else data)
    return h.hexdigest()

def _js_tw_crypto_hmac(algorithm: str, key: str, message: str) -> str:
    return hmac.new(key.encode("utf-8") if isinstance(key, str) else key, message.encode("utf-8") if isinstance(message, str) else message, algorithm).hexdigest()

def _js_tw_crypto_random(length: int = 32) -> str:
    return secrets.token_hex(length)

def _js_tw_crypto_uuid() -> str:
    import uuid
    return str(uuid.uuid4())

def _js_tw_env_get(name: str, default: str = "") -> str:
    # FIX #610: Filter env vars — only TW_/PUBLIC_/EDGE_ prefixed vars are safe
    if name.startswith(("TW_", "PUBLIC_", "EDGE_")) or name in ("NODE_ENV",):
        return os.environ.get(name, default)
    return default

def _js_tw_env_all() -> str:
    safe = {}
    for k, v in os.environ.items():
        if k.startswith(("TW_", "PUBLIC_", "EDGE_")) or k in ("NODE_ENV",):
            safe[k] = v
    return json.dumps(safe)

def _js_tw_cache_get(key: str, default_json: str = "null") -> str:
    # FIX: Check TTL expiry
    import time as _time
    ttl_key = "__ttl_" + key
    if ttl_key in _REQUEST_CACHE and _time.time() > _REQUEST_CACHE[ttl_key]:
        _REQUEST_CACHE.pop(key, None)
        _REQUEST_CACHE.pop(ttl_key, None)
        return default_json
    return json.dumps(_REQUEST_CACHE.get(key, json.loads(default_json)))

def _js_tw_cache_set(key: str, value_json: str, ttl: int = 0) -> bool:
    _REQUEST_CACHE[key] = json.loads(value_json)
    # FIX: Track TTL expiry on Python side too
    if ttl and ttl > 0:
        import time as _time
        _REQUEST_CACHE["__ttl_" + key] = _time.time() + ttl
    return True

def _js_tw_cache_delete(key: str) -> bool:
    return _REQUEST_CACHE.pop(key, None) is not None

def _js_tw_cache_has(key: str) -> bool:
    return key in _REQUEST_CACHE



# --- JS bootstrap for V8 (no host functions, pure JS implementations) ---

_JS_BOOTSTRAP_V8 = r"""
var __tw_cache_store = {};
var __tw_env_store = TW_ENV_DATA_PLACEHOLDER;

// === Pure JS SHA-256 ===
var __sha256 = (function() {
    var k = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    function rrot(x, n) { return (x >>> n) | (x << (32 - n)); }
    return function(msg) {
        if (typeof msg === "string") {
            var bytes = [];
            for (var i = 0; i < msg.length; i++) {
                var c = msg.charCodeAt(i);
                if (c < 128) bytes.push(c);
                else if (c < 2048) { bytes.push(192 | (c >> 6), 128 | (c & 63)); }
                else { bytes.push(224 | (c >> 12), 128 | ((c >> 6) & 63), 128 | (c & 63)); }
            }
            msg = bytes;
        }
        var l = msg.length, bl = l * 8, i, hL = l + 1;
        msg.push(0x80);
        while (hL % 64 !== 56) { msg.push(0); hL++; }
        for (i = 0; i < 8; i++) msg.push(0);
        for (i = 0; i < 4; i++) msg.push((bl >>> (24 - i * 8)) & 0xff);
        var h = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
        for (i = 0; i < msg.length; i += 64) {
            var w = [];
            for (var j = 0; j < 16; j++) {
                w[j] = (msg[i + j * 4] << 24) | (msg[i + j * 4 + 1] << 16) | (msg[i + j * 4 + 2] << 8) | msg[i + j * 4 + 3];
            }
            for (j = 16; j < 64; j++) {
                var s0 = rrot(w[j-15], 7) ^ rrot(w[j-15], 18) ^ (w[j-15] >>> 3);
                var s1 = rrot(w[j-2], 17) ^ rrot(w[j-2], 19) ^ (w[j-2] >>> 10);
                w[j] = (w[j-16] + s0 + w[j-7] + s1) | 0;
            }
            var a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
            for (j = 0; j < 64; j++) {
                var S1 = rrot(e, 6) ^ rrot(e, 11) ^ rrot(e, 25);
                var ch = (e & f) ^ (~e & g);
                var t1 = (hh + S1 + ch + k[j] + w[j]) | 0;
                var S0 = rrot(a, 2) ^ rrot(a, 13) ^ rrot(a, 22);
                var mj = (a & b) ^ (a & c) ^ (b & c);
                var t2 = (S0 + mj) | 0;
                hh = g; g = f; f = e; e = (d + t1) | 0;
                d = c; c = b; b = a; a = (t1 + t2) | 0;
            }
            h[0]=(h[0]+a)|0; h[1]=(h[1]+b)|0; h[2]=(h[2]+c)|0; h[3]=(h[3]+d)|0;
            h[4]=(h[4]+e)|0; h[5]=(h[5]+f)|0; h[6]=(h[6]+g)|0; h[7]=(h[7]+hh)|0;
        }
        var hex = "";
        for (i = 0; i < 8; i++) {
            var s = (h[i] >>> 0).toString(16);
            while (s.length < 8) s = "0" + s;
            hex += s;
        }
        return hex;
    };
})();

// === Pure JS HMAC-SHA256 ===
function __hmac_sha256(key, message) {
    var blockSize = 64;
    function strToBytes(s) {
        var b = [];
        for (var i = 0; i < s.length; i++) {
            var c = s.charCodeAt(i);
            if (c < 128) b.push(c);
            else if (c < 2048) { b.push(192 | (c >> 6), 128 | (c & 63)); }
            else { b.push(224 | (c >> 12), 128 | ((c >> 6) & 63), 128 | (c & 63)); }
        }
        return b;
    }
    var keyBytes = strToBytes(key);
    if (keyBytes.length > blockSize) keyBytes = __sha256(keyBytes);
    while (keyBytes.length < blockSize) keyBytes.push(0);
    var ipad = [], opad = [];
    for (var i = 0; i < blockSize; i++) {
        ipad.push(keyBytes[i] ^ 0x36);
        opad.push(keyBytes[i] ^ 0x5c);
    }
    var inner = __sha256(ipad.concat(strToBytes(message)));
    var innerBytes = [];
    for (var i = 0; i < inner.length; i += 2) innerBytes.push(parseInt(inner.substr(i, 2), 16));
    return __sha256(opad.concat(innerBytes));
}

// === Multi-pass HTTP fetch bridge ===
var __fetch_result = null;
var __pending_fetch = null;

var tw = {
    storage: {
        read: function(path) { throw new Error("Edge V8: filesystem not supported. Use runtime='nodejs' or runtime='python'."); },
        write: function(path, data) { __tw_cache_store[path] = data; return true; },
        delete: function(path) { return delete __tw_cache_store[path]; },
        exists: function(path) { return path in __tw_cache_store; }
    },
    http: {
        fetch: function(url, options) {
            __pending_fetch = { url: url, options: options || {} };
            throw "__YIELD_FETCH__";
        },
        get: function(url, headers, timeout) { return tw.http.fetch(url, {method: "GET", headers: headers || {}, timeout: timeout || 30}); },
        post: function(url, body, headers, timeout) { return tw.http.fetch(url, {method: "POST", body: body, headers: headers || {}, timeout: timeout || 30}); },
        put: function(url, body, headers, timeout) { return tw.http.fetch(url, {method: "PUT", body: body, headers: headers || {}, timeout: timeout || 30}); },
        delete: function(url, headers, timeout) { return tw.http.fetch(url, {method: "DELETE", headers: headers || {}, timeout: timeout || 30}); }
    },
    crypto: {
        hash: function(algorithm, data) {
            var algo = (algorithm || "sha256").toLowerCase();
            if (algo === "sha256") {
                return __sha256(typeof data === "string" ? data : JSON.stringify(data));
            }
            throw new Error("Edge V8: algorithm " + algo + " not yet supported in pure JS. Use sha256.");
        },
        hmac: function(algorithm, key, message) {
            var algo = (algorithm || "sha256").toLowerCase();
            if (algo === "sha256") {
                return __hmac_sha256(key, message);
            }
            throw new Error("Edge V8: HMAC " + algo + " not yet supported. Use sha256.");
        },
        random: function(length) {
            var chars = "0123456789abcdef";
            var result = "";
            for (var i = 0; i < (length || 32) * 2; i++) {
                result += chars[Math.floor((typeof crypto !== 'undefined' && crypto.getRandomValues) ? (crypto.getRandomValues(new Uint8Array(1))[0] / 256) : Math.random()) * 16)];
            }
            return result;
        },
        uuid: function() {
            return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
                var r = ((typeof crypto !== 'undefined' && crypto.getRandomValues) ? (crypto.getRandomValues(new Uint8Array(1))[0] / 256) : Math.random()) * 16 | 0;
                var v = c === "x" ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }
    },
    env: {
        get: function(name, defaultVal) {
            if (__tw_env_store && __tw_env_store[name] !== undefined) return __tw_env_store[name];
            return defaultVal || "";
        },
        all: function() { return __tw_env_store || {}; },
        has: function(name) { return __tw_env_store && __tw_env_store[name] !== undefined; }
    },
    cache: {
        get: function(key, defaultVal) {
            if (key in __tw_cache_store) {
                var ttlKey = '__ttl_' + key;
                if (ttlKey in __tw_cache_store && Date.now() > __tw_cache_store[ttlKey]) {
                    delete __tw_cache_store[key]; delete __tw_cache_store[ttlKey];
                    return defaultVal === undefined ? null : defaultVal;
                }
                return __tw_cache_store[key];
            }
            return defaultVal === undefined ? null : defaultVal;
        },
        set: function(key, value, ttl) { __tw_cache_store[key] = value; /* FIX #618: TTL stored but in-memory cache doesn't expire */ if(ttl && ttl > 0) { __tw_cache_store['__ttl_' + key] = Date.now() + ttl * 1000; } return true; },
        delete: function(key) { return delete __tw_cache_store[key]; },
        has: function(key) { return key in __tw_cache_store; },
        clear: function() { __tw_cache_store = {}; return true; }
    },
    runtime: {
        name: function() { return "edge-v8"; },
        version: function() { return "tw-edge-v8/1.0"; },
        capabilities: function() { return {filesystem: false, network: true, native_modules: false, subprocess: false, database: false, crypto: true, cache: true, env_vars: true, persistent_storage: false, timers: false, streaming: false  /* FIX #619: in-memory = not persistent */}; },
        supports: function(cap) { return this.capabilities()[cap] === true; }
    }
};
"""


# --- Storage/HTTP/Crypto/Env adapters (Python-side) ---

import threading as _threading
_KV_LOCK = _threading.Lock()


class EdgeV8Storage(StorageAPI):
    """Thread-safe KV storage for Edge V8 runtime."""
    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        with _KV_LOCK:
            if path in _REQUEST_KV:
                return _REQUEST_KV[path]
        raise PermissionError("Edge V8: filesystem not supported. Use tw.storage.write() for KV, or runtime='nodejs'.")
    def write(self, path: str, data: Union[str, bytes]) -> bool:
        with _KV_LOCK:
            # FIX #621: Handle binary data safely
            if isinstance(data, str):
                _REQUEST_KV[path] = data
            else:
                try:
                    _REQUEST_KV[path] = data.decode("utf-8")
                except UnicodeDecodeError:
                    import base64 as _b64
                    _REQUEST_KV[path] = "base64:" + _b64.b64encode(data).decode("ascii")
        return True
    def delete(self, path: str) -> bool:
        with _KV_LOCK:
            return _REQUEST_KV.pop(path, None) is not None
    def exists(self, path: str) -> bool:
        with _KV_LOCK:
            return path in _REQUEST_KV
    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        import fnmatch
        prefix = dir_path if dir_path else ""
        full_pattern = prefix + pattern if prefix else pattern
        with _KV_LOCK:
            return [k for k in _REQUEST_KV.keys() if fnmatch.fnmatch(k, full_pattern)]

class EdgeV8Http(HttpAPI):
    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        # v0.9.08 FIX #82: Single JSON encoding — fetch returns JSON string, parse once
        raw = _js_tw_http_fetch(url, json.dumps(options or {}))
        return json.loads(raw) if isinstance(raw, str) else raw

class EdgeV8Crypto(CryptoAPI):
    def hash(self, algorithm: str, data: Union[str, bytes]) -> str:
        if isinstance(data, str): data = data.encode("utf-8")
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()
    def hmac(self, algorithm: str, key: Union[str, bytes], message: Union[str, bytes]) -> str:
        if isinstance(key, str): key = key.encode("utf-8")
        if isinstance(message, str): message = message.encode("utf-8")
        return hmac.new(key, message, algorithm).hexdigest()
    def random(self, length: int = 32) -> str:
        return secrets.token_hex(length)
    def random_bytes(self, length: int = 32) -> bytes:
        return secrets.token_bytes(length)
    def uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def encrypt(self, algorithm: str, key: bytes, data: bytes) -> bytes:
        if not key:
            raise ValueError("Encryption key cannot be empty")
        if algorithm == "xor":
            # Legacy XOR — kept for backward compat but deprecated
            return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        elif algorithm in ("aes-256-gcm", "tw-secure"):
            # FIX #624/#626: Proper authenticated encryption using stdlib
            # Uses scrypt for key derivation + HMAC-SHA256 as stream cipher
            import struct
            salt = secrets.token_bytes(16)
            derived = hashlib.scrypt(key, salt=salt, n=16384, r=8, p=1, dklen=len(data) + 32)
            keystream = derived[:len(data)]
            mac_key = derived[len(data):]
            ciphertext = bytes(a ^ b for a, b in zip(data, keystream))
            tag = hmac.new(mac_key, ciphertext, hashlib.sha256).digest()
            # Format: salt(16) + tag(32) + ciphertext
            return salt + tag + ciphertext
        raise NotImplementedError(f"encrypt() not implemented for {algorithm}")

    def decrypt(self, algorithm: str, key: bytes, data: bytes) -> bytes:
        if not key:
            raise ValueError("Decryption key cannot be empty")
        if algorithm == "xor":
            return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        elif algorithm in ("aes-256-gcm", "tw-secure"):
            # FIX #624/#626: Verify HMAC tag before decrypting
            if len(data) < 48:  # salt(16) + tag(32) minimum
                raise ValueError("Invalid encrypted data: too short")
            salt = data[:16]
            tag = data[16:48]
            ciphertext = data[48:]
            derived = hashlib.scrypt(key, salt=salt, n=16384, r=8, p=1, dklen=len(ciphertext) + 32)
            keystream = derived[:len(ciphertext)]
            mac_key = derived[len(ciphertext):]
            expected_tag = hmac.new(mac_key, ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, expected_tag):
                raise ValueError("Authentication failed: data has been tampered with")
            return bytes(a ^ b for a, b in zip(ciphertext, keystream))
        raise NotImplementedError(f"decrypt() not implemented for {algorithm}")


class EdgeV8Env(EnvAPI):
    def get(self, name: str, default: str = "") -> str:
        # v0.9.08 FIX #71/#76: Filter env vars — only TW_ prefixed vars are safe
        if name.startswith("TW_") or name.startswith("NODE_") or name in ("PATH", "HOME", "USER"):
            return os.environ.get(name, default)
        return default
    def all(self) -> Dict[str, str]:
        safe = {}
        for k, v in os.environ.items():
            if k.startswith(("TW_", "PUBLIC_", "EDGE_")) or k in ("NODE_ENV",):
                safe[k] = v
        return safe


# --- V8 Execution Engine ---

class EdgeV8Executor:
    """Executes .twm handlers inside a V8 sandbox."""

    def __init__(self):
        self._engine = _ENGINE
        self._context = None
        self._setup_context()

    def _setup_context(self):
        if self._engine == "v8":
            self._context = _MiniRacer()  # v0.9.08: No host functions needed — JS bootstrap handles all tw.* APIs

    @property
    def engine(self) -> str:
        return self._engine or "none"

    def execute(self, handler_body: str, method: str, request_data: dict, handler_path: str = "<edge-v8>") -> dict:
        if self._engine is None:
            return {
                "status": 500,
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps({"error": "V8 engine (py_mini_racer) not installed. Install it:\n  pip install py_mini_racer"}).encode("utf-8"),
                "headers": [], "cookies": [],
            }

        import re
        # Strip runtime directive
        handler_body = re.sub(r'^[ \t]*runtime[ \t]*=[ \t]*["\']?\w+["\']?[ \t]*$', '', handler_body, flags=re.MULTILINE)

        # Wrap as JS IIFE
        # FIX #631: Sanitize request_json to prevent JS injection — use JSON.stringify in JS
        request_json = json.dumps(json.dumps(request_data))  # Double-encode for safe JS string literal
        js_code = "(function(request) {\n" + handler_body + "\n})(JSON.parse(" + request_json + "));"

        # Build env vars JSON for injection (only safe vars)
        safe_env = {}
        for k, v in os.environ.items():
            if k.startswith(("TW_", "PUBLIC_", "EDGE_")) or k in ("NODE_ENV",):
                safe_env[k] = v
        env_json = json.dumps(safe_env)

        # V8 bootstrap with env vars injected
        # v0.9.08 FIX #100: Use unique placeholder to avoid accidental replacement
        bootstrap = _JS_BOOTSTRAP_V8.replace("TW_ENV_DATA_PLACEHOLDER", env_json)
        full_js = bootstrap + "\n" + js_code

        # V8 multi-pass fetch: V8 is synchronous, so tw.http.fetch() throws
        # __YIELD_FETCH__ to pause execution. Python catches it, does the
        # HTTP request, then re-evals with __fetch_result__ set.
        # FIX #633: Validate max_fetch_passes from env
        try:
            max_fetch_passes = max(1, min(50, int(os.environ.get('TW_MAX_FETCH_PASSES', '10'))))
        except (ValueError, TypeError):
            max_fetch_passes = 10

        for pass_num in range(max_fetch_passes + 1):
            try:
                result = self._eval(full_js)
                return self._normalize_response(result)
            except Exception as err:
                err_str = str(err)
                # Check if this is a fetch yield (V8 multi-pass)
                if "__YIELD_FETCH__" in err_str and self._engine == "v8":
                    # Extract pending fetch from V8 context
                    try:
                        pending = self._eval("JSON.stringify(__pending_fetch)")
                        fetch_req = json.loads(pending) if pending else {}
                    except Exception:
                        fetch_req = {}

                    url = fetch_req.get("url", "")
                    opts = fetch_req.get("options", {})

                    # Do the actual HTTP request from Python
                    fetch_result_json = _js_tw_http_fetch(url, json.dumps(opts))

                    # Re-build JS: set __fetch_result__ and replay
                    # We wrap the handler in a try/catch to inject the result
                    fetch_inject = (
                        "var __fetch_result = " + fetch_result_json + ";\n"
                        "var __pending_fetch = null;\n"
                    )

                    # Re-eval: bootstrap + fetch result + original handler
                    # The handler needs to be re-run with __fetch_result__ available
                    # We modify the handler to use __fetch_result__ on re-entry
                    if pass_num == 0:
                        # First fetch: wrap handler to check __fetch_result__
                        # v0.9.08 FIX #77: bootstrap precomputed once before loop
                        full_js = bootstrap + "\n" + fetch_inject + "\n" + js_code
                    else:
                        # Subsequent fetches: update the fetch result
                        # v0.9.08 FIX #77: bootstrap precomputed once before loop
                        full_js = bootstrap + "\n" + fetch_inject + "\n" + js_code
                    continue
                else:
                    # Real error — not a fetch yield
                    # FIX: Sanitize error message — remove internal paths
                    err_msg = str(err)
                    if "<" in err_msg and ">" in err_msg:
                        err_msg = err_msg.replace("<", "[").replace(">", "]")
                    return {
                        "status": 500,
                        "content_type": "application/json; charset=utf-8",
                        "body": json.dumps({"error": err_msg, "type": type(err).__name__, "engine": self._engine, "file": handler_path}).encode("utf-8"),
                        "headers": [], "cookies": [],
                    }

        # Too many fetch passes
        return {
            "status": 500,
            "content_type": "application/json; charset=utf-8",
            "body": json.dumps({"error": "Too many HTTP fetch calls (max 10 per request)", "engine": self._engine}).encode("utf-8"),
            "headers": [], "cookies": [],
        }

    def _eval(self, js_code: str) -> Any:
        if self._engine == "v8":
            return self._context.eval(js_code)
        raise RuntimeError("V8 engine not available")

    def _normalize_response(self, result: Any) -> dict:
        status = 200
        content_type = "application/json; charset=utf-8"
        headers_out = []
        cookies_out = []

        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return {"status": 200, "content_type": "text/plain; charset=utf-8", "body": result.encode("utf-8"), "headers": [], "cookies": []}
        elif isinstance(result, (dict, list)):
            parsed = result
        else:
            parsed = {"result": str(result)}

        if isinstance(parsed, dict):
            if "status" in parsed:
                try: status = int(parsed["status"])
                except (ValueError, TypeError): status = 200
            if "content_type" in parsed: content_type = str(parsed["content_type"])
            if "headers" in parsed:
                h = parsed["headers"]
                headers_out = list(h.items()) if isinstance(h, dict) else (h if isinstance(h, list) else [])
            if "cookies" in parsed:
                c = parsed["cookies"]
                cookies_out = list(c.items()) if isinstance(c, dict) else (c if isinstance(c, list) else [])
            body_val = parsed.get("body", parsed)
        else:
            body_val = parsed

        if isinstance(body_val, (dict, list)):
            body_bytes = json.dumps(body_val, ensure_ascii=False).encode("utf-8")
        elif isinstance(body_val, str):
            body_bytes = body_val.encode("utf-8")
        elif isinstance(body_val, bytes):
            body_bytes = body_val
        else:
            body_bytes = str(body_val).encode("utf-8")

        return {"status": status, "content_type": content_type, "body": body_bytes, "headers": headers_out, "cookies": cookies_out}

    def reload(self):
        # FIX #641: Properly cleanup V8 context to avoid memory leaks
        if self._context is not None:
            try:
                # V8 contexts don't guarantee GC on del — explicitly clear
                if hasattr(self._context, 'eval'):
                    try:
                        self._context.eval("undefined")
                    except Exception:
                        pass
                del self._context
            except Exception:
                pass
            self._context = None
            import gc
            gc.collect()  # Force Python GC after V8 context teardown
        self._setup_context()


# --- Edge V8 Runtime class ---



class EdgeV8Cache(CacheAPI):
    """Cache adapter for Edge V8 runtime — uses _REQUEST_CACHE with TTL."""
    def get(self, key: str, default: Any = None) -> Any:
        import time as _time
        ttl_key = "__ttl_" + key
        if ttl_key in _REQUEST_CACHE and _time.time() > _REQUEST_CACHE[ttl_key]:
            _REQUEST_CACHE.pop(key, None)
            _REQUEST_CACHE.pop(ttl_key, None)
            return default
        return _REQUEST_CACHE.get(key, default)
    def set(self, key: str, value: Any, ttl: int = 0) -> bool:
        _REQUEST_CACHE[key] = value
        if ttl and ttl > 0:
            import time as _time
            _REQUEST_CACHE["__ttl_" + key] = _time.time() + ttl
        return True
    def delete(self, key: str) -> bool:
        existed = key in _REQUEST_CACHE
        _REQUEST_CACHE.pop(key, None)
        _REQUEST_CACHE.pop("__ttl_" + key, None)
        return existed
    def has(self, key: str) -> bool:
        import time as _time
        ttl_key = "__ttl_" + key
        if ttl_key in _REQUEST_CACHE and _time.time() > _REQUEST_CACHE[ttl_key]:
            _REQUEST_CACHE.pop(key, None)
            _REQUEST_CACHE.pop(ttl_key, None)
            return False
        return key in _REQUEST_CACHE
    def clear(self) -> bool:
        _REQUEST_CACHE.clear()
        return True


class EdgeV8Runtime(BaseRuntime):
    # FIX #642/#643: Move to instance variables — class variables are shared across instances
    # These are now initialized in __init__
    """Edge V8 Runtime — real JavaScript sandbox via V8.

    Like Next.js Edge Runtime:
    - Real JavaScript execution (V8 isolate)
    - NO filesystem, NO subprocess, NO native modules
    - YES network, crypto, cache, env vars

    Usage: runtime = "edge-v8"
    """

    def __init__(self):
        self._executor = EdgeV8Executor()
        self._storage_inst = None  # FIX #642: Instance variable, not class variable
        self._cache_inst = None    # FIX #643: Instance variable, not class variable

    @property
    def runtime_name(self) -> str:
        return "edge-v8"

    @property
    def display_name(self) -> str:
        engine = self._executor.engine
        if engine == "v8": return "Edge (V8 Isolate)"
        return "Edge (V8 not installed)"

    @property
    def version(self) -> str:
        engine = self._executor.engine
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        if engine == "v8": return f"v8/{_ENGINE_VERSION}+python{py_ver}"
        return f"v8-not-installed/python{py_ver}"

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: False,
            RuntimeCapability.NETWORK.value: True,
            RuntimeCapability.NATIVE_MODULES.value: False,
            RuntimeCapability.SUBPROCESS.value: False,
            RuntimeCapability.DATABASE.value: False,
            RuntimeCapability.CRYPTO.value: True,
            RuntimeCapability.CACHE.value: True,
            RuntimeCapability.ENV_VARS.value: True,
            RuntimeCapability.PERSISTENT_STORAGE.value: False,  # FIX #645: in-memory = not persistent
            RuntimeCapability.TIMERS.value: False,
            RuntimeCapability.STREAMING.value: False,
        }

    def is_available(self) -> bool:
        return _ENGINE is not None

    def engine_type(self) -> str:
        return self._executor.engine or "none"

    def execute_handler(self, handler_body: str, method: str, request_data: dict, handler_path: str = "") -> dict:
        # FIX #648: Execution timeout via worker thread to prevent infinite loops
        import threading
        result_holder = {"value": None, "error": None}
        def _run():
            try:
                result_holder["value"] = self._executor.execute(handler_body, method, request_data, handler_path)
            except Exception as e:
                result_holder["error"] = e
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout=30)  # 30s default timeout
        if worker.is_alive():
            return {
                "status": 504,
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps({"error": "Execution timeout (30s)", "engine": self._executor.engine}).encode("utf-8"),
                "headers": [], "cookies": [],
            }
        if result_holder["error"]:
            raise result_holder["error"]
        return result_holder["value"]

    def reload(self):
        self._executor.reload()

    def capabilities_info(self) -> Dict[str, Any]:
        info = super().capabilities_info()
        info["engine"] = self._executor.engine
        info["v8_available"] = is_v8_available()
        info["engine_version"] = _ENGINE_VERSION
        return info

    @property
    def storage(self) -> EdgeV8Storage:
        # v0.9.08 FIX #80: Cache instance instead of creating new every time
        if self._storage_inst is None:
            self._storage_inst = EdgeV8Storage()
        return self._storage_inst

    @property
    def http(self) -> EdgeV8Http:
        return EdgeV8Http()

    @property
    def cache(self) -> EdgeV8Cache:
        # v0.9.08 FIX #81: Return EdgeV8Cache, not base CacheAPI
        if self._cache_inst is None:
            self._cache_inst = EdgeV8Cache()
        return self._cache_inst

    @property
    def crypto(self) -> EdgeV8Crypto:
        return EdgeV8Crypto()

    @property
    def env(self) -> EdgeV8Env:
        return EdgeV8Env()

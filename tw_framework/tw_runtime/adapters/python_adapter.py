"""
TW Framework — Python Runtime Adapter (v0.9.0)

Native Python runtime: runs .twm handlers in-process (no Node.js needed!).
Supports filesystem, database, crypto, cache, env — everything Python offers.
No subprocess overhead — executes directly in the TW server process.

This is the recommended default for environments without Node.js (Termux,
restricted servers, etc.) and for Python-heavy workloads.
"""

from __future__ import annotations
import os
import sys
import json
import hashlib
import hmac
import secrets
import sqlite3
import urllib.request
import urllib.error
import glob as glob_module
from typing import Any, Dict, List, Optional, Union

from ..base import BaseRuntime, RuntimeCapability
from ..abstractions import StorageAPI, HttpAPI, DatabaseAPI, CryptoAPI, EnvAPI, CacheAPI
import urllib


class PythonStorage(StorageAPI):
    """Python storage adapter — maps tw.storage to Python os/file operations."""

    def read(self, path: str, encoding: str = "utf-8") -> Union[str, bytes]:
        mode = "r" if encoding else "rb"
        with open(path, mode, encoding=encoding if encoding else None) as f:
            return f.read()

    def write(self, path: str, data: Union[str, bytes]) -> bool:
        mode = "w" if isinstance(data, str) else "wb"
        with open(path, mode, encoding="utf-8" if mode == "w" else None) as f:
            f.write(data)
        return True

    def delete(self, path: str) -> bool:
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def list(self, dir_path: str, pattern: str = "*") -> List[str]:
        return glob_module.glob(os.path.join(dir_path, pattern))


class PythonHttp(HttpAPI):
    """Python HTTP adapter — uses urllib (stdlib, no external deps)."""

    def fetch(self, url: str, options: Optional[dict] = None) -> dict:
        opts = options or {}
        method = opts.get("method", "GET").upper()
        headers = opts.get("headers", {})
        body = opts.get("body")
        timeout = opts.get("timeout", 30)

        req_body = None
        if body is not None:
            if isinstance(body, (dict, list)):
                req_body = json.dumps(body).encode("utf-8")
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                req_body = body.encode("utf-8")
            elif isinstance(body, bytes):
                req_body = body

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
                return {
                    "ok": 200 <= resp.status < 300,
                    "status": resp.status,
                    "statusText": resp.reason,
                    "url": url,
                    "headers": resp_headers,
                    "text": text,
                    "data": data,
                }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            text = ""
            try:
                text = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {
                "ok": False,
                "status": e.code,
                "statusText": e.reason,
                "url": url,
                "headers": dict(e.headers),
                "text": text,
                "data": text,
            }


class _TransactionContext:
    """Transaction context passed to transaction() callbacks.
    v0.9.08 FIX: Provides execute/query/commit/rollback instead of raw DB object.
    """
    def __init__(self, conn):
        self._conn = conn
    def execute(self, sql, params=None):
        c = self._conn.execute(sql, params or [])
        return c.fetchall()
    def query(self, sql, params=None):
        c = self._conn.execute(sql, params or [])
        return [dict(r) for r in c.fetchall()]
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()


class PythonDatabase(DatabaseAPI):
    """Python database adapter — uses sqlite3 (stdlib) by default.

    For PostgreSQL/MySQL, the developer can configure a connection string
    via tw.env.get("DATABASE_URL") and use a Python DB driver.
    """

    _conn: Optional[sqlite3.Connection] = None
    _conn_str: str = ""

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            db_path = os.environ.get("TW_DB_PATH", os.path.join(os.getcwd(), ".tw", "data", "app.db"))
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def query(self, sql: str, params: Optional[list] = None) -> List[dict]:
        conn = self._get_conn()
        cursor = conn.execute(sql, params or [])
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute(self, sql: str, params: Optional[list] = None) -> int:
        conn = self._get_conn()
        cursor = conn.execute(sql, params or [])
        conn.commit()
        return cursor.rowcount

    def transaction(self, callback) -> Any:
        conn = self._get_conn()
        try:
            result = callback(self._TransactionContext(self._get_conn()))
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise


class PythonRuntime(BaseRuntime):
    """Python runtime — full Python capabilities, in-process execution.

    No Node.js required! .twm handlers are evaluated directly in Python.
    This is the recommended default for Termux/Android and restricted environments.
    """

    @property
    def runtime_name(self) -> str:
        return "python"

    @property
    def display_name(self) -> str:
        return "Python"

    @property
    def version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def capabilities(self) -> Dict[str, bool]:
        return {
            RuntimeCapability.FILESYSTEM.value: True,
            RuntimeCapability.NETWORK.value: True,
            RuntimeCapability.NATIVE_MODULES.value: True,  # Python packages
            RuntimeCapability.SUBPROCESS.value: True,
            RuntimeCapability.DATABASE.value: True,
            RuntimeCapability.CRYPTO.value: True,
            RuntimeCapability.CACHE.value: True,
            RuntimeCapability.ENV_VARS.value: True,
            RuntimeCapability.PERSISTENT_STORAGE.value: True,
            RuntimeCapability.TIMERS.value: True,
            RuntimeCapability.STREAMING.value: True,
        }

    def is_available(self) -> bool:
        return True  # Python is always available (it's the host process!)

    # ── API Adapters ──────────────────────────────────────────────────

    @property
    def storage(self) -> PythonStorage:
        return PythonStorage()

    @property
    def http(self) -> PythonHttp:
        return PythonHttp()

    @property
    def db(self) -> PythonDatabase:
        return PythonDatabase()

    @property
    def cache(self) -> CacheAPI:
        return CacheAPI()

    @property
    def crypto(self) -> CryptoAPI:
        return CryptoAPI()

    @property
    def env(self) -> EnvAPI:
        return EnvAPI()

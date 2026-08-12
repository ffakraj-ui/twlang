"""
TW Framework — Edge DB Proxy (v0.9.08)

Allows tw.db.query() on Edge runtime via HTTP proxy.
Next.js Edge can't do direct DB — TW can.
Set TW_DB_PROXY_URL environment variable.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
import urllib


class EdgeDBProxy:
    """HTTP-based database proxy for Edge runtime."""

    def __init__(self, proxy_url: str = None, secret: str = None):
        self.proxy_url = proxy_url or os.environ.get("TW_DB_PROXY_URL", "")
        self.secret = secret or os.environ.get("TW_DB_PROXY_SECRET", "")
        self.timeout = 30

    def is_configured(self) -> bool:
        return bool(self.proxy_url)

    def _send(self, payload: dict) -> dict:
        if not self.is_configured():
            raise RuntimeError("Edge DB proxy not configured. Set TW_DB_PROXY_URL.")
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.proxy_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.secret:
            req.add_header("X-DB-Secret", self.secret)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def query(self, sql: str, params: Optional[list] = None) -> List[dict]:
        r = self._send({"sql": sql, "params": params or [], "operation": "query"})
        if r.get("error"):
            raise RuntimeError(r["error"])
        return r.get("rows", [])

    def query_one(self, sql: str, params: Optional[list] = None) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Optional[list] = None) -> int:
        r = self._send({"sql": sql, "params": params or [], "operation": "execute"})
        if r.get("error"):
            raise RuntimeError(r["error"])
        return r.get("affected_rows", 0)

    def transaction(self, queries: List[dict]) -> bool:
        r = self._send({"operation": "transaction", "queries": queries})
        return r.get("success", False)


_edge_db: Optional[EdgeDBProxy] = None

def get_edge_db() -> EdgeDBProxy:
    global _edge_db
    if _edge_db is None:
        _edge_db = EdgeDBProxy()
    return _edge_db


def handle_db_proxy_request(body: dict) -> dict:
    """Handle incoming DB proxy requests (backend side)."""
    import sqlite3
    db_path = os.environ.get("TW_DB_PATH", os.path.join(os.getcwd(), ".tw", "data", "app.db"))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        op = body.get("operation", "query")
        if op == "transaction":
            for q in body.get("queries", []):
                conn.execute(q.get("sql", ""), q.get("params", []))
            conn.commit()
            return {"success": True}
        sql = body.get("sql", "")
        params = body.get("params", [])
        if op == "execute":
            c = conn.execute(sql, params)
            conn.commit()
            return {"affected_rows": c.rowcount}
        c = conn.execute(sql, params)
        return {"rows": [dict(r) for r in c.fetchall()]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

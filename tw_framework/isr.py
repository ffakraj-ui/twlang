"""
TW Framework — On-demand ISR (v0.9.08)

Incremental Static Regeneration with on-demand revalidation.
POST /__tw/revalidate { secret, paths: ["/blog/1"] }
"""

from __future__ import annotations
import os
import time
import threading
from typing import Dict, List, Optional, Set


_revalidation_secret = os.environ.get("TW_REVALIDATE_SECRET", "")
_revalidation_cache: Dict[str, float] = {}
_revalidation_lock = threading.Lock()
_pending_revalidations: Set[str] = set()


def get_revalidation_secret() -> str:
    return _revalidation_secret


def set_revalidation_secret(secret: str) -> None:
    global _revalidation_secret
    _revalidation_secret = secret


def should_revalidate(path: str, revalidate_interval: int) -> bool:
    if revalidate_interval <= 0:
        return False
    with _revalidation_lock:
        last = _revalidation_cache.get(path, 0)
        return (time.time() - last) >= revalidate_interval


def mark_revalidated(path: str) -> None:
    with _revalidation_lock:
        _revalidation_cache[path] = time.time()
        _pending_revalidations.discard(path)


def request_revalidation(paths: List[str], secret: str = None) -> dict:
    if _revalidation_secret and secret != _revalidation_secret:
        return {"success": False, "error": "Invalid revalidation secret"}
    with _revalidation_lock:
        for path in paths:
            _pending_revalidations.add(path)
    return {"success": True, "revalidated": paths}


def get_pending_revalidations() -> Set[str]:
    with _revalidation_lock:
        return set(_pending_revalidations)


def clear_pending(path: str) -> None:
    with _revalidation_lock:
        _pending_revalidations.discard(path)


def get_revalidation_status() -> dict:
    with _revalidation_lock:
        return {"secret_configured": bool(_revalidation_secret),
                "cached_pages": len(_revalidation_cache),
                "pending": list(_pending_revalidations)}


# v0.9.08 FIX: Actual page rebuild logic
_rebuild_callback = None


def set_rebuild_callback(callback):
    """Register a callback that rebuilds a single page."""
    global _rebuild_callback
    _rebuild_callback = callback


def process_pending_revalidations(project_root=".", output_dir="dist"):
    """Process all pending revalidations - actually rebuild pages.

    v0.9.08 FIX: This was missing. Now rebuilds pages via callback or full build.
    """
    pending = get_pending_revalidations()
    if not pending:
        return {"rebuilt": 0, "paths": []}

    rebuilt = []
    failed = []

    for path in list(pending):
        try:
            if _rebuild_callback:
                _rebuild_callback(path, project_root, output_dir)
                mark_revalidated(path)
                rebuilt.append(path)
            else:
                # Fallback: trigger full build
                try:
                    from .framework import build_hidden_site
                    build_hidden_site(project_root, output_dir, force=True)
                    mark_revalidated(path)
                    rebuilt.append(path)
                except Exception as err:
                    failed.append({"path": path, "error": str(err)})
        except Exception as err:
            failed.append({"path": path, "error": str(err)})

    return {"rebuilt": len(rebuilt), "paths": rebuilt, "failed": failed}

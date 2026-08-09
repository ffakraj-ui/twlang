"""
Incremental compiler cache for TW Framework.

Caches parsed AST, compiled output, dependency graph, CSS, and assets.
Only rebuilds changed nodes.
"""

import hashlib
import json
import logging
import os
import shutil
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IncrementalCache:
    """Persistent cache for compiler artifacts."""

    def __init__(self, project_root: str) -> None:
        self.cache_dir = os.path.join(project_root, ".tw", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _key_path(self, key: str) -> Any:
        # ``page_cache_key()`` returns a full absolute file path (e.g.
        # ``/abs/project/[home]/pages/index.tw``).  ``os.path.join()`` would
        # discard ``self.cache_dir`` because the key starts with ``/``, so
        # the cache file would be written next to the source file instead
        # of inside ``.tw/cache/``.
        #
        # We hash the key to produce a flat, safe filename that always lives
        # inside ``cache_dir``.  An SHA‑256 hex digest is used so collisions
        # are effectively impossible.
        safe_name = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, f"{safe_name}.json")

    def get(self, key: str) -> Optional[Any]:
        path = self._key_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._key_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2)

    def invalidate(self, key: str) -> None:
        path = self._key_path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear(self) -> None:
        """Remove all cached entries.

        Because ``_key_path()`` now hashes keys, all cache files are flat
        ``.json`` files directly inside ``cache_dir``.  A simple walk is
        still used for safety in case any legacy nested files exist from
        older versions.
        """
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)


__all__ = ["IncrementalCache"]

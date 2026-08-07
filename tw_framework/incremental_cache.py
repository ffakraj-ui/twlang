"""
Incremental compiler cache for TW Framework.

Caches parsed AST, compiled output, dependency graph, CSS, and assets.
Only rebuilds changed nodes.
"""

import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IncrementalCache:
    """Persistent cache for compiler artifacts."""

    def __init__(self, project_root: str) -> None:
        self.cache_dir = os.path.join(project_root, ".tw", "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _key_path(self, key: str) -> Any:
        return os.path.join(self.cache_dir, f"{key}.json")

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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2)

    def invalidate(self, key: str) -> None:
        path = self._key_path(key)
        if os.path.exists(path):
            os.remove(path)

    def clear(self) -> None:
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                os.remove(os.path.join(self.cache_dir, fname))


__all__ = ["IncrementalCache"]

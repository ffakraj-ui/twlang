"""
Compiler statistics for TW Framework.

Tracks pages compiled, components compiled, files reused from cache,
files rebuilt, build duration, and cache hit rate.
"""

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CompilerStats:
    """Collects compiler statistics during a build."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.pages_compiled = 0
        self.components_compiled = 0
        self.files_reused_from_cache = 0
        self.files_rebuilt = 0
        self.cache_hits = 0
        self.cache_misses = 0

    @property
    def cache_hit_rate(self) -> Any:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total

    @property
    def build_duration(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "build_duration_seconds": round(self.build_duration, 2),
            "pages_compiled": self.pages_compiled,
            "components_compiled": self.components_compiled,
            "files_reused_from_cache": self.files_reused_from_cache,
            "files_rebuilt": self.files_rebuilt,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": round(self.cache_hit_rate, 2),
        }


__all__ = ["CompilerStats"]

"""
Runtime performance analyzer for TW Framework.

Measures render time, SSR time, middleware time, and API execution time.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """Collects runtime performance metrics."""

    def __init__(self) -> None:
        self.metrics: Dict[str, float] = {}

    def measure(self, name: str, func: Callable[..., Any], *args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.perf_counter() - start
            self.metrics[name] = elapsed
            logger.debug("Performance: %s took %.4f seconds", name, elapsed)

    def get_report(self) -> Dict[str, float]:
        return dict(self.metrics)

    def reset(self) -> None:
        self.metrics.clear()


__all__ = ["PerformanceAnalyzer"]

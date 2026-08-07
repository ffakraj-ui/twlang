"""
Build report generation for TW Framework.

Generates .tw/build-report.json with bundle sizes, timings, and analysis.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BuildReport:
    """Collects build metrics and generates a report."""

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root
        self.start_time = time.time()
        self.pages: List[Dict[str, Any]] = []
        self.components: List[Dict[str, Any]] = []
        self.total_bundle_size = 0
        self.total_css_size = 0
        self.total_js_size = 0
        self.total_image_size = 0
        self.unused_code: List[str] = []
        self.largest_components: List[Dict[str, Any]] = []
        self.slowest_pages: List[Dict[str, Any]] = []
        self.build_timings: Dict[str, float] = {}

    def add_page(self, path: str, size: int, duration: float) -> None:
        self.pages.append({"path": path, "size": size, "duration": duration})
        self.total_bundle_size += size

    def add_component(self, name: str, size: int) -> None:
        self.components.append({"name": name, "size": size})
        self.total_bundle_size += size

    def add_css_size(self, size: int) -> None:
        self.total_css_size += size

    def add_js_size(self, size: int) -> None:
        self.total_js_size += size

    def add_image_size(self, size: int) -> None:
        self.total_image_size += size

    def add_unused_code(self, item: str) -> None:
        self.unused_code.append(item)

    def finalize(self) -> Dict[str, Any]:
        duration = time.time() - self.start_time
        self.pages.sort(key=lambda p: p["duration"], reverse=True)
        self.slowest_pages = self.pages[:10]
        self.components.sort(key=lambda c: c["size"], reverse=True)
        self.largest_components = self.components[:10]
        return {
            "build_duration_seconds": round(duration, 2),
            "total_bundle_size_bytes": self.total_bundle_size,
            "total_css_size_bytes": self.total_css_size,
            "total_js_size_bytes": self.total_js_size,
            "total_image_size_bytes": self.total_image_size,
            "pages_compiled": len(self.pages),
            "components_compiled": len(self.components),
            "unused_code": self.unused_code,
            "largest_components": self.largest_components,
            "slowest_pages": self.slowest_pages,
            "build_timings": self.build_timings,
        }

    def save(self) -> Any:
        report = self.finalize()
        report_dir = os.path.join(self.project_root, ".tw")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "build-report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Build report saved to %s", report_path)
        return report


__all__ = ["BuildReport"]

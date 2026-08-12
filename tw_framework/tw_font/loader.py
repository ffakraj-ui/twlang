"""
Font optimization for tw/font.

Provides font preloading, font-display: swap, and self-hosting support.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FontConfig:
    """Font configuration."""
    family: str
    weight: int = 400
    style: str = "normal"
    display: str = "swap"  # swap, optional, fallback, block
    preload: bool = True
    subset: List[str] = field(default_factory=list)
    src: str = ""  # URL or local path


class FontLoader:
    """Optimizes font loading for TW pages."""

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir
        self._fonts: List[FontConfig] = []

    def add_font(self, config: FontConfig) -> None:
        self._fonts.append(config)

    def generate_preload_tags(self) -> str:
        """Generate <link rel="preload"> tags for fonts."""
        tags = []
        for font in self._fonts:
            if not font.preload or not font.src:
                continue
            tags.append(
                f'<link rel="preload" href="{font.src}" as="font" '
                f'type="font/woff2" crossorigin>'
            )
        return "\n".join(tags)

    def generate_font_face_css(self) -> str:
        """Generate @font-face CSS rules."""
        rules = []
        for font in self._fonts:
            src_parts = []
            if font.src:
                src_parts.append(f"url('{font.src}') format('woff2')")

            rule = f"""@font-face {{
  font-family: '{font.family}';
  font-weight: {font.weight};
  font-style: {font.style};
  font-display: {font.display};
  src: {', '.join(src_parts)};
}}"""
            rules.append(rule)
        return "\n\n".join(rules)

    def get_fonts(self) -> List[FontConfig]:
        return list(self._fonts)


__all__ = ["FontLoader", "FontConfig"]

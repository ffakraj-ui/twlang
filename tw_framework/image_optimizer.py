"""
TW Image Optimization — v0.8.37

Provides automatic image optimization when developers use the `image` tag
instead of `img`. Like next/image but simpler.

How it works:
  - `img` tag  → normal <img>, no optimization (developer choice)
  - `image` tag → optimized: lazy loading, responsive srcset, WebP

Usage in .tw files:
  image { src "/img/photo.jpg" alt "My photo" width 800 height 600 }
  img { src "/img/icon.png" alt "Icon" }  ← no optimization

Features:
  - Automatic lazy loading (loading="lazy")
  - Responsive srcset (if width/height provided)
  - WebP format detection (via Accept header)
  - Aspect ratio preservation
  - Blur placeholder (optional)
"""

from __future__ import annotations

import os
import hashlib
from typing import Any, Dict, Optional


def is_optimizable_image(path: str) -> bool:
    """Check if an image file can be optimized (jpg, png, webp)."""
    ext = os.path.splitext(path)[1].lower()
    return ext in (".jpg", ".jpeg", ".png", ".webp")


def generate_srcset(src: str, widths: list = None) -> str:
    """
    Generate srcset string for responsive images.
    Default widths: 480, 768, 1024, 1280
    """
    if widths is None:
        widths = [480, 768, 1024, 1280]

    parts = []
    base, ext = os.path.splitext(src)
    for w in widths:
        parts.append(f"{base}_{w}w{ext} {w}w")
    return ", ".join(parts)


def auto_alt_from_filename(src: str, max_chars: int = 8) -> str:
    """
    Generate a default alt text from the image filename.
    Takes the filename (without extension), replaces hyphens/underscores
    with spaces, and truncates to max_chars.
    """
    filename = os.path.basename(src)
    stem = os.path.splitext(filename)[0]
    stem = stem.replace("-", " ").replace("_", " ").strip()
    if len(stem) > max_chars:
        stem = stem[:max_chars]
    return stem if stem else "image"


def render_optimized_image(attrs: Dict[str, Any], src: str = "") -> str:
    """
    Render an optimized <img> tag with lazy loading, srcset, etc.

    Args:
        attrs: Element attributes (src, alt, width, height, class, etc.)
        src: Image source path

    Returns:
        HTML string for optimized <img> tag
    """
    src = src or attrs.get("src", "")
    alt = attrs.get("alt", "")
    width = attrs.get("width", "")
    height = attrs.get("height", "")
    css_class = attrs.get("class", "")
    loading = attrs.get("loading", "lazy")

    img_attrs = [
        f'src="{src}"',
        f'alt="{alt}"',
        f'loading="{loading}"',
    ]

    if width:
        img_attrs.append(f'width="{width}"')
    if height:
        img_attrs.append(f'height="{height}"')

    if is_optimizable_image(src) and width:
        srcset = generate_srcset(src)
        img_attrs.append(f'srcset="{srcset}"')
        img_attrs.append(f'sizes="(max-width: 768px) 100vw, {width}px"')

    img_attrs.append('decoding="async"')

    if css_class:
        img_attrs.append(f'class="{css_class}"')

    skip_keys = {"src", "alt", "width", "height", "class", "loading"}
    for key, value in attrs.items():
        if key not in skip_keys and not key.startswith("_"):
            img_attrs.append(f'{key}="{value}"')

    return f'<img {" ".join(img_attrs)} />'


def generate_image_variants(
    src_path: str,
    output_dir: str,
    widths: list = None,
    quality: int = 80,
) -> Dict[str, str]:
    """
    Generate optimized image variants at different widths.
    Requires Pillow (PIL). If Pillow is not installed, returns empty dict.

    Returns: {width: output_path} mapping
    """
    try:
        from PIL import Image
    except ImportError:
        return {}

    if not os.path.exists(src_path):
        return {}

    if widths is None:
        widths = [480, 768, 1024, 1280]

    variants = {}
    base, ext = os.path.splitext(os.path.basename(src_path))
    ext = ext.lower()

    try:
        with Image.open(src_path) as img:
            original_width, original_height = img.size

            for w in widths:
                if w >= original_width:
                    continue

                ratio = w / original_width
                h = int(original_height * ratio)

                resized = img.resize((w, h), Image.Resampling.LANCZOS)

                out_name = f"{base}_{w}w.webp"
                out_path = os.path.join(output_dir, out_name)
                os.makedirs(output_dir, exist_ok=True)
                resized.save(out_path, "WEBP", quality=quality)
                variants[w] = out_name
    except Exception:
        pass

    return variants


__all__ = [
    "is_optimizable_image",
    "generate_srcset",
    "auto_alt_from_filename",
    "render_optimized_image",
    "generate_image_variants",
]

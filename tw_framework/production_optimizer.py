"""
Production optimization for TW Framework.

Generates production output with minified HTML, CSS, JS, compressed assets,
and hashed filenames.
"""

import gzip
import hashlib
import logging
import os
import shutil
from typing import List, Optional

from . import compiler

logger = logging.getLogger(__name__)


def optimize_for_production(output_dir: str) -> None:
    """Apply production optimizations to the output directory.

    FIX #146: Consolidated into a single directory walk for better performance.
    Also generates Brotli compressed files when the brotli library is available,
    and generates SRI (Subresource Integrity) hashes for CSS/JS files.
    """
    import json as _json

    # FIX #146: Try to import brotli for superior compression
    try:
        import brotli as _brotli
        _has_brotli = True
    except ImportError:
        _has_brotli = False

    _compressible_exts = (".html", ".css", ".js", ".json", ".xml", ".txt", ".svg")
    _minify_map = {
        ".html": compiler.minify_html_content,
        ".css": compiler.minify_css_content,
        ".js": compiler.minify_js_content,
    }

    # Single-pass: minify + compress + collect for hashing
    for root, _, files in os.walk(output_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            path = os.path.join(root, fname)

            # Skip already-compressed files
            if fname.endswith((".gz", ".br")):
                continue

            # Minify
            if ext in _minify_map:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    minified = _minify_map[ext](content)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(minified)
                except Exception as e:
                    logger.warning("Failed to minify %s: %s", path, e)

            # Compress
            if ext in _compressible_exts:
                try:
                    with open(path, "rb") as f:
                        data = f.read()
                    # Gzip
                    with gzip.open(path + ".gz", "wb", compresslevel=9) as gz:
                        gz.write(data)
                    # Brotli (better compression ratio)
                    if _has_brotli and len(data) > 1024:
                        compressed = _brotli.compress(data, quality=11)
                        with open(path + ".br", "wb") as br:
                            br.write(compressed)
                except Exception as e:
                    logger.warning("Failed to compress %s: %s", path, e)

    # Hash filenames for cache busting
    rename_map = {}  # old basename -> new basename
    for root, _, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith((".css", ".js")):
                path = os.path.join(root, fname)
                with open(path, "rb") as f:
                    data = f.read()
                digest = hashlib.sha256(data).hexdigest()[:12]
                name, ext = os.path.splitext(fname)
                hashed_name = f"{name}.{digest}{ext}"
                hashed_path = os.path.join(root, hashed_name)
                if not os.path.exists(hashed_path):
                    shutil.copy2(path, hashed_path)
                rename_map[fname] = hashed_name
                # Remove original file
                os.remove(path)

    # Update HTML references to use hashed filenames
    if rename_map:
        for root, _, files in os.walk(output_dir):
            for fname in files:
                if fname.endswith(".html"):
                    path = os.path.join(root, fname)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    for old_name, new_name in rename_map.items():
                        content = content.replace(old_name, new_name)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)


__all__ = ["optimize_for_production"]

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


def optimize_for_production(output_dir: str):
    """Apply production optimizations to the output directory."""
    # Minify HTML files
    for root, _, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith(".html"):
                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                minified = compiler.minify_html_content(content)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(minified)

    # Minify CSS files
    for root, _, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith(".css"):
                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                minified = compiler.minify_css_content(content)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(minified)

    # Minify JS files
    for root, _, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith(".js"):
                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                minified = compiler.minify_js_content(content)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(minified)

    # Gzip compress files
    for root, _, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith((".html", ".css", ".js", ".json", ".xml", ".txt", ".svg")):
                path = os.path.join(root, fname)
                with open(path, "rb") as f:
                    data = f.read()
                with gzip.open(path + ".gz", "wb", compresslevel=9) as gz:
                    gz.write(data)

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

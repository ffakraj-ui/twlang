"""
esbuild detection and integration utilities for TW Framework.

esbuild is an extremely fast JavaScript bundler that handles:
  - CJS → ESM conversion
  - Tree shaking (dead code elimination)
  - Transitive dependency resolution
  - Minification
  - JSX/TSX transforms
  - Code splitting

This module detects if esbuild is available (via npx or local install)
and provides a clean API for the client bundler to use it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple


_ESBUILD_PATH_CACHE: Optional[str] = None
_ESBUILD_VERSION_CACHE: Optional[str] = None


def find_esbuild() -> Optional[str]:
    """
    Find the esbuild binary.

    Checks in order:
    1. Local node_modules/.bin/esbuild
    2. Global npm install
    3. npx (will download on first use)

    Returns the command to run esbuild, or None if not available.
    """
    global _ESBUILD_PATH_CACHE
    if _ESBUILD_PATH_CACHE is not None:
        return _ESBUILD_PATH_CACHE

    # 1. Check local node_modules/.bin/esbuild
    # We need a project root to check this — but we can check common locations
    candidates = [
        "node_modules/.bin/esbuild",
        "/usr/local/bin/esbuild",
        "/usr/bin/esbuild",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    _ESBUILD_PATH_CACHE = candidate
                    return candidate
            except (subprocess.TimeoutExpired, OSError):
                continue

    # 2. Check if esbuild is on PATH
    path_esbuild = shutil.which("esbuild")
    if path_esbuild:
        try:
            result = subprocess.run(
                [path_esbuild, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                _ESBUILD_PATH_CACHE = path_esbuild
                return path_esbuild
        except (subprocess.TimeoutExpired, OSError):
            pass

    # 3. Check npx — esbuild can be run via npx (will download on first use)
    npx = shutil.which("npx")
    if npx:
        try:
            result = subprocess.run(
                [npx, "esbuild", "--version"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                _ESBUILD_PATH_CACHE = "npx esbuild"
                return "npx esbuild"
        except (subprocess.TimeoutExpired, OSError):
            pass

    _ESBUILD_PATH_CACHE = None
    return None


def get_esbuild_version() -> Optional[str]:
    """Get the installed esbuild version."""
    global _ESBUILD_VERSION_CACHE
    if _ESBUILD_VERSION_CACHE is not None:
        return _ESBUILD_VERSION_CACHE

    cmd = find_esbuild()
    if not cmd:
        return None

    try:
        parts = cmd.split()
        result = subprocess.run(
            parts + ["--version"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            _ESBUILD_VERSION_CACHE = result.stdout.strip()
            return _ESBUILD_VERSION_CACHE
    except (subprocess.TimeoutExpired, OSError):
        pass

    return None


def is_esbuild_available() -> bool:
    """Check if esbuild is available."""
    return find_esbuild() is not None


def ensure_esbuild_installed(project_root: str) -> bool:
    """
    Ensure esbuild is installed in the project.
    If not, install it as a dev dependency.
    """
    # Check if already available
    if is_esbuild_available():
        return True

    # Try installing via npm
    npm = shutil.which("npm")
    if not npm:
        return False

    try:
        result = subprocess.run(
            [npm, "install", "--save-dev", "esbuild"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=120,
        )
        if result.returncode == 0:
            # Reset cache so find_esbuild picks up the new install
            global _ESBUILD_PATH_CACHE, _ESBUILD_VERSION_CACHE
            _ESBUILD_PATH_CACHE = None
            _ESBUILD_VERSION_CACHE = None
            return is_esbuild_available()
    except (subprocess.TimeoutExpired, OSError):
        pass

    return False


def bundle_with_esbuild(
    entry_point: str,
    output_path: str,
    project_root: str,
    *,
    minify: bool = True,
    target: str = "es2020",
    format: str = "iife",
    global_name: Optional[str] = None,
    externals: Optional[List[str]] = None,
    define: Optional[Dict[str, str]] = None,
    sourcemap: bool = False,
    splitting: bool = False,
    timeout: int = 120,
) -> Tuple[bool, str]:
    """
    Bundle a JavaScript/TypeScript entry point with esbuild.

    Args:
        entry_point: Path to the entry JS/TS file
        output_path: Where to write the bundled output
        project_root: Project root (for node_modules resolution)
        minify: Whether to minify the output
        target: JavaScript target (es2015, es2020, esnext)
        format: Output format (iife, esm, cjs)
        global_name: Global variable name for IIFE format
        externals: Packages to exclude from the bundle
        define: Compile-time constants (e.g. {"process.env.NODE_ENV": '"production"'})
        sourcemap: Generate source maps
        splitting: Enable code splitting (ESM only)
        timeout: Max seconds for the build

    Returns (success, error_message_or_output_info)
    """
    cmd_str = find_esbuild()
    if not cmd_str:
        return False, "esbuild not found. Install with: tw install --save-dev esbuild"

    parts = cmd_str.split()
    args = list(parts)

    # Entry point
    args.append(entry_point)

    # Output — esbuild uses --outfile=path (with = sign)
    args.append(f"--outfile={output_path}")

    # Bundle (resolve dependencies)
    args.append("--bundle")

    # Format
    args.append(f"--format={format}")

    # Target
    args.append(f"--target={target}")

    # Minify
    if minify:
        args.append("--minify")

    # Global name for IIFE
    if global_name and format == "iife":
        args.append(f"--global-name={global_name}")

    # Externals
    if externals:
        for ext in externals:
            args.append(f"--external:{ext}")

    # Define constants
    if define:
        for key, value in define.items():
            args.append(f"--define:{key}={value}")

    # Sourcemap
    if sourcemap:
        args.append("--sourcemap")

    # Splitting
    if splitting:
        args.append("--splitting")
        args.append("--format=esm")  # Splitting requires ESM

    # Platform — browser for client bundles
    args.append("--platform=browser")

    # Main fields — prefer browser > module > main
    args.append("--main-fields=browser,module,main")

    # Conditions
    args.append("--conditions=browser,import,module")

    # Resolve extensions
    args.append("--resolve-extensions=.js,.jsx,.ts,.tsx,.mjs,.cjs,.json")

    # Banner: add a comment
    args.append("--banner:js=// TW Client Bundle (esbuild) — v0.8.1")

    # Log level
    args.append("--log-level=warning")

    # Run esbuild
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=timeout,
        )
        if result.returncode == 0:
            # Get output file size
            if os.path.exists(output_path):
                size = os.path.getsize(output_path)
                return True, f"OK ({size} bytes)"
            return True, "OK"
        else:
            error = result.stderr.strip() or result.stdout.strip()
            return False, error
    except subprocess.TimeoutExpired:
        return False, f"esbuild timed out after {timeout}s"
    except OSError as e:
        return False, f"Failed to run esbuild: {e}"


def bundle_package_with_esbuild(
    project_root: str,
    pkg_name: str,
    output_dir: str,
    *,
    minify: bool = True,
    sourcemap: bool = False,
) -> Tuple[Optional[str], str]:
    """
    Bundle a single npm package with esbuild.

    This creates a self-contained browser-compatible bundle of the package
    and all its transitive dependencies.

    Args:
        project_root: Project root with node_modules
        pkg_name: Package name to bundle
        output_dir: Where to write the output chunk
        minify: Whether to minify
        sourcemap: Generate source maps

    Returns (chunk_url, message) — chunk_url is None on failure.
    """
    import hashlib

    # Resolve the package entry point
    pkg_json_path = os.path.join(project_root, "node_modules", pkg_name, "package.json")
    if not os.path.exists(pkg_json_path):
        return None, f"Package '{pkg_name}' not found in node_modules"

    try:
        with open(pkg_json_path, "r", encoding="utf-8") as f:
            pkg_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None, f"Failed to read package.json for '{pkg_name}'"

    # Determine entry point
    entry = (
        pkg_data.get("browser")
        or pkg_data.get("module")
        or pkg_data.get("main")
        or "index.js"
    )
    if isinstance(entry, dict):
        entry = entry.get(".", pkg_data.get("main", "index.js"))

    entry_path = os.path.join(project_root, "node_modules", pkg_name, entry)
    if not os.path.exists(entry_path):
        entry_path = os.path.join(project_root, "node_modules", pkg_name, "index.js")
        if not os.path.exists(entry_path):
            return None, f"Entry point not found for '{pkg_name}'"

    # Output file with content hash for cache-busting
    safe_name = pkg_name.replace("/", "_").replace("@", "").replace(".", "-")
    # We'll hash after bundling, but need a temp name first
    temp_output = os.path.join(output_dir, "_tw", "chunks", "npm", f"{safe_name}.tmp.js")
    os.makedirs(os.path.dirname(temp_output), exist_ok=True)

    # Define common browser replacements
    define = {
        "process.env.NODE_ENV": '"production"',
    }

    success, message = bundle_with_esbuild(
        entry_point=entry_path,
        output_path=temp_output,
        project_root=project_root,
        minify=minify,
        format="iife",
        global_name=safe_name.replace("-", "_"),
        define=define,
        sourcemap=sourcemap,
    )

    if not success:
        return None, message

    # Read the bundled output to compute hash
    try:
        with open(temp_output, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None, "Failed to read bundled output"

    # Compute content hash
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    final_name = f"{safe_name}.{digest}.js"
    final_path = os.path.join(os.path.dirname(temp_output), final_name)

    # Rename temp file to final
    try:
        os.rename(temp_output, final_path)
    except OSError:
        # If rename fails (cross-device?), copy
        import shutil
        shutil.copy2(temp_output, final_path)
        os.unlink(temp_output)

    chunk_url = f"/_tw/chunks/npm/{final_name}"
    return chunk_url, f"OK ({len(content)} bytes)"


__all__ = [
    "find_esbuild",
    "get_esbuild_version",
    "is_esbuild_available",
    "ensure_esbuild_installed",
    "bundle_with_esbuild",
    "bundle_package_with_esbuild",
]

"""
Vercel adapter for TWLang framework.
Generates .vercel/output compliant with Build Output API v3.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any

def detect() -> dict:
    """Return framework metadata for Vercel detection."""
    return {
        "framework": "tw",
        "version": "1.0",
        "buildCommand": "tw build",
        "outputDirectory": "dist",
        "installCommand": "pip install tw-framework",
        "devCommand": "tw dev",
    }


def generate_vercel_output(
    dist_dir: str,
    config: Dict[str, Any],
    project_root: str,
) -> None:
    """
    Generate .vercel/output from the build output directory.

    Args:
        dist_dir: Path to the build output directory (e.g., 'dist').
        config: Parsed tw.config as a dictionary.
        project_root: Root directory of the project.
    """
    output_dir = Path(project_root) / ".vercel" / "output"
    # Clean previous output
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    static_dir = output_dir / "static"
    static_dir.mkdir(exist_ok=True)

    # Copy all files from dist to static (except functions/api)
    dist_path = Path(dist_dir)
    if not dist_path.exists():
        raise FileNotFoundError(f"Build output directory '{dist_dir}' not found")

    functions_src = dist_path / "functions"
    functions_dst = output_dir / "functions"

    for item in dist_path.rglob("*"):
        if item.is_file():
            rel = item.relative_to(dist_path)
            # Skip functions directory (handled separately)
            if rel.parts and rel.parts[0] == "functions":
                continue
            dest = static_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)

    # Handle functions if present
    if functions_src.exists():
        if functions_dst.exists():
            shutil.rmtree(functions_dst)
        shutil.copytree(functions_src, functions_dst)

    # Build config.json
    vercel_config = build_vercel_config(config, dist_path)
    config_path = output_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(vercel_config, f, indent=2)

    # Auto‑generate vercel.json for zero‑config detection
    vercel_json_path = Path(project_root) / "vercel.json"
    if not vercel_json_path.exists():
        vercel_config = {
            "framework": "tw",
            "buildCommand": "tw build",
            "outputDirectory": "dist",
            "installCommand": "pip install tw-framework",
        }
        with open(vercel_json_path, "w") as f:
            json.dump(vercel_config, f, indent=2)
        print(f"  ✅ Auto‑generated vercel.json at {vercel_json_path}")

    print(f"Generated .vercel/output at {output_dir}")


def build_vercel_config(tw_config: Dict[str, Any], dist_path: Path) -> Dict[str, Any]:
    """
    Build the Vercel config.json (version 3) from tw.config and build output.
    """
    routes = []
    headers_list = []
    rewrites_list = []
    redirects_list = []

    # Extract headers from tw.config
    headers_cfg = tw_config.get("headers", {}).get("rule", [])
    for rule in headers_cfg:
        source = rule.get("source", "/**")
        headers = {}
        sets = rule.get("set", {})
        for h_name, h_value in sets.items():
            headers[h_name] = h_value
        if headers:
            headers_list.append({
                "source": source,
                "headers": [{"key": k, "value": v} for k, v in headers.items()]
            })

    # Extract redirects
    redirects_cfg = tw_config.get("redirects", {}).get("rule", [])
    for rule in redirects_cfg:
        source = rule.get("source", "")
        destination = rule.get("destination", "")
        permanent = rule.get("permanent", False)
        redirects_list.append({
            "source": source,
            "destination": destination,
            "permanent": permanent,
        })

    # Extract rewrites
    rewrites_cfg = tw_config.get("rewrites", {}).get("rule", [])
    for rule in rewrites_cfg:
        source = rule.get("source", "")
        destination = rule.get("destination", "")
        rewrites_list.append({
            "source": source,
            "destination": destination,
        })

    # Build routes array
    # 1. Handle redirects first
    for r in redirects_list:
        routes.append({
            "src": r["source"],
            "status": 308 if r.get("permanent") else 307,
            "headers": {"Location": r["destination"]},
        })

    # 2. Handle rewrites
    for r in rewrites_list:
        routes.append({
            "src": r["source"],
            "dest": r["destination"],
        })

    # 3. Apply headers
    for h in headers_list:
        routes.append({
            "src": h["source"],
            "headers": h["headers"],
            "continue": True,
        })

    # 4. Static files and functions
    has_functions = (dist_path / "functions").exists()
    if has_functions:
        routes.append({
            "src": "/api/(.*)",
            "dest": "/api/$1",
        })

    # 5. Static files catch-all
    routes.append({
        "src": "/(.*)",
        "dest": "/$1",
    })

    config = {
        "version": 3,
        "routes": routes,
    }

    # Add images config if present
    images_cfg = tw_config.get("images", {})
    if images_cfg:
        config["images"] = {
            "sizes": images_cfg.get("sizes", [640, 750, 828, 1080, 1200, 1920, 2048, 3840]),
            "domains": [],
            "remotePatterns": images_cfg.get("remote_patterns", []),
            "minimumCacheTTL": 60,
            "formats": ["image/avif", "image/webp"],
            "dangerouslyAllowSVG": False,
            "contentSecurityPolicy": "script-src 'none'; frame-src 'none'; sandbox;",
        }

    return config

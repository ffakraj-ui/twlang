"""
Cloudflare adapter for TWLang framework.
Generates _routes.json and _worker.js for Cloudflare Pages.
"""

import json
from pathlib import Path
from typing import Dict, Any

def generate_cloudflare_output(
    dist_dir: str,
    config: Dict[str, Any],
    project_root: str,
) -> None:
    """
    Generate Cloudflare deployment files from build output.

    Args:
        dist_dir: Path to the build output directory (e.g., 'dist').
        config: JSON to tw.config as a dictionary.
        project_root: Root directory of the project.
    """
    root = Path(project_root)
    routes_path = root / "_routes.json"
    worker_path = root / "_worker.js"

    # Build _routes.json
    routes = []
    # Add redirects
    redirects = config.get("redirects", {}).get("rule", [])
    for rule in redirects:
        source = rule.get("source", "")
        destination = rule.get("destination", "")
        status = 301 if rule.get("permanent") else 302
        routes.append({
            "src": source,
            "dest": destination,
            "status": status,
        })

    # Add rewrites
    rewrites = config.get("rewrites", {}).get("rule", [])
    for rule in rewrites:
        source = rule.get("source", "")
        destination = rule.get("destination", "")
        routes.append({
            "src": source,
            "dest": destination,
        })

    # Add headers
    headers = config.get("headers", {}).get("rule", [])
    for rule in headers:
        source = rule.get("source", "/**")
        sets = rule.get("set", {})
        headers_dict = {}
        for h_name, h_value in sets.items():
            headers_dict[h_name] = h_value
        routes.append({
            "src": source,
            "headers": headers_dict,
            "continue": True,
        })

    # Static assets catch-all
    routes.append({
        "src": "/(.*)",
        "dest": "/$1",
    })

    with open(routes_path, "w") as f:
        json.dump({"version": 1, "routes": routes}, f, indent=2)

    # Generate _worker.js for API routes
    dist_path = Path(dist_dir)
    functions_src = dist_path / "functions"
    if functions_src.exists():
        worker_code = """
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // Handle API routes
    if (url.pathname.startsWith('/api/')) {
      return new Response(JSON.stringify({ message: "API route" }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    // Otherwise serve static assets from KV or R2
    return env.ASSETS.fetch(request);
  }
}
"""
        with open(worker_path, "w") as f:
            f.write(worker_code)

    print(f"Generated Cloudflare deployment files at {root}")

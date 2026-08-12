"""
Netlify adapter for TWLang framework.
Generates netlify.toml and functions directory.
"""

import shutil
from pathlib import Path
from typing import Dict, Any

def detect() -> dict:
    """Return framework metadata for Netlify detection."""
    return {
        "framework": "tw",
        "version": "1.0",
        "buildCommand": "tw build",
        "publish": "dist",
        "installCommand": "pip install tw-framework",
    }


def generate_netlify_output(
    dist_dir: str,
    config: Dict[str, Any],
    project_root: str,
) -> None:
    """
    Generate Netlify deployment files from build output.

    Args:
        dist_dir: Path to the build output directory (e.g., 'dist').
        config: Parsed tw.config as a dictionary.
        project_root: Root directory of the project.
    """
    root = Path(project_root)
    netlify_toml_path = root / "netlify.toml"
    functions_dir = root / "netlify" / "functions"
    publish_dir = "dist"

    # Build netlify.toml
    toml_lines = ['[build]', 'command = "tw build --prod"', f'publish = "{publish_dir}"', '']

    # Add redirects from tw.config
    redirects = config.get("redirects", {}).get("rule", [])
    if redirects:
        toml_lines.append('[[redirects]]')
        for rule in redirects:
            source = rule.get("source", "")
            destination = rule.get("destination", "")
            status = 301 if rule.get("permanent") else 302
            toml_lines.append(f'  from = "{source}"')
            toml_lines.append(f'  to = "{destination}"')
            toml_lines.append(f'  status = {status}')
            toml_lines.append('')

    # Add headers from tw.config
    headers = config.get("headers", {}).get("rule", [])
    if headers:
        toml_lines.append('[[headers]]')
        for rule in headers:
            source = rule.get("source", "/**")
            sets = rule.get("set", {})
            for h_name, h_value in sets.items():
                toml_lines.append(f'  for = "{source}"')
                toml_lines.append('  [headers.values]')
                toml_lines.append(f'    {h_name} = "{h_value}"')
                toml_lines.append('')

    with open(netlify_toml_path, "w") as f:
        f.write("\n".join(toml_lines))

    # Copy API functions if present
    dist_path = Path(dist_dir)
    functions_src = dist_path / "functions"
    if functions_src.exists():
        if functions_dir.exists():
            shutil.rmtree(functions_dir)
        shutil.copytree(functions_src, functions_dir)

    # Auto‑generate netlify.toml for zero‑config detection
    netlify_toml_path = root / "netlify.toml"
    if not netlify_toml_path.exists():
        toml_content = (
            "[build]\n"
            'command = "tw build --prod"\n'
            'publish = "dist"\n'
        )
        with open(netlify_toml_path, "w") as f:
            f.write(toml_content)
        print(f"  ✅ Auto‑generated netlify.toml at {netlify_toml_path}")

    print(f"Generated Netlify deployment files at {root}")

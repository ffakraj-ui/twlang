"""
TW Framework — Zero-Config Deployment (v0.9.08)

Auto-detects deployment target and generates config.
Supported: Vercel, Netlify, Cloudflare Pages, GitHub Pages, Docker, Static.

Usage:
  tw deploy              # Auto-detect
  tw deploy vercel       # Force Vercel
  tw deploy docker       # Force Docker
"""

from __future__ import annotations
import os
import json
from typing import Optional


# Preserve backwards-compat re-exports from framework.py
try:
    from .framework import (  # noqa: F401
        deploy_with_cloudflare,
        deploy_with_docker,
        deploy_with_netlify,
        deploy_with_vercel,
        run_deploy,
    )
except ImportError:
    pass


def detect_deploy_target(project_root: str = ".") -> str:
    """Auto-detect deployment target from project files."""
    pr = os.path.abspath(project_root)
    if os.path.exists(os.path.join(pr, "vercel.json")):
        return "vercel"
    if os.path.exists(os.path.join(pr, "netlify.toml")):
        return "netlify"
    if os.path.exists(os.path.join(pr, "wrangler.toml")):
        return "cloudflare"
    if os.path.exists(os.path.join(pr, "Dockerfile")):
        return "docker"
    if os.path.exists(os.path.join(pr, ".github")):
        return "github"
    api_dir = os.path.join(pr, "app", "api")
    if os.path.isdir(api_dir):
        return "vercel"
    has_twm = False
    app_dir = os.path.join(pr, "app")
    if os.path.isdir(app_dir):
        for root, dirs, files in os.walk(app_dir):
            for f in files:
                if f.endswith(".twm"):
                    has_twm = True
                    break
            if has_twm:
                break
    if has_twm:
        return "vercel"
    return "static"


def deploy(target: str = None, project_root: str = ".") -> dict:
    """Generate deployment configuration."""
    pr = os.path.abspath(project_root)
    if target is None:
        target = detect_deploy_target(pr)

    files = {}

    if target == "vercel":
        config = {"buildCommand": "tw build", "outputDirectory": "dist",
                  "framework": "tw",
                  "rewrites": [{"source": "/api/(.*)", "destination": "/api/$1"}]}
        files["vercel.json"] = json.dumps(config, indent=2)

    elif target == "netlify":
        config = "[build]\n  command = \"tw build\"\n  publish = \"dist\"\n"
        files["netlify.toml"] = config

    elif target == "cloudflare":
        config = {"build": {"command": "tw build", "output": "dist"}}
        files["wrangler.toml"] = json.dumps(config, indent=2)

    elif target == "github":
        files[".nojekyll"] = ""
        wf = ("name: Deploy to GitHub Pages\n"
              "on:\n  push:\n    branches: [main]\n"
              "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - uses: actions/checkout@v4\n"
              "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n"
              "      - run: pip install tw-framework\n"
              "      - run: tw build\n"
              "      - uses: peaceiris/actions-gh-pages@v3\n        with:\n"
              "          github_token: ${{ secrets.GITHUB_TOKEN }}\n          publish_dir: ./dist\n")
        files[".github/workflows/deploy.yml"] = wf

    elif target == "docker":
        df = ("FROM python:3.12-slim\nWORKDIR /app\n"
              "RUN pip install tw-framework\nCOPY . .\nRUN tw build\n"
              "EXPOSE 8080\nCMD [\"python\", \"-m\", \"http.server\", \"8080\", \"--directory\", \"dist\"]\n")
        files["Dockerfile"] = df

    else:
        config = {"output": "dist", "serve": "python -m http.server 8080 --directory dist"}
        files["deploy-info.json"] = json.dumps(config, indent=2)

    for fp, content in files.items():
        full = os.path.join(pr, fp)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    return {"target": target, "files_created": list(files.keys()),
            "message": "Deployment config generated for " + target}

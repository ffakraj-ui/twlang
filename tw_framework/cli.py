from typing import Any, Dict, List, Optional

import argparse
import json
import os
import re
import threading
import time
import webbrowser

from . import compiler, framework
from .common import log
from .lexer import tokenize_file
from .lowering import lower_program
from .parser import parse_file
from .npm_manager import (
    install_packages as npm_install_packages,
    remove_packages as npm_remove_packages,
    list_packages as npm_list_packages,
    verify_node_modules as npm_verify_node_modules,
    ensure_dependencies as npm_ensure_dependencies,
)
from .semantic import analyze_program


CLI_NAME = "tw"
GLOBAL_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tw-framework")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "config.json")


STARTER_FILES = {
    "tw.config": """name: My TW Site
site_url: http://localhost:3000
description: A modern TW App Router project
theme: system
pretty_urls: true
search: true
modular_pipeline: true
allow_raw_script: true
sitemap: true
robots: true
rss: true
auto_image_alt: true
""",
    ".env": """SITE_NAME=My TW Site
API_TOKEN=change-me
""",
    "middleware.tw": '''use {
    match "/dashboard/**"
    header "X-Content-Type-Options" "nosniff"
    header "X-Frame-Options" "DENY"
}
''',
    "[home]/layout.tw": '''page {
    title "My TW Site"
    render static
}

load "@./style.tss"

head {
    meta { charset "utf-8" }
    meta { name "viewport", content "width=device-width, initial-scale=1" }
    meta { name "theme-color", content "#0f172a" }
    seo {
        description "A modern TW App Router project - zero JS by default"
    }
}

body {
    Navbar {}
    main { class "main-content"
        children
    }
    Footer {}
}
''',
    "[home]/page.tw": '''page {
    title "Home"
    render static
}

body {
    section { class "hero"
        h1 "Build Modern Web Apps"
        p { class "hero-sub" text "Write .tw files. Run tw dev. Ship fast. Zero JS by default." }
        Button { href "/about", label "Get Started" }
    }
    section { class "features"
        h2 { class "section-title" text "Why TW Framework?" }
        div { class "feature-grid"
            Card { title "Zero JS by Default", description "Static HTML output with zero client-side JavaScript unless you opt in." }
            Card { title "App Router", description "Nested layouts, dynamic routes, API routes - all file-based." }
            Card { title "Component System", description "Build reusable UI components with scoped CSS and props." }
            Card { title "Image Optimization", description "Use the image tag for lazy loading, srcset, and responsive images." }
            Card { title "Scoped CSS", description "Component-level styles that do not leak - CSS Modules built in." }
            Card { title "Deploy Anywhere", description "Static output that works on Vercel, Netlify, GitHub Pages, or any host." }
        }
    }
}
''',
    "[home]/style.tss": '''body {
    margin 0
    font-family system-ui, -apple-system, sans-serif
    background var(--tw-bg)
    color var(--tw-fg)
    line-height 1.6
    -webkit-font-smoothing antialiased
}

:root {
    --tw-bg #ffffff
    --tw-fg #0b1220
    --tw-card #f8fafc
    --tw-border #e2e8f0
    --tw-accent #3b82f6
    --tw-accent-fg #ffffff
    --tw-muted #64748b
    --tw-radius 12
    --tw-shadow 0 1 3 rgba(0,0,0,0.08)
    --tw-shadow-hover 0 8 25 rgba(0,0,0,0.12)
}

:root[data-theme="dark"] {
    --tw-bg #0f172a
    --tw-fg #e2e8f0
    --tw-card #1e293b
    --tw-border #334155
    --tw-accent #38bdf8
    --tw-accent-fg #082f49
    --tw-muted #94a3b8
    --tw-shadow 0 1 3 rgba(0,0,0,0.3)
    --tw-shadow-hover 0 8 25 rgba(0,0,0,0.4)
}

.navbar {
    position sticky
    top 0
    z-index 100
    display flex
    align-items center
    justify-content space-between
    padding 16 24
    background var(--tw-card)
    border-bottom 1 solid var(--tw-border)
    backdrop-filter blur(12)
}

.nav-logo {
    font-size 22
    font-weight 800
    color var(--tw-accent)
    text-decoration none
}

.nav-links {
    display flex
    gap 24
}

.nav-link {
    color var(--tw-fg)
    text-decoration none
    font-weight 600
    font-size 15
    opacity 0.8
}

.nav-link:hover {
    opacity 1
}

.main-content {
    min-height calc(100vh - 120)
}

.hero {
    text-align center
    padding 100 24
    background linear-gradient(135deg, var(--tw-card), var(--tw-bg))
}

.hero h1 {
    font-size 56
    font-weight 800
    margin 0 0 16
    background linear-gradient(135deg, var(--tw-accent), #8b5cf6)
    -webkit-background-clip text
    -webkit-text-fill-color transparent
    background-clip text
}

.hero-sub {
    font-size 20
    color var(--tw-muted)
    max-width 600
    margin 0 auto 32
}

.features {
    padding 80 24
    max-width 1200
    margin 0 auto
}

.section-title {
    font-size 36
    font-weight 800
    text-align center
    margin-bottom 48
}

.feature-grid {
    display grid
    grid-template-columns repeat(auto-fill, minmax(320, 1fr))
    gap 24
}

.card {
    background var(--tw-card)
    border 1 solid var(--tw-border)
    border-radius var(--tw-radius)
    padding 28
    box-shadow var(--tw-shadow)
}

.card:hover {
    transform translateY(-4)
    box-shadow var(--tw-shadow-hover)
}

.card h3 {
    font-size 20
    font-weight 700
    margin 0 0 12
    color var(--tw-fg)
}

.card p {
    font-size 15
    color var(--tw-muted)
    margin 0
    line-height 1.6
}

.btn {
    display inline-block
    padding 14 32
    border-radius var(--tw-radius)
    background var(--tw-accent)
    color var(--tw-accent-fg)
    text-decoration none
    font-weight 700
    font-size 16
    border none
    cursor pointer
}

.btn:hover {
    transform translateY(-2)
    opacity 0.9
}

.page {
    max-width 800
    margin 0 auto
    padding 48 24
}

.page h1 {
    font-size 40
    font-weight 800
    margin-bottom 16
}

.blog-list {
    max-width 800
    margin 0 auto
    padding 48 24
}

.blog-list h1 {
    font-size 40
    font-weight 800
    margin-bottom 32
}

.blog-card {
    display block
    background var(--tw-card)
    border 1 solid var(--tw-border)
    border-radius var(--tw-radius)
    padding 24
    margin-bottom 16
    text-decoration none
    color var(--tw-fg)
    box-shadow var(--tw-shadow)
}

.blog-card:hover {
    transform translateY(-2)
    box-shadow var(--tw-shadow-hover)
}

.blog-card h2 {
    font-size 22
    font-weight 700
    margin 0 0 8
}

.blog-card p {
    color var(--tw-muted)
    margin 0 0 8
    font-size 15
}

.blog-card .meta {
    font-size 13
    color var(--tw-muted)
    opacity 0.7
}

.blog-post {
    max-width 720
    margin 0 auto
    padding 48 24
}

.blog-post h1 {
    font-size 40
    font-weight 800
    margin-bottom 8
}

.blog-post .meta {
    color var(--tw-muted)
    font-size 15
    margin-bottom 32
}

.blog-post .excerpt {
    font-size 18
    line-height 1.7
    color var(--tw-fg)
}

.counter {
    max-width 400
    margin 0 auto
    text-align center
    padding 80 24
}

.counter h1 {
    font-size 40
    font-weight 800
    margin-bottom 32
}

.counter-display {
    font-size 72
    font-weight 800
    color var(--tw-accent)
    margin-bottom 32
}

.counter-buttons {
    display flex
    gap 16
    justify-content center
}

.contact-form {
    display flex
    flex-direction column
    gap 16
    max-width 480
    margin 0 auto
}

.contact-form input, .contact-form textarea {
    padding 14
    border-radius var(--tw-radius)
    border 1 solid var(--tw-border)
    background var(--tw-card)
    color var(--tw-fg)
    font-size 16
    font-family inherit
}

.contact-form input:focus, .contact-form textarea:focus {
    outline none
    border-color var(--tw-accent)
}

.footer {
    text-align center
    padding 32 24
    border-top 1 solid var(--tw-border)
    color var(--tw-muted)
    font-size 14
}

.footer p {
    margin 4 0
}

.not-found {
    text-align center
    padding 120 24
}

.not-found h1 {
    font-size 120
    font-weight 800
    color var(--tw-accent)
    margin 0
}

.not-found p {
    font-size 20
    color var(--tw-muted)
    margin-bottom 32
}

@media (max-width: 768) {
    .hero h1 {
        font-size 36
    }
    .hero-sub {
        font-size 16
    }
    .nav-links {
        gap 16
    }
    .feature-grid {
        grid-template-columns 1fr
    }
    .section-title {
        font-size 28
    }
}
''',
    "[home]/not-found.tw": '''page {
    title "Page Not Found"
    render static
}

body {
    div { class "not-found"
        h1 "404"
        p "The page you are looking for does not exist."
        Button { href "/", label "Go Home" }
    }
}
''',
    "[home]/about/page.tw": '''page {
    title "About"
    render static
}

body {
    div { class "page"
        h1 "About TW Framework"
        p "TW Framework is a modern web framework that compiles .tw files into optimized static HTML. It uses an App Router architecture with zero JavaScript by default."
        p "Built for developers who want fast, secure, and lightweight websites without sacrificing developer experience."
        h2 { class "section-title" text "Key Features" }
        div { class "feature-grid"
            Card { title "File-based Routing", description "Create pages by adding .tw files. No configuration needed." }
            Card { title "Zero JS Default", description "Static HTML output. Add interactivity only where needed." }
            Card { title "Type Safe", description "Built-in TypeScript-like type checking for templates." }
        }
        Button { href "/", label "Back Home" }
    }
}
''',
    "[home]/blog/page.tw": '''page {
    title "Blog"
    render static
}

load "@./blog/posts.json"

body {
    div { class "blog-list"
        h1 "Blog"
        p "Latest articles and updates from the TW Framework team."
        each posts as post {
            a { class "blog-card", href "/blog/{post.slug}"
                h2 "{post.title}"
                p "{post.excerpt}"
                p { class "meta" text "By {post.author} - {post.date}" }
            }
        }
    }
}
''',
    "[home]/blog/[slug]/page.tw": '''page {
    title "{title}"
    render static
    generateStaticParams "../posts.json"
}

body {
    article { class "blog-post"
        h1 "{title}"
        p { class "meta" text "By {author} - {date}" }
        div { class "excerpt"
            p "{excerpt}"
        }
        a { class "btn", href "/blog", text "Back to Blog" }
    }
}
''',
    "[home]/blog/posts.json": '[\n    {"slug": "getting-started", "title": "Getting Started with TW", "author": "TW Team", "date": "2026-08-01", "excerpt": "Learn how to build your first TW Framework app from scratch. Install the CLI, create a project, and deploy in minutes."},\n    {"slug": "app-router-guide", "title": "App Router Guide", "author": "TW Team", "date": "2026-08-03", "excerpt": "Understand nested layouts, dynamic routes, and API routes in TW Framework App Router architecture."},\n    {"slug": "components-explained", "title": "Components Explained", "author": "TW Team", "date": "2026-08-05", "excerpt": "Build reusable UI components with TW component system. Props, scoped CSS, and composition patterns."},\n    {"slug": "styling-with-tss", "title": "Styling with TSS", "author": "TW Team", "date": "2026-08-07", "excerpt": "Master the TW Style System with CSS variables, dark mode support, and responsive design."},\n    {"slug": "deployment-guide", "title": "Deployment Guide", "author": "TW Team", "date": "2026-08-09", "excerpt": "Deploy your TW app to Vercel, Netlify, GitHub Pages, or any static hosting provider."}\n]\n',
    "[home]/counter/page.tw": '''page {
    title "Counter Demo"
    render static
}

state {
    count 0
}

body {
    div { class "counter"
        h1 "Reactive Counter"
        p { class "counter-display" text "{count}" }
        div { class "counter-buttons"
            button {
                on:click "__tw.set('count', __tw.get('count') + 1)"
                class "btn"
                text "+"
            }
            button {
                on:click "__tw.set('count', __tw.get('count') - 1)"
                class "btn"
                text "-"
            }
            button {
                on:click "__tw.set('count', 0)"
                class "btn"
                text "Reset"
            }
        }
    }
}
''',
    "[home]/contact/page.tw": '''page {
    title "Contact"
    render static
}

body {
    div { class "page"
        h1 "Contact Us"
        p "Have a question? Send us a message and we will get back to you."
        form { class "contact-form", method "post", action "/api/contact"
            input { type "text", name "name", placeholder "Your name", required true }
            input { type "email", name "email", placeholder "Email address", required true }
            textarea { name "message", placeholder "Your message", rows 5, required true }
            button { type "submit", class "btn", text "Send Message" }
        }
    }
}
''',
    "[home]/components/Navbar.tw": '''nav { class "navbar"
    a "TW" { href "/", class "nav-logo" }
    div { class "nav-links"
        a "Home" { href "/", class "nav-link" }
        a "About" { href "/about", class "nav-link" }
        a "Blog" { href "/blog", class "nav-link" }
        a "Counter" { href "/counter", class "nav-link" }
        a "Contact" { href "/contact", class "nav-link" }
    }
}
''',
    "[home]/components/Footer.tw": '''footer { class "footer"
    p "Built with TW Framework"
    p "Zero JS by default - App Router - Static-first"
}
''',
    "[home]/components/Button.tw": '''a { class "btn", href "{href}"
    text "{label}"
}
''',
    "[home]/components/Card.tw": '''div { class "card"
    h3 "{title}"
    p "{description}"
}
''',
    "[home]/api/contact/route.tw": '''fn post(request) {
    return {
        status: 200,
        json: { ok: true, message: "Thanks for your message!", received: request.body || {} }
    };
}
''',
    "[home]/api/users/route.tw": '''fn get(request) {
    return {
        status: 200,
        json: [
            { id: 1, name: "Ada Lovelace" },
            { id: 2, name: "Grace Hopper" },
            { id: 3, name: "Dennis Ritchie" }
        ]
    };
}
''',
    ".gitignore": """.tw/
.tw-cache/
dist/
__pycache__/
*.pyc
node_modules/
""",
}


def ensure_dir(path) -> None:
    os.makedirs(path, exist_ok=True)


def _restrict_global_config_permissions() -> None:
    try:
        os.chmod(GLOBAL_CONFIG_DIR, 0o700)
    except Exception:
        pass
    try:
        os.chmod(GLOBAL_CONFIG_FILE, 0o600)
    except Exception:
        pass


def write_text(path, content) -> None:
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def slugify_package_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9-_]+", "-", name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "tw-site"


def build_package_json(project_name) -> Any:
    package_name = slugify_package_name(project_name)
    return json.dumps(
        {
            "name": package_name,
            "private": True,
            "version": "0.1.0",
            "scripts": {
                "dev": "tw dev",
                "build": "tw build",
                "export": "tw export",
                "preview": "tw preview",
                "clean": "tw clean",
                "doctor": "tw doctor",
                "info": "tw info",
                "deploy": "tw deploy",
            },
            "dependencies": {},
            "devDependencies": {},
        },
        indent=2,
    ) + "\n"


def build_vercel_json() -> Any:
    return json.dumps(
        {
            "buildCommand": "npx tw build",  # FIX #278: Use npx in case tw is not global
            "outputDirectory": "dist",
        },
        indent=2,
    ) + "\n"


def load_global_config() -> Any:
    if not os.path.exists(GLOBAL_CONFIG_FILE):
        return {}
    try:
        with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as err:
        # Don't silently wipe config if the file is corrupt.
        log(f"⚠️ Failed to read global config (ignoring): {GLOBAL_CONFIG_FILE} ({err})", level="warning")
        return {}


def save_global_config(config) -> None:
    ensure_dir(GLOBAL_CONFIG_DIR)
    _restrict_global_config_permissions()
    # Atomic write (temp-file + rename) to avoid corrupting config on crash/kill.
    tmp_path = GLOBAL_CONFIG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
    os.replace(tmp_path, GLOBAL_CONFIG_FILE)
    _restrict_global_config_permissions()


def find_project_root(start_dir=None) -> Any:
    current = os.path.abspath(start_dir or os.getcwd())
    # FIX #279: Limit depth to prevent walking to filesystem root
    _max_depth = 20
    _depth = 0
    while _depth < _max_depth:
        config_path = os.path.join(current, "tw.config")
        home_dir = os.path.join(current, "[home]")
        if os.path.exists(config_path) and os.path.isdir(home_dir):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        _depth += 1
    raise RuntimeError(
        "TW project root not found. Run `tw create <name>` or `cd` into a TW project folder."
    )


def create_project(project_name, parent_dir=None) -> None:
    parent_dir = os.path.abspath(parent_dir or os.getcwd())
    root = os.path.join(parent_dir, project_name)
    if os.path.exists(root) and os.listdir(root):
        raise RuntimeError(f"Target folder already exists and is not empty: {root}")

    ensure_dir(root)
    for rel_path, content in STARTER_FILES.items():
        write_text(os.path.join(root, rel_path), content)

    write_text(os.path.join(root, "package.json"), build_package_json(project_name))
    write_text(os.path.join(root, "vercel.json"), build_vercel_json())

    for extra_dir in [
        os.path.join(root, ".tw", "cache"),
        os.path.join(root, ".tw", "manifest"),
        os.path.join(root, ".tw", "compiler", "chunks"),
        os.path.join(root, "dist"),
        os.path.join(root, "public"),
        os.path.join(root, "[home]", "assets", "images"),
        os.path.join(root, "[home]", "assets", "js"),
        os.path.join(root, "[home]", "assets", "css"),
        os.path.join(root, "[home]", "assets", "fonts"),
        os.path.join(root, "[home]", "api", "contact"),
        os.path.join(root, "[home]", "api", "users"),
        os.path.join(root, "[home]", "about"),
        os.path.join(root, "[home]", "blog", "[slug]"),
        os.path.join(root, "[home]", "counter"),
        os.path.join(root, "[home]", "contact"),
        os.path.join(root, "[home]", "components"),
        os.path.join(root, "[home]", "lib"),
    ]:
        ensure_dir(extra_dir)

    log(f"✔ Project created: {root}")
    log("Next steps:")
    log(f"  cd {project_name}")
    log(f"  {CLI_NAME} dev")


def open_browser_later(url) -> None:
    timer = threading.Timer(1.0, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def resolve_output_dir(project_root) -> Any:
    return os.path.join(project_root, "dist")


def configure_project_for_file(file_path) -> Any:
    abs_path = os.path.abspath(file_path)
    try:
        project_root = find_project_root(os.path.dirname(abs_path))
    except Exception:
        return None
    framework.configure_compiler_paths(project_root)
    return project_root


def _guess_route_for_file(abs_path) -> Any:
    for page_info in compiler.discover_pages():
        if os.path.abspath(page_info["path"]) == abs_path:
            return compiler.route_path_from_page_info(page_info)
    return "/"


def _diagnostics_have_errors(items) -> Any:
    return any(item.get("severity") == "error" for item in items or [])


def _serialize_token(token) -> Any:
    if hasattr(token, "to_dict"):
        return token.to_dict()
    return {
        "type": getattr(token, "type", ""),
        "value": getattr(token, "value", ""),
        "line": getattr(token, "line", 0),
        "col": getattr(token, "col", 0),
    }


def _json_safe(value) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _json_safe(
                {
                    key: item
                    for key, item in vars(value).items()
                    if not str(key).startswith("_")
                }
            )
        except Exception:
            pass
    return repr(value)


def _diagnostic_summary(items) -> Any:
    summary = {"total": 0, "errors": 0, "warnings": 0, "info": 0, "by_phase": {}, "by_code": {}}
    for item in items or []:
        summary["total"] += 1
        severity = str(item.get("severity", "info") or "info").lower()
        if severity == "error":
            summary["errors"] += 1
        elif severity == "warning":
            summary["warnings"] += 1
        else:
            summary["info"] += 1
        phase = item.get("phase") or "unspecified"
        summary["by_phase"][phase] = summary["by_phase"].get(phase, 0) + 1
        code = item.get("code") or "unknown"
        summary["by_code"][code] = summary["by_code"].get(code, 0) + 1
    return summary


def _compile_file_artifacts(file_path, *, include_css=False, capture_errors=False) -> Any:
    abs_path = os.path.abspath(file_path)
    configure_project_for_file(abs_path)
    css_href = None
    if include_css and os.path.exists(getattr(compiler, "STYLE_FILE", "")):
        css_href, _ = compiler.read_global_stylesheet()
    return compiler.compile_file_pipeline(
        abs_path,
        css_href=css_href,
        route_path=_guess_route_for_file(abs_path),
        capture_errors=capture_errors,
    )


def command_create(args) -> None:
    create_project(args.name, args.directory)


def command_init(args) -> None:
    """Create a new TW project in the current directory (zero‑config)."""
    project_name = args.name or os.path.basename(os.getcwd())
    create_project(project_name, os.getcwd())


def command_dev(args) -> int:
    project_root = find_project_root(args.project_root)
    host = args.host
    port = args.port
    url = f"http://{host}:{port}"
    if not args.no_open:
        open_browser_later(url)
    try:
        framework.run_dev_server(project_root, host, port)
    except Exception as err:
        log(f"✖ Dev server start failed: {err}", level="error")
        return 1
    return 0


def command_build(args) -> Any:
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    if args.clean:
        framework.clean_project_outputs(project_root)
    strict = bool(getattr(args, "strict", False))
    fail_on_warnings = bool(
        strict or getattr(args, "fail_on_warnings", False) or getattr(args, "prod", False)
    )
    debug = getattr(args, "debug", False)

    adapters = [args.adapter] if args.adapter else None

    def run_once(force_build=False) -> Any:
        summary = framework.build_hidden_site(
            project_root=project_root,
            output_dir=output_dir,
            force=args.force or force_build,
            workers=args.workers,
            minify=(args.prod or not args.dev) and not args.no_minify,
            strict=strict,
            adapters=adapters,
            debug=debug,
        )
        if summary.errors:
            log(f"✖ Build finished with {summary.errors} error(s)", level="error")
            return summary, 1
        if getattr(summary, "warnings", 0):
            log(f"⚠️  Build warnings: {summary.warnings}", level="warning")
            if fail_on_warnings:
                if getattr(args, "prod", False) and not getattr(args, "fail_on_warnings", False):
                    log("✖ Failing build because --prod implies --fail-on-warnings", level="error")
                else:
                    log("✖ Failing build because --fail-on-warnings was set", level="error")
                return summary, 1
        log("✔ Build completed")
        log(f"✔ Optimized {summary.built} page(s)")
        if summary.skipped:
            log(f"✔ Reused cache for {summary.skipped} page(s)")
        if args.analyze:
            route_manifest = os.path.join(output_dir, "_tw", "route-manifest.json")
            api_manifest = os.path.join(output_dir, "_tw", "api-manifest.json")
            log(f"✔ Route analysis: {route_manifest}")
            log(f"✔ API analysis: {api_manifest}")
        log("✔ Ready for deployment")
        return summary, 0

    _, code = run_once()
    if code or not args.watch:
        # generate_deploy_metadata() is already called inside
        # framework.build_hidden_site() (framework.py ~line 3209),
        # so we don't need to call it again here — that was a
        # duplicate call causing wasted file I/O (fixed v0.8.1).
        return code

    watcher_project = framework.TWProject(project_root)
    watched = watcher_project.list_source_files()
    last_stats = {}
    for p in watched:
        try:
            st = os.stat(p)
            last_stats[p] = (st.st_mtime_ns, st.st_size)
        except Exception:
            last_stats[p] = None
    log("👀 Build watch mode active")
    try:
        while True:
            time.sleep(1)
            changed = False
            for p in list(watched):
                try:
                    st = os.stat(p)
                    sig = (st.st_mtime_ns, st.st_size)
                except Exception:
                    sig = None
                if last_stats.get(p) != sig:
                    changed = True
                    break
            if not changed:
                new_list = watcher_project.list_source_files()
                if set(new_list) != set(watched):
                    changed = True

            if changed:
                watched = watcher_project.list_source_files()
                last_stats = {}
                for p in watched:
                    try:
                        st = os.stat(p)
                        last_stats[p] = (st.st_mtime_ns, st.st_size)
                    except Exception:
                        last_stats[p] = None
                watcher_project.invalidate()
                log("↻ Change detected, rebuilding...")
                _, code = run_once(force_build=True)
                if code:
                    log("⚠️  Watching will continue. Fix the error(s) and save the file to retry.", level="warning")
    except KeyboardInterrupt:
        log("\nWatch mode stopped")
    return 0


def command_export(args) -> int:
    project_root = find_project_root(args.project_root)
    summary = framework.build_hidden_site(
        project_root=project_root,
        output_dir=args.out_dir or resolve_output_dir(project_root),
        force=True,
        workers=args.workers,
        minify=not args.no_minify,
    )

    if summary.errors:
        log(f"✖ Export finished with {summary.errors} error(s)", level="error")
        return 1
    if getattr(summary, "warnings", 0):
        log(f"⚠️  Export warnings: {summary.warnings}", level="warning")
        if args.fail_on_warnings:
            log("✖ Failing export because --fail-on-warnings was set", level="error")
            return 1

    log("✔ Static export completed")
    log(f"✔ Output ready in {summary.output_dir}")
    return 0


def command_preview(args) -> Any:
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    if not args.no_build:
        # FIX #285/#286: Use proper args namespace and check result correctly
        # (0 is a valid success return, not falsy)
        export_args = argparse.Namespace(
            project_root=project_root,
            out_dir=output_dir,
            workers=args.workers,
            no_minify=args.no_minify,
            debug=False,
        )
        result = command_export(export_args)
        if result is not None and result != 0:
            return result

    url = f"http://{args.host}:{args.port}"
    if not args.no_open:
        open_browser_later(url)
    framework.run_preview_server(output_dir=output_dir, host=args.host, port=args.port)


def command_clean(args) -> int:
    project_root = find_project_root(args.project_root)
    framework.clean_project_outputs(project_root)
    log("✔ dist/ and .tw/ cleaned successfully")  # FIX #287: Use English for consistency
    return 0


def command_doctor(args) -> Any:
    project_root = find_project_root(args.project_root)
    checks = framework.doctor_project(project_root)
    # Extra CLI-level checks (global deploy config)
    config = load_global_config()
    if os.path.exists(GLOBAL_CONFIG_FILE):
        checks.append({"name": "Global deploy config", "ok": True, "detail": GLOBAL_CONFIG_FILE})
    else:
        checks.append({"name": "Global deploy config", "ok": False, "detail": f"Missing: {GLOBAL_CONFIG_FILE} (run `tw login` to create it)"})
    # FIX #288: Vercel token is informational, not a blocking check
    if config.get("vercel_token") or os.environ.get("VERCEL_TOKEN"):
        checks.append({"name": "Vercel token (optional)", "ok": True, "detail": "Token available"})
    else:
        checks.append({"name": "Vercel token (optional)", "ok": True, "detail": "Not set (only needed for `tw deploy --provider vercel`)"})
    failed = 0
    for check in checks:
        status = "OK" if check["ok"] else "WARN"
        log(f"[{status}] {check['name']}: {check['detail']}", level="warning" if status == "WARN" else "info")
        if not check["ok"] and check["name"] in {"tw.config", "[home]", "Route discovery"}:
            failed += 1
    return 1 if failed else 0


def command_info(args) -> int:
    project_root = find_project_root(args.project_root)
    info = framework.inspect_project(project_root)
    # FIX #289: Use log() for consistent output
    log(f"Project root: {info['project_root']}")
    log(f"Source root: {info['source_root']}")
    log(f"Output dir: {info['output_dir']}")
    log(f"Hidden dir: {info['hidden_dir']}")
    log(f"Pages: {info['page_count']}")
    log(f"Static routes: {info['static_routes']}")
    log(f"Dynamic routes: {info['dynamic_routes']}")
    log(f"Components: {info['component_count']}")
    log(f"Custom 404: {'yes' if info['has_404'] else 'no'}")
    log(f"Custom 500: {'yes' if info['has_500'] else 'no'}")
    log(f"Modular pipeline: {'yes' if info['modular_pipeline'] else 'no'}")
    node_status = f"detected ({info['node_path']})" if info.get('node_detected') else "not detected (API routes disabled)"
    log(f"Node.js: {node_status}")
    api_count = info.get('api_route_count', 0)
    if api_count > 0:
        if info.get('api_routes_disabled'):
            log(f"API routes: {api_count} found (DISABLED without Node.js)")
        else:
            log(f"API routes: {api_count} found (enabled)")
    else:
        log(f"API routes: 0 found")
    mw_status = f"detected ({info['middleware_path']})" if info.get('middleware_detected') else "not found"
    log(f"Middleware: {mw_status}")
    return 0


def _write_or_print_output(output_path, payload) -> None:
    if output_path:
        write_text(output_path, payload)
        log(f"✔ Output saved: {output_path}")
        return
    print(payload)


def command_ast(args) -> Any:
    # FIX #290: Check file exists before attempting to parse
    if not os.path.exists(args.file):
        log(f"✖ File not found: {args.file}", level="error")
        return 1
    configure_project_for_file(args.file)
    program = parse_file(os.path.abspath(args.file))
    diagnostics = analyze_program(program)
    payload = {
        "ast": program.to_dict(),
    }
    if args.diagnostics:
        payload["diagnostics"] = diagnostics.to_list()
        payload["summary"] = _diagnostic_summary(payload["diagnostics"])
    _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    return 1 if diagnostics.has_errors else 0


def command_ir(args) -> Any:
    configure_project_for_file(args.file)
    program = parse_file(os.path.abspath(args.file))
    diagnostics = analyze_program(program)
    ir_program = lower_program(program)
    payload = {
        "ir": ir_program.to_dict(),
    }
    if args.diagnostics:
        payload["diagnostics"] = diagnostics.to_list()
        payload["summary"] = _diagnostic_summary(payload["diagnostics"])
    _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    return 1 if diagnostics.has_errors else 0


def command_run_file(args) -> Any:
    artifacts = _compile_file_artifacts(args.file, include_css=True, capture_errors=args.diagnostics)
    # FIX #291: Warn when compilation produced no HTML output
    if not artifacts.html:
        log("⚠️  Compilation produced no HTML output", level="warning")
    if args.diagnostics:
        payload = {
            "html": artifacts.html or "",
            "diagnostics": artifacts.diagnostics,
            "metadata": artifacts.metadata,
            "dependencies": artifacts.dependencies,
            "summary": _diagnostic_summary(artifacts.diagnostics),
        }
        _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    else:
        _write_or_print_output(args.out, artifacts.html or "")
    return 1 if _diagnostics_have_errors(artifacts.diagnostics) else 0


def command_tokens(args) -> int:
    configure_project_for_file(args.file)
    payload = {
        "tokens": [_serialize_token(token) for token in tokenize_file(os.path.abspath(args.file))]
    }
    _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    return 0


def command_check(args) -> Any:
    artifacts = _compile_file_artifacts(args.file, capture_errors=True)
    payload = {
        "diagnostics": artifacts.diagnostics,
        "metadata": artifacts.metadata,
        "dependencies": artifacts.dependencies,
        "route_path": artifacts.route_path,
        "pipeline": artifacts.pipeline,
        "summary": _diagnostic_summary(artifacts.diagnostics),
    }
    if args.include_ast:
        payload["ast"] = artifacts.ast
    if args.include_ir:
        payload["ir"] = artifacts.ir
    _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    return 1 if _diagnostics_have_errors(artifacts.diagnostics) else 0
    

def command_verify(args) -> int:
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    manifest_path = os.path.join(output_dir, "_tw", "route-manifest.json")
    if not os.path.exists(manifest_path):
        log(f" Route manifest not found: {manifest_path}. Run `tw build` first.", level="error")
        return 1

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    routes = manifest.get("routes") if isinstance(manifest, dict) else manifest
    if not isinstance(routes, list):
        log(" Unexpected route-manifest.json format; cannot verify.", level="error")
        return 1

    from .signature import compute_tw_signature

    total = 0
    ok = 0
    mismatched = []
    for route in routes:
        source_path = route.get("source") or route.get("source_path") or route.get("file")
        output_path = route.get("output") or route.get("output_path") or route.get("html_path")
        route_name = route.get("route") or route.get("path") or source_path or "?"
        if not source_path or not output_path:
            continue
        abs_source = os.path.join(project_root, source_path) if not os.path.isabs(source_path) else source_path
        abs_output = os.path.join(output_dir, output_path) if not os.path.isabs(output_path) else output_path
        if not os.path.exists(abs_source) or not os.path.exists(abs_output):
            continue

        total += 1
        try:
            program = parse_file(abs_source)
            expected_sig = compute_tw_signature(program)
        except Exception as err:
            mismatched.append((route_name, f"failed to recompile source: {err}"))
            continue

        with open(abs_output, "r", encoding="utf-8") as f:
            built_html = f.read()

        match = re.search(r'name="tw-signature"\s+content="([a-f0-9]+)"', built_html)
        found_sig = match.group(1) if match else None

        if found_sig == expected_sig:
            ok += 1
        else:
            mismatched.append((route_name, f"expected {expected_sig}, found {found_sig or 'none'}"))

    log(f" Verified {ok}/{total} route(s) against their TW source.")
    if mismatched:
        log(f"  {len(mismatched)} mismatch(es):", level="warning")
        for name, detail in mismatched:
            log(f"   - {name}: {detail}", level="warning")
        return 1
    return 0


def apply_deploy_config(config, provider) -> Any:
    """Returns a cleanup callable to restore env changes."""
    cleanup = lambda: None
    if provider == "vercel" and config.get("vercel_token"):
        old_value = os.environ.get("VERCEL_TOKEN")
        os.environ["VERCEL_TOKEN"] = config["vercel_token"]

        def cleanup() -> None:
            if old_value is None:
                os.environ.pop("VERCEL_TOKEN", None)
            else:
                os.environ["VERCEL_TOKEN"] = old_value

    return cleanup


def resolve_provider(args, config) -> Any:
    if args.vercel:
        return "vercel"
    if args.cloudflare:
        return "cloudflare"
    if args.provider:
        return args.provider
    return config.get("default_provider", "local")


def command_login(args) -> None:
    # FIX #293: Token is stored in a file with restrictive permissions (0600)
    config = load_global_config()
    if args.provider:
        config["default_provider"] = args.provider
    if args.vercel_token:
        config["vercel_token"] = args.vercel_token
    save_global_config(config)
    log("✔ TW deploy config saved")
    if config.get("default_provider"):
        log(f"✔ Default provider: {config['default_provider']}")


def command_deploy(args) -> int:
    project_root = find_project_root(args.project_root)
    config = load_global_config()
    provider = resolve_provider(args, config)
    # FIX #294: apply_deploy_config sets env vars — cleanup restores them
    cleanup = apply_deploy_config(config, provider)
    try:
        if provider == "vercel" and not (os.environ.get("VERCEL_TOKEN") or config.get("vercel_token")):
            log("✖ Missing Vercel token. Set `VERCEL_TOKEN` or run `tw login --vercel-token <token>`.", level="error")
            return 1
        framework.run_deploy(
            project_root=project_root,
            output_dir=args.out_dir or resolve_output_dir(project_root),
            provider=provider,
            production=args.prod or provider in {"vercel", "cloudflare", "netlify", "docker"},
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    finally:
        cleanup()
    if getattr(args, "dry_run", False):
        log("✔ Deploy dry-run completed")
    else:
        log("✔ Deploy completed")
    return 0


def command_plugin(args) -> int:
    """v0.9.08: Plugin management."""
    # FIX #295: Warn about arbitrary code execution risk
    if args.plugin_action in ("add", "install"):
        log("⚠️  Warning: Plugins can execute arbitrary code. Only install from trusted sources.", level="warning")
    from . import plugin_manager

    action = getattr(args, "plugin_action", None)
    name = getattr(args, "plugin_name", None)

    if action == "add" and name:
        log("Installing plugin: " + name + "...")
        result = plugin_manager.install_plugin(name)
        if result.get("success"):
            log("  Installed: " + result.get("plugin", name) + " v" + str(result.get("version", "?")))
            return 0
        else:
            log("  Error: " + str(result.get("error")), level="error")
            return 1

    elif action == "remove" and name:
        result = plugin_manager.remove_plugin(name)
        if result.get("success"):
            log("  Removed: " + name)
            return 0
        else:
            log("  Error: " + str(result.get("error")), level="error")
            return 1

    elif action == "list":
        pm = plugin_manager.PluginManager()
        pm.load_all()
        plugins = pm.list_plugins()
        if not plugins:
            log("No plugins installed")
            return 0
        for p in plugins:
            status = "enabled" if p["enabled"] else "disabled"
            hooks = ", ".join(p["hooks"]) or "none"
            log("  " + p["name"] + " v" + p["version"] + " [" + status + "] hooks: " + hooks)
        return 0

    elif action == "search":
        registry = plugin_manager.fetch_registry()
        if "error" in registry:
            log("  Error: " + registry["error"], level="error")
            return 1
        plugins = registry.get("plugins", [])
        if not plugins:
            log("No plugins available in registry")
            return 0
        log("Available plugins:")
        for p in plugins:
            log("  " + p["name"] + " v" + p.get("version", "?") + " - " + p.get("description", ""))
        return 0

    else:
        log("Usage: tw plugin <add|remove|list|search> [name]")
        return 1


def command_serve(args) -> int:
    """Start the TW production server."""
    from .server import run_production_server
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    host = args.host or os.environ.get("TW_HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("TW_PORT", "8000"))

    # Optionally build first
    if not args.no_build:
        log("Building before serve...")
        summary = framework.build_hidden_site(
            project_root=project_root,
            output_dir=output_dir,
            force=False,
            minify=not args.no_minify,
        )
        if summary.errors:
            log(f"✖ Build had {summary.errors} error(s). Serving anyway...", level="error")
        if getattr(summary, "warnings", 0):
            log(f"⚠️  Build warnings: {summary.warnings}", level="warning")
            if args.fail_on_warnings:
                log("✖ Not starting server because --fail-on-warnings was set", level="error")
                return 1

    try:
        run_production_server(
            project_root=project_root,
            host=host,
            port=port,
            output_dir=output_dir if os.path.isdir(output_dir) else None,
        )
    except Exception as err:
        log(f"✖ Server error: {err}", level="error")
        return 1
    return 0


def command_install(args) -> int:
    """Install npm packages — like `npm install` in Next.js."""
    project_root = find_project_root(args.project_root) if args.project_root else os.getcwd()
    # If no project root found and no packages, try current dir
    try:
        project_root = find_project_root(args.project_root)
    except Exception:
        if args.packages:
            # Create a minimal project in current dir
            project_root = os.getcwd()
            if not os.path.exists(os.path.join(project_root, "package.json")):
                write_text(
                    os.path.join(project_root, "package.json"),
                    build_package_json(os.path.basename(project_root)),
                )
        else:
            log("✖ Not in a TW project. Run `tw create <name>` first or specify --project-root.", level="error")
            return 1

    packages = args.packages or []
    success = npm_install_packages(
        project_root=project_root,
        packages=packages,
        dev=args.dev,
        exact=args.exact,
    )
    return 0 if success else 1


def command_add(args) -> int:
    """Alias for `tw install`."""
    return command_install(args)


def command_remove(args) -> int:
    """Remove npm packages."""
    try:
        project_root = find_project_root(args.project_root)
    except Exception:
        log("✖ Not in a TW project.", level="error")
        return 1

    if not args.packages:
        log("✖ Specify packages to remove: tw remove <package> [package2 ...]", level="error")
        return 1

    success = npm_remove_packages(project_root, args.packages)
    return 0 if success else 1


def command_list(args) -> int:
    """List installed npm packages."""
    try:
        project_root = find_project_root(args.project_root)
    except Exception:
        log("✖ Not in a TW project.", level="error")
        return 1

    npm_list_packages(project_root, detailed=args.detailed)
    return 0




def command_infrastructure(args) -> int:
    """Generate Terraform IaC configuration for AWS."""
    project_root = find_project_root(args.project_root)
    try:
        from .infrastructure import AWSConfig, TerraformGenerator
    except ImportError:
        log("✖ infrastructure module not available", level="error")
        return 1

    config = AWSConfig(region=args.region)
    generator = TerraformGenerator(config)
    tf_code = generator.generate_all()

    out_dir = os.path.join(project_root, args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Write main.tf
    main_tf = os.path.join(out_dir, "main.tf")
    with open(main_tf, "w") as f:
        f.write(tf_code)

    log(f"✔ Infrastructure generated: {main_tf}")
    log(f"  Provider: {args.provider}")
    log(f"  Region: {args.region}")
    log(f"  Components: VPC, ECS, ECR, ALB, S3, CloudFront, WAF, Redis")
    return 0


def command_health(args) -> int:
    """Run health checks on the project."""
    project_root = find_project_root(args.project_root)
    try:
        from .enterprise_features import HealthCheckManager
        manager = HealthCheckManager()
        checks = manager.run_all_checks()
        passed = sum(1 for c in checks if c.get("status") == "healthy")
        failed = sum(1 for c in checks if c.get("status") == "unhealthy")
        for c in checks:
            status = "✔" if c.get("status") == "healthy" else "✖"
            log(f"  {status} {c.get('name', 'unknown')}: {c.get('message', '')}")
        log(f"\n  {passed} healthy, {failed} unhealthy")
        return 1 if failed > 0 else 0
    except Exception as err:
        if getattr(args, "debug", False):
            raise
        log(f"✖ {err}", level="error")
        return 1


def command_routes(args) -> int:
    """List all routes in the project."""
    project_root = find_project_root(args.project_root)
    try:
        from .app_router import AppRouter
        router = AppRouter(os.path.join(project_root, "app"))
        routes = router.discover_routes()
        if not routes:
            log("  No routes found. Create pages in app/ directory.")
            return 0
        log(f"  Found {len(routes)} route(s):\n")
        for r in routes:
            path = getattr(r, "path", str(r))
            page = getattr(r, "page", "")
            log(f"  {path:<30} {page}")
        return 0
    except Exception as err:
        if getattr(args, "debug", False):
            raise
        log(f"✖ {err}", level="error")
        return 1


def build_parser() -> Any:
    parser = argparse.ArgumentParser(description="TW framework CLI")
    parser.add_argument("--debug", action="store_true", help="Show full error details and stack traces")
    parser.add_argument("--version", "-v", action="store_true", help="Show version and exit")
    parser.add_argument("--project-root", help="Manual project root override")

    subparsers = parser.add_subparsers(dest="command", required=False)

    def add_output_dir_arg(subparser, help_text) -> None:
        subparser.add_argument("--out-dir", help=help_text)

    def add_workers_arg(subparser) -> None:
        subparser.add_argument("--workers", type=int, default=framework.compiler.DEFAULT_WORKERS)

    def add_host_port_args(subparser, *, host_default, port_default, allow_no_open=False) -> None:
        subparser.add_argument("--host", default=host_default)
        subparser.add_argument("--port", type=int, default=port_default)
        if allow_no_open:
            subparser.add_argument("--no-open", action="store_true", help="Disable auto-opening the browser")

    def add_no_minify_arg(subparser, help_text) -> None:
        subparser.add_argument("--no-minify", action="store_true", help=help_text)

    create_parser = subparsers.add_parser("create", help="Create a new TW project")
    create_parser.add_argument("name", help="Project folder name")
    create_parser.add_argument("--directory", help="Parent directory where the project will be created")
    create_parser.set_defaults(func=command_create)

    init_parser = subparsers.add_parser("init", help="Create a new TW project in the current directory")
    init_parser.add_argument("name", nargs="?", help="Project folder name (default: current directory name)")
    init_parser.set_defaults(func=command_init)

    doctor_parser = subparsers.add_parser("doctor", help="Run project health checks and deployment compatibility")
    doctor_parser.set_defaults(func=command_doctor)

    dev_parser = subparsers.add_parser("dev", help="Run the local dev server")
    dev_parser.add_argument("project_root", nargs="?", default=None, help="Project root directory")
    add_host_port_args(
        dev_parser,
        host_default=framework.DEFAULT_DEV_HOST,
        port_default=framework.DEFAULT_DEV_PORT,
        allow_no_open=True,
    )
    dev_parser.set_defaults(func=command_dev)

    build_parser = subparsers.add_parser("build", help="Generate a production build")
    add_output_dir_arg(build_parser, "Internal output directory")
    build_parser.add_argument("--force", action="store_true")
    add_workers_arg(build_parser)
    build_parser.add_argument("--dev", action="store_true", help="Development-style non-minified build")
    build_parser.add_argument("--prod", action="store_true", help="Production optimized build")
    build_parser.add_argument("--watch", action="store_true", help="Rebuild on file changes")
    build_parser.add_argument(
        "--analyze",
        action="store_true",
        help="After generating route/API analysis files, print their paths",
    )
    build_parser.add_argument("--clean", action="store_true", help="Clean dist and cache before building")
    add_no_minify_arg(build_parser, "Disable HTML/CSS minification")
    build_parser.add_argument("--fail-on-warnings", action="store_true", help="Treat warnings as build failures")
    build_parser.add_argument("--strict", action="store_true", help="Strict build (= --fail-on-warnings + route collisions are errors)")
    build_parser.add_argument("--adapter", choices=["vercel", "netlify", "cloudflare"], help="Generate adapter-specific config files after build")
    build_parser.add_argument("--report", action="store_true", help="Generate build report after build")
    build_parser.set_defaults(func=command_build)

    export_parser = subparsers.add_parser("export", help="Generate a static export")
    add_output_dir_arg(export_parser, "Export output directory")
    add_workers_arg(export_parser)
    add_no_minify_arg(export_parser, "Disable HTML/CSS minification")
    export_parser.add_argument("--fail-on-warnings", action="store_true", help="Treat warnings as export failures")
    export_parser.set_defaults(func=command_export)

    preview_parser = subparsers.add_parser("preview", help="Preview the built dist output")
    add_output_dir_arg(preview_parser, "Preview output directory")
    add_host_port_args(
        preview_parser,
        host_default=framework.DEFAULT_DEV_HOST,
        port_default=framework.DEFAULT_PREVIEW_PORT,
        allow_no_open=True,
    )
    add_workers_arg(preview_parser)
    preview_parser.add_argument("--no-build", action="store_true", help="Serve the existing dist without rebuilding")
    add_no_minify_arg(preview_parser, "Disable minification in the preview build")
    preview_parser.set_defaults(func=command_preview)

    clean_parser = subparsers.add_parser("clean", help="Clean dist and hidden cache folders")
    clean_parser.set_defaults(func=command_clean)

    info_parser = subparsers.add_parser("info", help="Show a project summary")
    info_parser.set_defaults(func=command_info)

    ast_parser = subparsers.add_parser("ast", help="Print the AST JSON for a TW source file")
    ast_parser.add_argument("file", help=".tw file path")
    ast_parser.add_argument("--out", help="AST JSON file save path")
    ast_parser.add_argument("--diagnostics", action="store_true", help="Include diagnostics in the output")
    ast_parser.set_defaults(func=command_ast)

    ir_parser = subparsers.add_parser("ir", help="Print the IR JSON for a TW source file")
    ir_parser.add_argument("file", help=".tw file path")
    ir_parser.add_argument("--out", help="IR JSON file save path")
    ir_parser.add_argument("--diagnostics", action="store_true", help="Include diagnostics in the output")
    ir_parser.set_defaults(func=command_ir)

    run_parser = subparsers.add_parser("run", help="Interpret a TW file and output HTML")
    run_parser.add_argument("file", help=".tw file path")
    run_parser.add_argument("--out", help="Rendered HTML file save path")
    run_parser.add_argument("--diagnostics", action="store_true", help="Also output a diagnostics payload with the HTML")
    run_parser.set_defaults(func=command_run_file)

    tokens_parser = subparsers.add_parser("tokens", help="Print the token stream JSON for a TW source file")
    tokens_parser.add_argument("file", help=".tw file path")
    tokens_parser.add_argument("--out", help="Tokens JSON file save path")
    tokens_parser.set_defaults(func=command_tokens)

    check_parser = subparsers.add_parser("check", help="Print diagnostics for a TW file")
    check_parser.add_argument("file", help=".tw file path")
    check_parser.add_argument("--out", help="Diagnostics JSON file save path")
    check_parser.add_argument("--include-ast", action="store_true", help="Include AST in the output")
    check_parser.add_argument("--include-ir", action="store_true", help="Include IR in the output")
    check_parser.set_defaults(func=command_check)

    login_parser = subparsers.add_parser("login", help="Save deploy provider configuration")
    login_parser.add_argument("--provider", choices=["local", "vercel", "cloudflare", "netlify", "github-pages", "docker"])
    login_parser.add_argument("--vercel-token", help="Save a Vercel token")
    login_parser.set_defaults(func=command_login)

    deploy_parser = subparsers.add_parser("deploy", help="Deploy the current project")
    add_output_dir_arg(deploy_parser, "Internal output directory")
    deploy_parser.add_argument("--provider", choices=["local", "vercel", "cloudflare", "netlify", "github-pages", "docker"])
    deploy_parser.add_argument("--vercel", action="store_true", help="Use the Vercel provider")
    deploy_parser.add_argument("--cloudflare", action="store_true", help="Use the Cloudflare provider")
    deploy_parser.add_argument("--prod", action="store_true", help="Production deploy flag")
    deploy_parser.add_argument("--dry-run", action="store_true", help="Validate config + build, but do not deploy")
    deploy_parser.set_defaults(func=command_deploy)

    # v0.9.08: Plugin management
    plugin_parser = subparsers.add_parser("plugin", aliases=["plugins"], help="Manage TW plugins")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_action")
    add_p = plugin_sub.add_parser("add", aliases=["install"])
    add_p.add_argument("plugin_name", help="Plugin name to install")
    rm_p = plugin_sub.add_parser("remove", aliases=["rm"])
    rm_p.add_argument("plugin_name", help="Plugin name to remove")
    plugin_sub.add_parser("list", aliases=["ls"])
    _search_p = plugin_sub.add_parser("search")
    _search_p.add_argument("query", nargs="?", default="", help="Search query")  # FIX #299
    plugin_parser.set_defaults(func=command_plugin)

    # ── NPM Package Management (v0.8.1) ──────────────────────────────────────
    install_parser = subparsers.add_parser("install", help="Install npm packages (like Next.js)")
    install_parser.add_argument("packages", nargs="*", help="Package names (e.g. react react-dom@18.2.0)")
    install_parser.add_argument("--dev", action="store_true", help="Save as devDependency")
    install_parser.add_argument("--exact", action="store_true", help="Save exact version (no ^)")
    install_parser.set_defaults(func=command_install)

    add_parser_cmd = subparsers.add_parser("add", help="Add npm packages (alias for install)")
    add_parser_cmd.add_argument("packages", nargs="*", help="Package names")
    add_parser_cmd.add_argument("--dev", action="store_true", help="Save as devDependency")
    add_parser_cmd.add_argument("--exact", action="store_true", help="Save exact version")
    add_parser_cmd.set_defaults(func=command_add)

    remove_parser = subparsers.add_parser("remove", aliases=["rm"], help="Remove npm packages")
    remove_parser.add_argument("packages", nargs="+", help="Package names to remove")
    remove_parser.set_defaults(func=command_remove)

    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List installed npm packages")
    list_parser.add_argument("--detailed", action="store_true", help="Show installed versions")
    list_parser.set_defaults(func=command_list)

    serve_parser = subparsers.add_parser("serve", help="Run the production server (SSR + API routes)")
    serve_parser.add_argument("project_root", nargs="?", default=None, help="Project root directory")
    serve_parser.add_argument("--host", default=None, help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8000, auto-increments if busy)")
    add_output_dir_arg(serve_parser, "Static output dir (optional)")
    serve_parser.add_argument("--no-build", action="store_true", help="Skip the build step and serve directly")
    add_no_minify_arg(serve_parser, "Disable HTML/CSS minification in the pre-build step")
    serve_parser.add_argument("--fail-on-warnings", action="store_true", help="Do not start server if build emits warnings")
    serve_parser.set_defaults(func=command_serve)


    # ── infrastructure command ──────────────────────────────────────
    infra_parser = subparsers.add_parser("infrastructure", aliases=["infra"], help="Generate Terraform IaC for AWS")
    infra_parser.add_argument("--provider", default="aws", help="Cloud provider (aws, gcp, azure)")
    infra_parser.add_argument("--region", default="ap-south-1", help="AWS region")
    infra_parser.add_argument("--out-dir", default="infrastructure", help="Output directory")
    infra_parser.set_defaults(func=command_infrastructure)

    # ── health command ──────────────────────────────────────────────
    health_parser = subparsers.add_parser("health", help="Run health checks on the project")
    health_parser.set_defaults(func=command_health)

    # ── routes command ───────────────────────────────────────────────
    routes_parser = subparsers.add_parser("routes", help="List all routes in the project")
    routes_parser.set_defaults(func=command_routes)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "version", False):
        from . import __version__
        print(f"tw-framework v{__version__}")
        return

    if not getattr(args, "command", None):
        parser.print_help()
        raise SystemExit(1)

    try:
        result = args.func(args)
    except KeyboardInterrupt:
        log("\n✖ Interrupted by user", level="error")
        raise SystemExit(130)
    except SystemExit:
        raise
    except FileNotFoundError as err:
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
            raise
        log(f"✖ File not found: {err.filename}", level="error")
        raise SystemExit(1)
    except PermissionError as err:
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
            raise
        log(f"✖ Permission denied: {err.filename}", level="error")
        raise SystemExit(1)
    except Exception as err:
        if getattr(args, "debug", False):
            import traceback
            traceback.print_exc()
            raise
        # Show short clean error by default
        err_msg = str(err).split("\n")[0][:200]
        log(f"✖ {err_msg}", level="error")
        log("  Run with --debug for full details.", level="warning")
        raise SystemExit(1)
    if isinstance(result, int):
        raise SystemExit(result)


if __name__ == "__main__":
    main()

import argparse
import json
import os
import re
import threading
import time
import webbrowser

from . import framework


CLI_NAME = "tw"
GLOBAL_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".tw-framework")
GLOBAL_CONFIG_FILE = os.path.join(GLOBAL_CONFIG_DIR, "config.json")


STARTER_FILES = {
    "tw.config": """name: My TW Site
site_url: http://localhost:3000
description: A TW starter project
theme: system
pretty_urls: true
search: true
""",
    ".env": """SITE_NAME=My TW Site
API_TOKEN=change-me
""",
    "middleware.tw": '''use {
    match "/dashboard/**"
    auth "session" "/"
    header "X-Frame-Options" "DENY"
}
''',
    "[home]/index.tw": '''page {
    title "My TW Site"
    layout "main"
    render static
}

let siteName = "My TW Site"
let heroTitle = "Build websites in TW"
let heroText = "Write .tw, .tss and .ts. Run dev. Ship fast."

head {
    seo {
        description "A TW starter project"
        og_title "{siteName}"
        og_description "{heroText}"
    }
}

BODY {
    import "Hero"
    import "ThemeToggle"

    ThemeToggle {}
    Hero {
        title "{heroTitle}"
        text "{heroText}"
        ctaText "Open About Page"
        ctaLink "/about"
    }
}
''',
    "[home]/pages/about.tw": '''page {
    title "About"
    layout "main"
    render static
}

BODY {
    div {
        class "page"
        h1 "About this project"
        p "This page is written in TW."
        a {
            href "/"
            text "Back home"
        }
    }
}
''',
    "[home]/pages/contact.tw": '''page {
    title "Contact"
    layout "main"
    render static
}

BODY {
    import "ContactForm"
    ContactForm {
        action "/api/contact"
    }
}
''',
    "[home]/pages/search.tw": '''page {
    title "Search"
    layout "main"
    render static
}

BODY {
    div {
        class "page"
        h1 "Search"
        input {
            id "tw-search"
            type "search"
            placeholder "Type to search..."
            input "__twSearchInput"
        }
        div { id "tw-search-results" }
        script {
          window.__twSearchInput = async function(event) {
            try {
              var q = (event && event.target && event.target.value) ? event.target.value : '';
              var results = await window.__twSearch(q, {limit: 15});
              var root = document.getElementById('tw-search-results');
              if (!root) return;
              if (!q) { root.innerHTML = ''; return; }
              root.innerHTML = results.map(function(r){
                var href = r.route || '/';
                return '<div style=\"padding:10px 0;border-bottom:1px solid var(--tw-border)\">' +
                  '<a href=\"' + href + '\" style=\"color:inherit;text-decoration:none;font-weight:700\">' +
                  (r.title || href) + '</a>' +
                  '<div style=\"opacity:.8;font-size:14px\">' + (r.excerpt || '') + '</div>' +
                '</div>';
              }).join('');
            } catch (e) {}
          };
        }
    }
}
''',
    "[home]/pages/dashboard.tw": '''page {
    title "Dashboard"
    layout "main"
    render server
    revalidate 60
}

BODY {
    div {
        class "page"
        h1 "Private dashboard"
        p "Protected by middleware.tw cookie auth."
    }
}
''',
    "[home]/api/users.tw": '''GET {
    json "[{\\"id\\":1,\\"name\\":\\"Ada\\"}]"
}

POST {
    status 201
    json "{\\"ok\\":true,\\"source\\":\\"{body.raw}\\"}"
}
''',
    "[home]/api/contact.tw": '''POST {
    // Dev server me JSON response milega. Production me isko runtime host chahiye.
    status 200
    json "{\\"ok\\":true,\\"message\\":\\"Thanks!\\",\\"received\\":{body}}"
}
''',
    "[home]/components/Hero.tw": '''section {
    class "hero"
    h1 "{title}"
    p "{text}"
    a {
        href "{ctaLink}"
        class "button"
        text "{ctaText}"
    }
}
''',
    "[home]/components/ThemeToggle.tw": '''button {
    class "theme-toggle"
    click "__twToggleTheme"
    aria-label "Toggle theme"
    text "Toggle theme"
}
''',
    "[home]/components/ContactForm.tw": '''form {
    class "contact-form"
    method "post"
    action "{action}"
    input {
        type "text"
        name "name"
        placeholder "Your name"
        required true
    }
    input {
        type "email"
        name "email"
        placeholder "Email"
        required true
    }
    textarea {
        name "message"
        placeholder "Message"
        rows 5
        required true
    }
    button {
        type "submit"
        class "button"
        text "Send"
    }
}
''',
    "[home]/layouts/main.tw": """<!DOCTYPE html>
<html>
<head>
{head}
{styles}
</head>
<body>
{slot}
{scripts}
</body>
</html>
""",
    "[home]/style.tss": '''body {
    margin 0
    font-family system-ui, sans-serif
    background var(--tw-bg)
    color var(--tw-fg)
}

:root[data-theme="dark"] {
    --tw-bg #0f172a
    --tw-fg #e2e8f0
    --tw-card rgba(15, 23, 42, 0.7)
    --tw-border rgba(148, 163, 184, 0.25)
}

:root[data-theme="light"] {
    --tw-bg #ffffff
    --tw-fg #0b1220
    --tw-card rgba(255, 255, 255, 0.8)
    --tw-border rgba(2, 6, 23, 0.12)
}

.hero {
    min-height 100
    padding 64
    display flex
    flex-direction column
    gap 16
    justify-content center
    align-items flex-start
}

.button {
    display inline-block
    margin-top 12
    padding 12 18
    border-radius 12
    background #38bdf8
    color #082f49
    text-decoration none
    font-weight 700
}

.theme-toggle {
    position fixed
    top 16
    right 16
    padding 10 12
    border-radius 12
    border 1 solid var(--tw-border)
    background var(--tw-card)
    color var(--tw-fg)
    cursor pointer
}

.contact-form {
    display flex
    flex-direction column
    gap 12
    padding 48
    max-width 680
}

.contact-form input {
    padding 12 12
    border-radius 12
    border 1 solid var(--tw-border)
    background var(--tw-card)
    color var(--tw-fg)
}

.contact-form textarea {
    padding 12 12
    border-radius 12
    border 1 solid var(--tw-border)
    background var(--tw-card)
    color var(--tw-fg)
}

.page {
    padding 48
}
''',
    ".gitignore": """.tw/
dist/
__pycache__/
*.pyc
""",
}


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_text(path, content):
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def slugify_package_name(name):
    normalized = re.sub(r"[^a-z0-9-_]+", "-", name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "tw-site"


def build_package_json(project_name):
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
        },
        indent=2,
    ) + "\n"


def build_vercel_json():
    return json.dumps(
        {
            "buildCommand": "tw build",
            "outputDirectory": "dist",
        },
        indent=2,
    ) + "\n"


def load_global_config():
    if not os.path.exists(GLOBAL_CONFIG_FILE):
        return {}
    try:
        with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_global_config(config):
    ensure_dir(GLOBAL_CONFIG_DIR)
    with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)


def find_project_root(start_dir=None):
    current = os.path.abspath(start_dir or os.getcwd())
    while True:
        config_path = os.path.join(current, "tw.config")
        home_dir = os.path.join(current, "[home]")
        if os.path.exists(config_path) and os.path.isdir(home_dir):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise RuntimeError("TW project root nahi mila. `tw create <name>` chalao ya project folder me jao.")


def create_project(project_name, parent_dir=None):
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
        os.path.join(root, "app"),
        os.path.join(root, "pages"),
        os.path.join(root, "components"),
        os.path.join(root, "layouts"),
        os.path.join(root, "api"),
        os.path.join(root, "middleware"),
        os.path.join(root, "dist"),
        os.path.join(root, "public"),
        os.path.join(root, "[home]", "assets", "images"),
        os.path.join(root, "[home]", "assets", "js"),
        os.path.join(root, "[home]", "assets", "css"),
        os.path.join(root, "[home]", "assets", "fonts"),
        os.path.join(root, "[home]", "api"),
        os.path.join(root, "[home]", "hooks"),
        os.path.join(root, "[home]", "stores"),
        os.path.join(root, "[home]", "middleware"),
        os.path.join(root, "[home]", "plugins"),
        os.path.join(root, "[home]", "types"),
    ]:
        ensure_dir(extra_dir)

    print(f"✔ Project created: {root}")
    print(f"Next steps:")
    print(f"  cd {project_name}")
    print(f"  {CLI_NAME} dev")


def open_browser_later(url):
    timer = threading.Timer(1.0, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def resolve_output_dir(project_root):
    return os.path.join(project_root, "dist")


def command_create(args):
    create_project(args.name, args.directory)


def command_dev(args):
    project_root = find_project_root(args.project_root)
    host = args.host
    port = args.port
    url = f"http://{host}:{port}"
    if not args.no_open:
        open_browser_later(url)
    try:
        framework.run_dev_server(project_root, host, port)
    except Exception as err:
        print(f"✖ Dev server start failed: {err}")
        return 1
    return 0


def command_build(args):
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    if args.clean:
        framework.clean_project_outputs(project_root)

    def run_once(force_build=False):
        summary = framework.build_hidden_site(
            project_root=project_root,
            output_dir=output_dir,
            force=args.force or force_build,
            workers=args.workers,
            minify=(args.prod or not args.dev) and not args.no_minify,
        )
        if summary.errors:
            print(f"✖ Build finished with {summary.errors} error(s)")
            return summary, 1
        print("✔ Build completed")
        print(f"✔ Optimized {summary.built} page(s)")
        if summary.skipped:
            print(f"✔ Reused cache for {summary.skipped} page(s)")
        if args.analyze:
            route_manifest = os.path.join(output_dir, "_tw", "route-manifest.json")
            api_manifest = os.path.join(output_dir, "_tw", "api-manifest.json")
            print(f"✔ Route analysis: {route_manifest}")
            print(f"✔ API analysis: {api_manifest}")
        print("✔ Ready for deployment")
        return summary, 0

    _, code = run_once()
    if code or not args.watch:
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
    print("👀 Build watch mode active")
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
                print("↻ Change detected, rebuilding...")
                _, code = run_once(force_build=True)
                if code:
                    print("⚠️  Watching continue karega, error fix karke save karo.")
    except KeyboardInterrupt:
        print("\nWatch mode stopped")
    return 0


def command_export(args):
    project_root = find_project_root(args.project_root)
    summary = framework.build_hidden_site(
        project_root=project_root,
        output_dir=args.out_dir or resolve_output_dir(project_root),
        force=True,
        workers=args.workers,
        minify=not args.no_minify,
    )

    if summary.errors:
        print(f"✖ Export finished with {summary.errors} error(s)")
        return 1

    print("✔ Static export completed")
    print(f"✔ Output ready in {summary.output_dir}")
    return 0


def command_preview(args):
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    if not args.no_build:
        result = command_export(
            argparse.Namespace(
                project_root=project_root,
                out_dir=output_dir,
                workers=args.workers,
                no_minify=args.no_minify,
            )
        )
        if result:
            return result

    url = f"http://{args.host}:{args.port}"
    if not args.no_open:
        open_browser_later(url)
    framework.run_preview_server(output_dir=output_dir, host=args.host, port=args.port)


def command_clean(args):
    project_root = find_project_root(args.project_root)
    framework.clean_project_outputs(project_root)
    print("✔ dist/ aur .tw/ clean kar diye gaye")
    return 0


def command_doctor(args):
    project_root = find_project_root(args.project_root)
    checks = framework.doctor_project(project_root)
    failed = 0
    for check in checks:
        status = "OK" if check["ok"] else "WARN"
        print(f"[{status}] {check['name']}: {check['detail']}")
        if not check["ok"] and check["name"] in {"tw.config", "[home]", "Route discovery"}:
            failed += 1
    return 1 if failed else 0


def command_info(args):
    project_root = find_project_root(args.project_root)
    info = framework.inspect_project(project_root)
    print(f"Project root: {info['project_root']}")
    print(f"Source root: {info['source_root']}")
    print(f"Output dir: {info['output_dir']}")
    print(f"Hidden dir: {info['hidden_dir']}")
    print(f"Pages: {info['page_count']}")
    print(f"Static routes: {info['static_routes']}")
    print(f"Dynamic routes: {info['dynamic_routes']}")
    print(f"Components: {info['component_count']}")
    print(f"Custom 404: {'yes' if info['has_404'] else 'no'}")
    print(f"Custom 500: {'yes' if info['has_500'] else 'no'}")
    return 0


def apply_deploy_config(config, provider):
    if provider == "vercel" and config.get("vercel_token"):
        os.environ["VERCEL_TOKEN"] = config["vercel_token"]


def resolve_provider(args, config):
    if args.vercel:
        return "vercel"
    if args.cloudflare:
        return "cloudflare"
    if args.provider:
        return args.provider
    return config.get("default_provider", "local")


def command_login(args):
    config = load_global_config()
    if args.provider:
        config["default_provider"] = args.provider
    if args.vercel_token:
        config["vercel_token"] = args.vercel_token
    save_global_config(config)
    print("✔ TW deploy config saved")
    if config.get("default_provider"):
        print(f"✔ Default provider: {config['default_provider']}")


def command_deploy(args):
    project_root = find_project_root(args.project_root)
    config = load_global_config()
    provider = resolve_provider(args, config)
    apply_deploy_config(config, provider)

    framework.run_deploy(
        project_root=project_root,
        output_dir=args.out_dir or resolve_output_dir(project_root),
        provider=provider,
        production=args.prod or provider in {"vercel", "cloudflare", "netlify", "docker"},
    )
    print("✔ Deploy completed")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="TW framework CLI")
    parser.add_argument("--project-root", help="Manual project root override")

    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="New TW project create karo")
    create_parser.add_argument("name", help="Project folder name")
    create_parser.add_argument("--directory", help="Parent directory jahan project create hoga")
    create_parser.set_defaults(func=command_create)

    dev_parser = subparsers.add_parser("dev", help="Local dev server chalao")
    dev_parser.add_argument("--host", default=framework.DEFAULT_DEV_HOST)
    dev_parser.add_argument("--port", type=int, default=framework.DEFAULT_DEV_PORT)
    dev_parser.add_argument("--no-open", action="store_true", help="Browser auto-open disable karo")
    dev_parser.set_defaults(func=command_dev)

    build_parser = subparsers.add_parser("build", help="Production build generate karo")
    build_parser.add_argument("--out-dir", help="Internal output directory")
    build_parser.add_argument("--force", action="store_true")
    build_parser.add_argument("--workers", type=int, default=framework.compiler.DEFAULT_WORKERS)
    build_parser.add_argument("--dev", action="store_true", help="Development-style non-minified build")
    build_parser.add_argument("--prod", action="store_true", help="Production optimized build")
    build_parser.add_argument("--watch", action="store_true", help="File changes pe rebuild karo")
    build_parser.add_argument("--analyze", action="store_true", help="Route/API analysis files generate hone ke baad paths dikhao")
    build_parser.add_argument("--clean", action="store_true", help="Build se pehle dist aur cache clean karo")
    build_parser.add_argument("--no-minify", action="store_true", help="HTML/CSS minify disable karo")
    build_parser.set_defaults(func=command_build)

    export_parser = subparsers.add_parser("export", help="Static export generate karo")
    export_parser.add_argument("--out-dir", help="Export output directory")
    export_parser.add_argument("--workers", type=int, default=framework.compiler.DEFAULT_WORKERS)
    export_parser.add_argument("--no-minify", action="store_true", help="HTML/CSS minify disable karo")
    export_parser.set_defaults(func=command_export)

    preview_parser = subparsers.add_parser("preview", help="Built dist output preview karo")
    preview_parser.add_argument("--out-dir", help="Preview output directory")
    preview_parser.add_argument("--host", default=framework.DEFAULT_DEV_HOST)
    preview_parser.add_argument("--port", type=int, default=framework.DEFAULT_PREVIEW_PORT)
    preview_parser.add_argument("--workers", type=int, default=framework.compiler.DEFAULT_WORKERS)
    preview_parser.add_argument("--no-build", action="store_true", help="Existing dist ko bina rebuild serve karo")
    preview_parser.add_argument("--no-minify", action="store_true", help="Preview se pehle build me minify disable karo")
    preview_parser.add_argument("--no-open", action="store_true", help="Browser auto-open disable karo")
    preview_parser.set_defaults(func=command_preview)

    clean_parser = subparsers.add_parser("clean", help="dist aur hidden cache clean karo")
    clean_parser.set_defaults(func=command_clean)

    doctor_parser = subparsers.add_parser("doctor", help="Project health checks chalao")
    doctor_parser.set_defaults(func=command_doctor)

    info_parser = subparsers.add_parser("info", help="Project summary dikhao")
    info_parser.set_defaults(func=command_info)

    login_parser = subparsers.add_parser("login", help="Deploy provider config save karo")
    login_parser.add_argument("--provider", choices=["local", "vercel", "cloudflare", "netlify", "github-pages", "docker"])
    login_parser.add_argument("--vercel-token", help="Vercel token save karo")
    login_parser.set_defaults(func=command_login)

    deploy_parser = subparsers.add_parser("deploy", help="Current project deploy karo")
    deploy_parser.add_argument("--out-dir", help="Internal output directory")
    deploy_parser.add_argument("--provider", choices=["local", "vercel", "cloudflare", "netlify", "github-pages", "docker"])
    deploy_parser.add_argument("--vercel", action="store_true", help="Vercel provider use karo")
    deploy_parser.add_argument("--cloudflare", action="store_true", help="Cloudflare provider use karo")
    deploy_parser.add_argument("--prod", action="store_true", help="Production deploy flag")
    deploy_parser.set_defaults(func=command_deploy)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, int):
        raise SystemExit(result)


if __name__ == "__main__":
    main()

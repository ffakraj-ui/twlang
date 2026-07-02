import argparse
import json
import os
import re
import sys
import threading
import time
import webbrowser

from . import compiler, framework
from .common import log
from .lexer import tokenize_file
from .lowering import lower_program
from .parser import parse_file
from .semantic import analyze_program


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
modular_pipeline: true
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
    "[home]/pages/counter.tw": '''page {
    title "Counter Demo"
    layout "main"
    render static
}

state {
    count 0
    name "World"
}

BODY {
    div {
        class "page"
        h1 "TW Reactive Counter"

        p { tw-text "count" }

        button {
            on:click "__tw.set(\'count\', __tw.get(\'count\') + 1)"
            class "button"
            text "+"
        }
        button {
            on:click "__tw.set(\'count\', __tw.get(\'count\') - 1)"
            class "button"
            text "-"
        }

        hr {}
        p "Your name:"
        input {
            type "text"
            bind:value "name"
            placeholder "Type here..."
        }
        p { tw-text "\'Hello, \' + name + \'!\'"}
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
    "[home]/api/users/route.twm": '''fn get(request) {
    return {
        status: 200,
        json: [{ id: 1, name: "Ada" }]
    };
}

fn post(request) {
    return {
        status: 201,
        json: { ok: true, source: request.body || {} }
    };
}
''',
    "[home]/api/contact/route.twm": '''fn post(request) {
    return {
        status: 200,
        json: { ok: true, message: "Thanks!", received: request.body || {} }
    };
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
.tw-cache/
dist/
__pycache__/
*.pyc
""",
}


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def _restrict_global_config_permissions():
    try:
        os.chmod(GLOBAL_CONFIG_DIR, 0o700)
    except Exception:
        pass
    try:
        os.chmod(GLOBAL_CONFIG_FILE, 0o600)
    except Exception:
        pass


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
            "engines": {
                "node": ">=18",
            },
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
    except Exception as err:
        # Don't silently wipe config if the file is corrupt.
        log(f"⚠️ Failed to read global config (ignoring): {GLOBAL_CONFIG_FILE} ({err})", level="warning")
        return {}


def save_global_config(config):
    ensure_dir(GLOBAL_CONFIG_DIR)
    _restrict_global_config_permissions()
    # Atomic write (temp-file + rename) to avoid corrupting config on crash/kill.
    tmp_path = GLOBAL_CONFIG_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
    os.replace(tmp_path, GLOBAL_CONFIG_FILE)
    _restrict_global_config_permissions()


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
    raise RuntimeError(
        "TW project root not found. Run `tw create <name>` or `cd` into a TW project folder."
    )


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

    log(f"✔ Project created: {root}")
    log("Next steps:")
    log(f"  cd {project_name}")
    log(f"  {CLI_NAME} dev")


def open_browser_later(url):
    timer = threading.Timer(1.0, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def resolve_output_dir(project_root):
    return os.path.join(project_root, "dist")


def configure_project_for_file(file_path):
    abs_path = os.path.abspath(file_path)
    try:
        project_root = find_project_root(os.path.dirname(abs_path))
    except Exception:
        return None
    framework.configure_compiler_paths(project_root)
    return project_root


def _guess_route_for_file(abs_path):
    for page_info in compiler.discover_pages():
        if os.path.abspath(page_info["path"]) == abs_path:
            return compiler.route_path_from_page_info(page_info)
    return "/"


def _diagnostics_have_errors(items):
    return any(item.get("severity") == "error" for item in items or [])


def _serialize_token(token):
    if hasattr(token, "to_dict"):
        return token.to_dict()
    return {
        "type": getattr(token, "type", ""),
        "value": getattr(token, "value", ""),
        "line": getattr(token, "line", 0),
        "col": getattr(token, "col", 0),
    }


def _json_safe(value):
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


def _diagnostic_summary(items):
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


def _compile_file_artifacts(file_path, *, include_css=False, capture_errors=False):
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
        log(f"✖ Dev server start failed: {err}", level="error")
        return 1
    return 0


def command_build(args):
    project_root = find_project_root(args.project_root)
    output_dir = args.out_dir or resolve_output_dir(project_root)
    if args.clean:
        framework.clean_project_outputs(project_root)
    strict = bool(getattr(args, "strict", False))
    fail_on_warnings = bool(
        strict or getattr(args, "fail_on_warnings", False) or getattr(args, "prod", False)
    )

    def run_once(force_build=False):
        summary = framework.build_hidden_site(
            project_root=project_root,
            output_dir=output_dir,
            force=args.force or force_build,
            workers=args.workers,
            minify=(args.prod or not args.dev) and not args.no_minify,
            strict=strict,
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
    log("✔ dist/ aur .tw/ clean kar diye gaye")
    return 0


def command_doctor(args):
    project_root = find_project_root(args.project_root)
    checks = framework.doctor_project(project_root)
    # Extra CLI-level checks (global deploy config)
    config = load_global_config()
    if os.path.exists(GLOBAL_CONFIG_FILE):
        checks.append({"name": "Global deploy config", "ok": True, "detail": GLOBAL_CONFIG_FILE})
    else:
        checks.append({"name": "Global deploy config", "ok": False, "detail": f"Missing: {GLOBAL_CONFIG_FILE} (run `tw login` to create it)"})
    # Provider token hints (best-effort)
    if config.get("vercel_token") or os.environ.get("VERCEL_TOKEN"):
        checks.append({"name": "Vercel token", "ok": True, "detail": "Token available"})
    else:
        checks.append({"name": "Vercel token", "ok": False, "detail": "Missing Vercel token (run `tw login --vercel-token ...` or set VERCEL_TOKEN)"})
    failed = 0
    for check in checks:
        status = "OK" if check["ok"] else "WARN"
        log(f"[{status}] {check['name']}: {check['detail']}", level="warning" if status == "WARN" else "info")
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
    print(f"Modular pipeline: {'yes' if info['modular_pipeline'] else 'no'}")
    return 0


def _write_or_print_output(output_path, payload):
    if output_path:
        write_text(output_path, payload)
        log(f"✔ Output saved: {output_path}")
        return
    print(payload)


def command_ast(args):
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


def command_ir(args):
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


def command_run_file(args):
    artifacts = _compile_file_artifacts(args.file, include_css=True, capture_errors=args.diagnostics)
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


def command_tokens(args):
    configure_project_for_file(args.file)
    payload = {
        "tokens": [_serialize_token(token) for token in tokenize_file(os.path.abspath(args.file))]
    }
    _write_or_print_output(args.out, json.dumps(_json_safe(payload), indent=2, ensure_ascii=False))
    return 0


def command_check(args):
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


def apply_deploy_config(config, provider):
    """Returns a cleanup callable to restore env changes."""
    cleanup = lambda: None
    if provider == "vercel" and config.get("vercel_token"):
        old_value = os.environ.get("VERCEL_TOKEN")
        os.environ["VERCEL_TOKEN"] = config["vercel_token"]

        def cleanup():
            if old_value is None:
                os.environ.pop("VERCEL_TOKEN", None)
            else:
                os.environ["VERCEL_TOKEN"] = old_value

    return cleanup


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
    log("✔ TW deploy config saved")
    if config.get("default_provider"):
        log(f"✔ Default provider: {config['default_provider']}")


def command_deploy(args):
    project_root = find_project_root(args.project_root)
    config = load_global_config()
    provider = resolve_provider(args, config)
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


def command_serve(args):
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


def build_parser():
    parser = argparse.ArgumentParser(description="TW framework CLI")
    parser.add_argument("--project-root", help="Manual project root override")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_output_dir_arg(subparser, help_text):
        subparser.add_argument("--out-dir", help=help_text)

    def add_workers_arg(subparser):
        subparser.add_argument("--workers", type=int, default=framework.compiler.DEFAULT_WORKERS)

    def add_host_port_args(subparser, *, host_default, port_default, allow_no_open=False):
        subparser.add_argument("--host", default=host_default)
        subparser.add_argument("--port", type=int, default=port_default)
        if allow_no_open:
            subparser.add_argument("--no-open", action="store_true", help="Disable auto-opening the browser")

    def add_no_minify_arg(subparser, help_text):
        subparser.add_argument("--no-minify", action="store_true", help=help_text)

    create_parser = subparsers.add_parser("create", help="Create a new TW project")
    create_parser.add_argument("name", help="Project folder name")
    create_parser.add_argument("--directory", help="Parent directory where the project will be created")
    create_parser.set_defaults(func=command_create)

    dev_parser = subparsers.add_parser("dev", help="Run the local dev server")
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

    doctor_parser = subparsers.add_parser("doctor", help="Run project health checks")
    doctor_parser.set_defaults(func=command_doctor)

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

    serve_parser = subparsers.add_parser("serve", help="Run the production server (SSR + API routes)")
    serve_parser.add_argument("--host", default=None, help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=None, help="Bind port (default: 8000)")
    add_output_dir_arg(serve_parser, "Static output dir (optional)")
    serve_parser.add_argument("--no-build", action="store_true", help="Skip the build step and serve directly")
    add_no_minify_arg(serve_parser, "Disable HTML/CSS minification in the pre-build step")
    serve_parser.add_argument("--fail-on-warnings", action="store_true", help="Do not start server if build emits warnings")
    serve_parser.set_defaults(func=command_serve)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    if isinstance(result, int):
        raise SystemExit(result)


if __name__ == "__main__":
    main()

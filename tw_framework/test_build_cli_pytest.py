from __future__ import annotations

import http.server
import json
import os
import shutil
import socketserver
import stat
import sys
import threading
from pathlib import Path

import pytest

from tw_framework import cli, compiler, framework, server
from tw_framework.plugin_runtime import ExtensionManager
from tw_framework.reactivity import parse_state_block


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_project(tmp_path: Path, *, modular: bool = True, pretty_urls: bool = True) -> Path:
    root = tmp_path / "proj"
    home = root / "[home]"
    (home / "pages").mkdir(parents=True, exist_ok=True)
    (home / "components").mkdir(parents=True, exist_ok=True)
    (home / "layouts").mkdir(parents=True, exist_ok=True)

    _write(
        root / "tw.config",
        "\n".join(
            [
                "name: Test Site",
                f"pretty_urls: {'true' if pretty_urls else 'false'}",
                f"modular_pipeline: {'true' if modular else 'false'}",
                "search: false",
                "",
            ]
        ),
    )
    _write(root / "package.json", '{"name":"test","private":true}\n')
    _write(root / "vercel.json", "{}\n")

    _write(
        home / "layouts" / "main.tw",
        "<!doctype html><html><head>{head}{styles}</head><body>{slot}{scripts}</body></html>",
    )
    _write(
        home / "index.tw",
        """
page {
  title "Home"
  layout "main"
  render static
}
BODY { div "Home" }
""".lstrip(),
    )
    return root


def test_static_route_build_pretty_urls(tmp_path: Path):
    root = make_project(tmp_path, pretty_urls=True)
    home = root / "[home]"
    _write(
        home / "pages" / "about.tw",
        """
page { title "About" layout "main" render static }
BODY { h1 "About" }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    assert (root / "dist" / "about" / "index.html").exists()


def test_dynamic_route_single_build(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "pages" / "[id].tw",
        """
page { title "Item" layout "main" render static }
BODY { h1 "{id}" }
""".lstrip(),
    )
    _write(home / "pages" / "[id].json", json.dumps([{"id": "a"}, {"id": "b"}]))
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    assert (root / "dist" / "a" / "index.html").exists()
    assert (root / "dist" / "b" / "index.html").exists()


def test_dynamic_route_catch_all_build(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "pages" / "[...x].tw",
        """
page { title "Catch" layout "main" render static }
BODY { p "{x}" }
""".lstrip(),
    )
    _write(home / "pages" / "[...x].json", json.dumps([{"x": "a/b"}]))
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    assert (root / "dist" / "a" / "b" / "index.html").exists()


def test_dynamic_route_optional_catch_all_build(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "pages" / "[[...x]].tw",
        """
page { title "Opt" layout "main" render static }
BODY { p "ok" }
""".lstrip(),
    )
    _write(home / "pages" / "[[...x]].json", json.dumps([{"x": None}]))
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    # optional catch-all can map to `/` (no segments) for null/empty input
    assert (root / "dist" / "index.html").exists()


def test_imported_component_supports_unicode_text(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "components" / "Profile.tw",
        """
div {
  p "Python • JavaScript • HTML • CSS"
  p "Hello — “world” 🚀"
}
""".lstrip(),
    )
    _write(
        home / "index.tw",
        """
page { title "Home" layout "main" render static }
BODY {
  import "Profile"
  Profile {}
}
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "index.html").read_text(encoding="utf-8")
    assert "Python • JavaScript • HTML • CSS" in html
    assert "Hello — “world” 🚀" in html


def test_imported_component_repairs_common_mojibake(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "components" / "Profile.tw",
        """
div {
  p "Python â€¢ JavaScript â€” HTML"
}
""".lstrip(),
    )
    _write(
        home / "index.tw",
        """
page { title "Home" layout "main" render static }
BODY {
  import "Profile"
  Profile {}
}
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "index.html").read_text(encoding="utf-8")
    assert "Python • JavaScript — HTML" in html


def test_component_block_accepts_semicolon_separators(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "components" / "Examples.tw",
        """
section {
  div {
    class "example-grid"
    div { h3 "Landing Page"; p "Modern UI page" }
    div { h3 "Dashboard"; p "Admin panel UI" }
  }
}
""".lstrip(),
    )
    _write(
        home / "index.tw",
        """
page { title "Home" layout "main" render static }
BODY {
  import "Examples"
  Examples {}
}
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "index.html").read_text(encoding="utf-8")
    assert "Landing Page" in html
    assert "Modern UI page" in html
    assert "Dashboard" in html
    assert "Admin panel UI" in html


def test_circular_component_import_detection(tmp_path: Path):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    _write(root / "[home]" / "components" / "A.tw", 'div { import "B" p "A" }')
    _write(root / "[home]" / "components" / "B.tw", 'div { import "A" p "B" }')
    with pytest.raises(compiler.CompilerError) as exc:
        compiler.collect_component_dependencies("A")
    assert "Circular component import" in str(exc.value)


def test_component_not_found_error(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(
        home / "pages" / "broken.tw",
        """
page { title "Broken" layout "main" render static }
BODY { import "Nope" }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors >= 1


def test_component_level_load_directive(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "styles" / "extra.tss", ".x { color red }")
    _write(
        home / "components" / "Card.tw",
        """
load @./styles/extra.tss
div { class "x" text "Card" }
""".lstrip(),
    )
    _write(
        home / "pages" / "card.tw",
        """
page { title "Card" layout "main" render static }
BODY { import "Card" Card {} }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "card" / "index.html").read_text("utf-8")
    assert "color: red" in html


def test_resolve_source_path_supports_project_and_home_aliases(tmp_path: Path):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    base_dir = str(root / "[home]" / "pages")
    assert compiler.resolve_source_path("page.tss", base_dir) == str(root / "[home]" / "pages" / "page.tss")
    assert compiler.resolve_source_path("@lib/mlkraj.tw", base_dir) == str(root / "lib" / "mlkraj.tw")
    assert compiler.resolve_source_path("@./lib/mlkraj.tw", base_dir) == str(root / "[home]" / "lib" / "mlkraj.tw")
    assert compiler.resolve_source_path("@../style/site.tss", base_dir) == str(root / "[home]" / "style" / "site.tss")


def test_quoted_load_uses_same_folder(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    (home / "pages" / "apps").mkdir(parents=True, exist_ok=True)
    _write(home / "pages" / "apps" / "page.tss", ".apps-page { color blue }")
    _write(
        home / "pages" / "apps" / "page.tw",
        """
page { title "Apps" layout "main" render static }
load "page.tss"
BODY { div { class "apps-page" text "Apps" } }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "apps" / "page" / "index.html").read_text("utf-8")
    assert "color: blue" in html


def test_layout_level_load_directive(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "components" / "Header.tw", 'header { h1 "Header" }')
    _write(
        home / "layouts" / "main.tw",
        "<!doctype html><html><head>{head}{styles}</head><body>\n"
        "load @./components/Header.tw\n"
        "{slot}{scripts}\n"
        "</body></html>",
    )
    _write(
        home / "pages" / "x.tw",
        """
page {
  title "X"
  layout "main"
  render static
}
BODY { p "ok" }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "x" / "index.html").read_text("utf-8")
    assert "<header>" in html and "Header" in html


def test_layout_chaining_multiple_layouts(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "layouts" / "outer.tw", "<html><body><main>OUTER{slot}</main></body></html>")
    _write(home / "layouts" / "inner.tw", "<section>INNER{slot}</section>")
    _write(
        home / "pages" / "chain.tw",
        """
page {
  title "Chain"
  layout "outer > inner"
  render static
}
BODY { p "Hello" }
""".lstrip(),
    )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0
    html = (root / "dist" / "chain" / "index.html").read_text("utf-8")
    assert "OUTER" in html and "INNER" in html and "Hello" in html


def test_undefined_symbol_diagnostics_edge_cases(tmp_path: Path):
    root = make_project(tmp_path)
    tw = root / "[home]" / "pages" / "warn.tw"
    _write(
        tw,
        """
page { title "Warn" layout "main" render static }
let ok = 1
BODY {
  if missingCond { div "x" }
  for item in missingList { div { class "{missingAttr}" text "{item}" } }
}
""".lstrip(),
    )
    artifacts = compiler.compile_file_pipeline(str(tw), capture_errors=True)
    warnings = [d for d in artifacts.diagnostics if d.get("severity") == "warning"]
    codes = {d.get("code") for d in warnings}
    assert "TW2001" in codes


def test_cli_build_exit_code_zero_clean(tmp_path: Path):
    root = make_project(tmp_path)
    args = type(
        "Args",
        (),
        dict(
            project_root=str(root),
            out_dir=str(root / "dist"),
            force=False,
            workers=1,
            dev=False,
            prod=False,
            watch=False,
            analyze=False,
            clean=False,
            no_minify=True,
            fail_on_warnings=False,
            strict=False,
        ),
    )()
    assert cli.command_build(args) == 0


def test_cli_build_prod_fails_on_warnings(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "pages" / "warn.tw", 'page { title "W" layout "main" render static } BODY { p "{missing}" }')
    args = type(
        "Args",
        (),
        dict(
            project_root=str(root),
            out_dir=str(root / "dist"),
            force=True,
            workers=1,
            dev=False,
            prod=True,
            watch=False,
            analyze=False,
            clean=False,
            no_minify=True,
            fail_on_warnings=False,
            strict=False,
        ),
    )()
    assert cli.command_build(args) == 1


def test_cli_check_json_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = make_project(tmp_path)
    tw = root / "[home]" / "pages" / "ok.tw"
    _write(tw, 'page { title "Ok" layout "main" render static } BODY { p "ok" }')
    args = type("Args", (), dict(file=str(tw), out=None, include_ast=False, include_ir=False))()
    code = cli.command_check(args)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert set(payload.keys()) >= {"diagnostics", "metadata", "dependencies", "route_path", "pipeline", "summary"}
    assert payload["summary"]["errors"] == 0


def test_cli_check_include_ast_and_ir_are_json_serializable(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = make_project(tmp_path)
    tw = root / "[home]" / "pages" / "ok.tw"
    _write(
        tw,
        """
page { title "Ok" layout "main" render static }
load @../style/extra.tss
BODY { p "ok" }
""".lstrip(),
    )
    _write(root / "[home]" / "style" / "extra.tss", ".ok { color red }")
    args = type("Args", (), dict(file=str(tw), out=None, include_ast=True, include_ir=True))()
    code = cli.command_check(args)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert code == 0
    assert "ast" in payload and "ir" in payload
    assert isinstance(payload["ast"]["loaded_sheets"], list)
    assert payload["metadata"]["diagnostic_summary"]["errors"] == 0


def test_compile_pipeline_reports_failure_phase(tmp_path: Path):
    root = make_project(tmp_path)
    tw = root / "[home]" / "pages" / "broken.tw"
    _write(tw, 'page { title "Broken" layout "main" render static } BODY { p "oops }')
    artifacts = compiler.compile_file_pipeline(str(tw), capture_errors=True)
    assert artifacts.diagnostics
    assert artifacts.diagnostics[0]["phase"] in {"tokenize", "parse"}
    assert artifacts.metadata["diagnostic_summary"]["errors"] >= 1


def test_cli_doctor_smoke(tmp_path: Path):
    root = make_project(tmp_path)
    args = type("Args", (), dict(project_root=str(root)))()
    assert cli.command_doctor(args) == 0


def test_cli_create_scaffold_generates_files(tmp_path: Path):
    target_parent = tmp_path / "parent"
    target_parent.mkdir()
    cli.create_project("hello", str(target_parent))
    root = target_parent / "hello"
    assert (root / "tw.config").exists()
    assert (root / "[home]" / "index.tw").exists()
    assert (root / ".gitignore").exists()


def test_incremental_build_cache_skips(tmp_path: Path):
    root = make_project(tmp_path)
    out_dir = root / "dist"
    first = framework.build_hidden_site(str(root), str(out_dir), workers=1, minify=False)
    second = framework.build_hidden_site(str(root), str(out_dir), workers=1, minify=False)
    assert first.errors == 0
    assert second.errors == 0
    assert second.skipped >= 1


def test_dependency_graph_contains_component_deps(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "components" / "Thing.tw", 'div { p "T" }')
    _write(home / "pages" / "uses.tw", 'page { title "U" layout "main" render static } BODY { import "Thing" Thing {} }')
    framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    graph_path = root / ".tw" / "cache" / "dependency-graph.json"
    payload = json.loads(graph_path.read_text("utf-8"))
    forward = payload["forward"]
    # At least one page should include the component .tw path as a dependency
    assert any("Thing.tw" in " ".join(deps) for deps in forward.values())


def test_parse_state_block_basic():
    state = parse_state_block(
        """
state {
  count 0
  name "World"
  items [1,2,3]
}
""".lstrip()
    )
    assert state["count"] == 0
    assert state["name"] == "World"
    assert state["items"] == [1, 2, 3]


def test_css_normalization_edge_cases():
    css = framework.compiler.render_css(  # type: ignore[attr-defined]
        compiler.build_tss_ast_from_text(
            """
.x {
  padding 0
  margin -2
  width 50%
}
"""
        )
    )
    assert "padding: 0;" in css
    assert "margin: -2px;" in css
    assert "width: 50%;" in css


def test_minifiers_do_not_crash():
    assert compiler.minify_html_content("<div> \n  <span> x </span>\n</div>")
    assert compiler.minify_css_content("/*x*/ .a { color : red ; }")
    assert compiler.minify_js_content("//c\n/*x*/\nvar a = 1;\n")


def test_dynamic_json_malformed_returns_empty_and_warns(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "pages" / "[id].tw", 'page { title "D" layout "main" render static } BODY { p "x" }')
    _write(home / "pages" / "[id].json", "{not: json")
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    err = capsys.readouterr().err
    assert summary.errors == 0  # malformed dynamic items should not crash the whole build
    assert "Failed to parse dynamic route JSON" in err


def test_route_collision_warning_and_strict_error(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    # Static /about
    _write(home / "pages" / "about.tw", 'page { title "A" layout "main" render static } BODY { p "about" }')
    # Dynamic [slug] that also emits /about
    _write(home / "pages" / "[slug].tw", 'page { title "S" layout "main" render static } BODY { p "{slug}" }')
    _write(home / "pages" / "[slug].json", json.dumps([{"slug": "about"}]))

    non_strict = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False, strict=False)
    assert non_strict.errors == 0
    assert non_strict.route_collisions >= 1

    strict = framework.build_hidden_site(str(root), str(root / "dist2"), workers=1, minify=False, strict=True)
    assert strict.errors >= 1
    assert strict.route_collisions >= 1


def test_dynamic_json_schema_validation_is_error(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "pages" / "[id].tw", 'page { title "D" layout "main" render static } BODY { p "{id}" }')
    # Wrong schema (not list / not {items:[]})
    _write(home / "pages" / "[id].json", json.dumps({"bad": True}))
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors >= 1


def test_backup_before_write_manifest_and_dependency_graph(tmp_path: Path):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    # Seed old files
    old_manifest = {"version": compiler.BUILD_MANIFEST_VERSION, "pages": {"x": {"outputs": []}}}
    old_graph = {"version": compiler.DEPENDENCY_GRAPH_VERSION, "forward": {}, "reverse": {}, "metadata": {}}
    (root / ".tw" / "manifest").mkdir(parents=True, exist_ok=True)
    (root / ".tw" / "cache").mkdir(parents=True, exist_ok=True)
    (root / ".tw" / "manifest" / "build-manifest.json").write_text(json.dumps(old_manifest), "utf-8")
    (root / ".tw" / "cache" / "dependency-graph.json").write_text(json.dumps(old_graph), "utf-8")

    compiler.save_build_manifest({"pages": {}})
    compiler.save_dependency_graph({"forward": {}, "metadata": {}})

    assert (root / ".tw" / "manifest" / "build-manifest.json.bak").exists()
    assert (root / ".tw" / "cache" / "dependency-graph.json.bak").exists()


def test_chunk_cache_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    monkeypatch.setenv("TW_CHUNK_CACHE_MAX", "2")
    framework.invalidate_compiler_caches()
    compiler.write_chunk("a", "js")
    compiler.write_chunk("b", "js")
    compiler.write_chunk("c", "js")
    assert len(compiler._CHUNK_CACHE) <= 2


def test_env_parsing_inline_comments_and_quotes(tmp_path: Path):
    root = make_project(tmp_path)
    env_path = root / ".env"
    env_path.write_text('A=1 # comment\nB="x # not comment"\nC=\'y # not comment\'\n', "utf-8")
    env = framework.load_project_env(str(root), "development")
    assert env["A"] == "1"
    assert env["B"] == "x # not comment"
    assert env["C"] == "y # not comment"


def test_build_package_json_scaffolds_dependency_sections():
    package_json = json.loads(cli.build_package_json("Demo App"))
    assert package_json["name"] == "demo-app"
    assert package_json["engines"]["node"] == ">=18"
    assert package_json["dependencies"] == {}
    assert package_json["devDependencies"] == {}


def test_twm_async_helpers_support_http_env_and_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if shutil.which("node") is None:
        pytest.skip("Node.js is required for `.twm` runtime tests")

    root = make_project(tmp_path)
    home = root / "[home]"
    handler_path = home / "api" / "proxy.twm"
    _write(
        handler_path,
        """
async fn post(request) {
  const response = await http.post(
    env.require("TW_TEST_TARGET") + "/echo",
    { hello: "world", incoming: request.body },
    { timeout: 3000 }
  );
  return {
    json: {
      ok: response.ok,
      status: response.status,
      echoed: response.data.received,
      secret: secrets.require("TW_TEST_SECRET"),
      sep: pkg.require("path").sep
    }
  };
}
""".lstrip(),
    )

    class EchoHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0") or "0")
            payload = self.rfile.read(length)
            data = json.loads(payload.decode("utf-8"))
            body = json.dumps({"received": data}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server_instance = socketserver.TCPServer(("127.0.0.1", 0), EchoHandler)
    server_thread = threading.Thread(target=server_instance.serve_forever, daemon=True)
    server_thread.start()

    monkeypatch.setenv("TW_TEST_TARGET", f"http://127.0.0.1:{server_instance.server_address[1]}")
    monkeypatch.setenv("TW_TEST_SECRET", "top-secret")
    framework.configure_compiler_paths(str(root))

    try:
        response = framework.execute_twm_api_handler(
            str(handler_path),
            "POST",
            "/api/proxy",
            {"Content-Type": "application/json"},
            {"user": "demo"},
        )
    finally:
        server_instance.shutdown()
        server_thread.join(timeout=2)
        server_instance.server_close()

    payload = json.loads(response["body"].decode("utf-8"))
    assert response["status"] == 200
    assert payload["ok"] is True
    assert payload["status"] == 200
    assert payload["echoed"] == {"hello": "world", "incoming": {"user": "demo"}}
    assert payload["secret"] == "top-secret"
    assert payload["sep"] in {"/", "\\"}


def test_global_config_atomic_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Redirect global config to temp paths
    cfg_dir = tmp_path / "cfg"
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr(cli, "GLOBAL_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(cli, "GLOBAL_CONFIG_FILE", str(cfg_file))
    cli.save_global_config({"vercel_token": "t"})
    assert cfg_file.exists()
    data = json.loads(cfg_file.read_text("utf-8"))
    assert data["vercel_token"] == "t"
    assert stat.S_IMODE(os.stat(cfg_dir).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(cfg_file).st_mode) == 0o600


def test_file_watcher_rescan_ticks_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    project = framework.TWProject(str(root))
    state = framework.TWDevState(project)
    monkeypatch.setenv("TW_WATCH_RESCAN_TICKS", "1")
    monkeypatch.setenv("TW_WATCH_BACKEND", "poll")
    watcher = framework.TWFileWatcher(state, interval=0.2)
    assert watcher.rescan_ticks == 1


def test_file_watcher_inotify_setup_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not sys.platform.startswith("linux"):
        pytest.skip("inotify backend is Linux-only")
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    project = framework.TWProject(str(root))
    state = framework.TWDevState(project)
    monkeypatch.setenv("TW_WATCH_BACKEND", "inotify")
    watcher = framework.TWFileWatcher(state, interval=0.2)
    ok = watcher._inotify_setup()
    if not ok:
        pytest.skip("inotify not available in this environment")
    assert watcher._inotify_fd is not None
    # Cleanup: close fd to avoid leaking across tests
    os.close(watcher._inotify_fd)
    watcher._inotify_fd = None


def test_thread_safety_build_workers(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"
    _write(home / "components" / "Shared.tw", 'div { p "shared" }')
    for i in range(12):
        _write(
            home / "pages" / f"p{i}.tw",
            f"""
page {{
  title "P{i}"
  layout "main"
  render static
}}
BODY {{ import "Shared" Shared {{}} }}
""".lstrip(),
        )
    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=4, minify=False)
    assert summary.errors == 0


def test_component_import_path_traversal_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    with pytest.raises(compiler.CompilerError):
        compiler.resolve_component_path("../secrets")


def test_component_name_absolute_and_null_bytes_rejected(tmp_path: Path):
    root = make_project(tmp_path)
    framework.configure_compiler_paths(str(root))
    with pytest.raises(compiler.CompilerError):
        compiler.resolve_component_path("/tmp/secret")
    with pytest.raises(compiler.CompilerError):
        compiler.resolve_component_path("Bad\x00Name")


def test_extension_manager_warns_before_executing_plugins(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    root = make_project(tmp_path)
    plugin_dir = root / "[home]" / "plugins"
    _write(
        plugin_dir / "sample.py",
        """
def register(api):
    api.register_hook("beforeBuild", lambda payload: payload)
""".lstrip(),
    )
    caplog.set_level("WARNING")
    manager = ExtensionManager(str(root), config={}, env={}).refresh()
    assert manager.extensions
    assert "Executing TW extensions from project code" in caplog.text
    assert "sample.py" in caplog.text


def test_extension_allowlist_blocks_unlisted_plugins(tmp_path: Path):
    root = make_project(tmp_path)
    plugin_dir = root / "[home]" / "plugins"
    marker = root / "executed.txt"
    _write(
        plugin_dir / "allowed.py",
        """
def register(api):
    api.register_hook("beforeBuild", lambda payload: dict(payload, allowed=True))
""".lstrip(),
    )
    _write(
        plugin_dir / "blocked.py",
        f"""
from pathlib import Path
Path({str(marker)!r}).write_text("blocked", encoding="utf-8")

def register(api):
    api.register_hook("beforeBuild", lambda payload: payload)
""".lstrip(),
    )
    manager = ExtensionManager(
        str(root),
        config={"plugin_allowlist": ["allowed.py"]},
        env={},
    ).refresh()
    assert [ext.name for ext in manager.extensions] == ["allowed"]
    assert not marker.exists()


def test_create_project_gitignore_includes_cache_dir(tmp_path: Path):
    target_parent = tmp_path / "parent2"
    target_parent.mkdir()
    cli.create_project("hello2", str(target_parent))
    gitignore = (target_parent / "hello2" / ".gitignore").read_text("utf-8")
    assert ".tw-cache/" in gitignore


def test_load_config_supports_nested_blocks(tmp_path: Path):
    root = make_project(tmp_path)
    _write(
        root / "tw.config",
        """
name: Nested Site
security:
  headers:
    X-Frame-Options: DENY
cookies:
  secure: auto
ssr:
  cache_max: 42
""".lstrip(),
    )
    framework.configure_compiler_paths(str(root))
    config = compiler.load_config()
    assert config["security"]["headers"]["X-Frame-Options"] == "DENY"
    assert config["cookies"]["secure"] == "auto"
    assert config["ssr"]["cache_max"] == 42


def test_page_parser_accepts_cache_controls(tmp_path: Path):
    root = make_project(tmp_path)
    page_path = root / "[home]" / "pages" / "edge.tw"
    _write(
        page_path,
        """
page {
  title "Edge"
  layout "main"
  render edge
  revalidate 60
  cache_by cookie:session_id
  cache_size 3
}
BODY { div "edge" }
""".lstrip(),
    )
    framework.configure_compiler_paths(str(root))
    page_ast = compiler.load_page_ast_from_file(str(page_path))
    assert page_ast.cache_by == "cookie:session_id"
    assert page_ast.cache_size == 3


def test_rate_limit_is_opt_in_middleware_primitive(tmp_path: Path):
    root = make_project(tmp_path)
    _write(
        root / "middleware.tw",
        """
use {
  match "/api/**"
  rate_limit {
    requests 1
    window 60
  }
}
""".lstrip(),
    )
    framework.configure_compiler_paths(str(root))
    project = framework.TWProject(str(root))
    first = project.apply_middleware("/api/users", {"Cookie": ""}, request_meta={"client_ip": "127.0.0.1"})
    second = project.apply_middleware("/api/users", {"Cookie": ""}, request_meta={"client_ip": "127.0.0.1"})
    assert first["response"] is None
    assert second["response"]["status"] == 429


def test_render_cookie_header_honors_secure_mode_auto():
    secure = framework.render_cookie_header(
        "session",
        "abc",
        config={"cookies": {"secure": "auto"}},
        request_headers={"X-Forwarded-Proto": "https"},
        server_port=443,
    )
    insecure = framework.render_cookie_header(
        "session",
        "abc",
        config={"cookies": {"secure": "auto"}},
        request_headers={"X-Forwarded-Proto": "http"},
        server_port=80,
    )
    assert "Secure" in secure
    assert "Secure" not in insecure


def test_is_path_within_blocks_prefix_confusion(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    sibling = tmp_path / "root-evil" / "file.txt"
    sibling.parent.mkdir()
    sibling.write_text("x", encoding="utf-8")
    assert framework.is_path_within(str(root), str(root / "ok.txt"))
    assert not framework.is_path_within(str(root), str(sibling))


def test_ssr_cache_respects_namespace_limit():
    cache = server.SSRCache(max_entries=10)
    cache.set("a", b"1", None, namespace="/dashboard", namespace_max=2)
    cache.set("b", b"2", None, namespace="/dashboard", namespace_max=2)
    cache.set("c", b"3", None, namespace="/dashboard", namespace_max=2)
    assert cache.get("a") is None
    assert cache.get("b") == b"2"
    assert cache.get("c") == b"3"


def test_twm_modules_compile_and_do_not_auto_execute(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"

    # External `.twm` module loaded via the universal `load` keyword.
    _write(
        home / "lib" / "auth.twm",
        """
fn login() {
  // only runs when called explicitly from an event
  console.log("login");
}
""".lstrip(),
    )

    # Local SCRIPT { ... } block should behave like a `.twm` module (registered, not executed).
    _write(
        home / "pages" / "mod.tw",
        """
load @./lib/auth.twm

SCRIPT {
  fn hello() {
    console.log("hello");
  }
}

page { title "M" layout "main" render static }
BODY {
  button {
    onclick login
    text "Login"
  }
}
""".lstrip(),
    )

    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0

    html_path = root / "dist" / "mod" / "index.html"
    assert html_path.exists()
    html = html_path.read_text("utf-8")
    assert "onclick" in html
    assert "__twInvoke" in html or "window.__twInvoke" in html

    chunks_dir = root / "dist" / "_tw" / "static" / "chunks"
    js_files = list(chunks_dir.glob("*.js"))
    assert js_files, "Expected TW to emit at least one JS chunk for `.twm` bundle"
    joined = "\n".join(p.read_text("utf-8") for p in js_files)
    assert "__twRegistry" in joined
    assert "function login" in joined
    assert "function hello" in joined


def test_on_load_init_injects_explicit_invoke(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"

    _write(
        home / "lib" / "init.twm",
        """
fn init() {
  console.log("init ran");
}
""".lstrip(),
    )

    _write(
        home / "pages" / "init.tw",
        """
load @./lib/init.twm

on load init init

page { title "Init" layout "main" render static }
BODY {
  div { text "Hello" }
}
""".lstrip(),
    )

    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0

    html_path = root / "dist" / "init" / "index.html"
    assert html_path.exists()
    html = html_path.read_text("utf-8")
    assert "__twInvoke" in html
    assert "DOMContentLoaded" in html
    assert '"init"' in html or "'init'" in html


def test_declarative_script_tag_strategies(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"

    _write(
        home / "pages" / "scripts.tw",
        """
page { title "Scripts" layout "main" render static }
BODY {
  script { src "https://example.com/a.js" strategy beforeInteractive }
  script { src "https://example.com/b.js" strategy afterInteractive }
  script { src "https://example.com/c.js" strategy lazyOnload }
  div { text "ok" }
}
""".lstrip(),
    )

    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors == 0

    html_path = root / "dist" / "scripts" / "index.html"
    html = html_path.read_text("utf-8")
    # beforeInteractive should land in <head>
    assert "<head>" in html
    assert "https://example.com/a.js" in html.split("</head>", 1)[0]
    # afterInteractive & lazyOnload should be deferred via loader script
    assert "https://example.com/b.js" in html
    assert "https://example.com/c.js" in html
    assert "DOMContentLoaded" in html
    assert "addEventListener('load'" in html or "addEventListener(\"load\"" in html


def test_raw_script_blocks_disabled_by_default(tmp_path: Path):
    root = make_project(tmp_path)
    home = root / "[home]"

    _write(
        home / "pages" / "raw.tw",
        """
page { title "Raw" layout "main" render static }
BODY {
  script { console.log("should not run") }
  div { text "x" }
}
""".lstrip(),
    )

    summary = framework.build_hidden_site(str(root), str(root / "dist"), workers=1, minify=False)
    assert summary.errors >= 1

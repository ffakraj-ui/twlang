"""
Tests for v0.8.0 features: VDOM, Lib system overhaul, Server Actions, 
Metadata API, ISR, Suspense/Streaming.
"""
from __future__ import annotations
import os, sys, json, re, tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tw_framework import compiler
from tw_framework.reactivity import (
    get_vdom_runtime_js, build_state_init_script, has_vdom_features,
    should_use_vdom, transform_reactive_attrs, parse_state_block,
    extract_server_actions, build_action_bindings_js,
)
from tw_framework.lib_executor import (
    parse_imports, resolve_module_path, strip_imports,
    extract_client_functions, strip_type_annotations,
    is_function_call, execute_lib_function, LibExecutionError,
    extract_generate_metadata, extract_isr_config,
)


def _compile_page(source):
    """Helper: compile .tw source to HTML using the correct TW API."""
    tw_path = tempfile.mktemp(suffix='.tw')
    with open(tw_path, 'w') as f:
        f.write(source)
    tokens = compiler.tokenize_tw(source)
    base_dir = os.path.dirname(tw_path)
    page_ast = compiler.build_tw_ast(tokens, base_dir, tw_path, source)
    context = compiler.create_base_context(page_ast, tw_path)
    result = compiler.render_elements_html(page_ast.body, context)
    # render_elements_html returns (html_str, needs_router, head_scripts)
    if isinstance(result, tuple):
        html = result[0]
    else:
        html = result
    from tw_framework.reactivity import has_vdom_features, parse_state_block
    if has_vdom_features(source):
        state = parse_state_block(source)
        html = compiler._inject_reactivity_runtime(html, source, state)
    return html


# ─── VDOM Tests ──────────────────────────────────────────────────────────────

class TestVDOMRuntime:
    def test_vdom_runtime_js_exists(self):
        js = get_vdom_runtime_js()
        assert len(js) > 1000

    def test_vdom_has_diff_algorithm(self):
        js = get_vdom_runtime_js()
        assert '__twDiff' in js
        assert '__twDiffChildren' in js
        assert '__twDiffProps' in js

    def test_vdom_has_batched_updates(self):
        js = get_vdom_runtime_js()
        assert '__twScheduleUpdate' in js
        assert '__twFlush' in js
        assert 'requestAnimationFrame' in js

    def test_vdom_has_keyed_children(self):
        js = get_vdom_runtime_js()
        assert 'data-tw-key' in js
        assert '__twReorderChildren' in js

    def test_vdom_has_create_element(self):
        js = get_vdom_runtime_js()
        assert '__twCreateElement' in js

    def test_vdom_has_server_actions(self):
        js = get_vdom_runtime_js()
        assert '__twAction' in js
        assert '__twActions' in js

    def test_vdom_has_suspense(self):
        js = get_vdom_runtime_js()
        assert '__twSuspense' in js

    def test_vdom_has_fetch_helper(self):
        js = get_vdom_runtime_js()
        assert '__twFetch' in js

    def test_vdom_has_hyperscript(self):
        js = get_vdom_runtime_js()
        assert '__twH' in js
        assert '__twText' in js

    def test_vdom_no_react_dependency(self):
        js = get_vdom_runtime_js()
        assert 'React' not in js
        assert 'ReactDOM' not in js

    def test_vdom_size_reasonable(self):
        js = get_vdom_runtime_js()
        assert len(js) < 20000


class TestVDOMDetection:
    def test_has_vdom_features_state(self):
        assert has_vdom_features('state {\n  count 0\n}')

    def test_has_vdom_features_bind(self):
        assert has_vdom_features('input { bind:value "name" }')

    def test_has_vdom_features_on_click(self):
        assert has_vdom_features('button { on:click "count++" }')

    def test_has_vdom_features_show(self):
        assert has_vdom_features('div { show:visible "count > 0" }')

    def test_has_vdom_features_tw_for(self):
        assert has_vdom_features('ul { tw-for "items" }')

    def test_has_vdom_features_tw_if(self):
        assert has_vdom_features('div { tw-if "show" }')

    def test_no_vdom_features_static(self):
        assert not has_vdom_features('h1 "Hello"')

    def test_no_vdom_features_plain_html(self):
        assert not has_vdom_features('<div>Hello</div>')

    def test_should_use_vdom_interactive(self):
        assert should_use_vdom('', 'interactive')

    def test_should_use_vdom_auto_detect(self):
        assert should_use_vdom('state { count 0 }', '')

    def test_should_not_use_vdom_static(self):
        assert not should_use_vdom('h1 "Hello"', 'static')


class TestVDOMStateInit:
    def test_state_init_basic(self):
        js = build_state_init_script({"count": 0, "name": "hello"})
        assert "__twDefineState" in js
        assert '"count": 0' in js

    def test_state_init_empty(self):
        assert build_state_init_script({}) == ""

    def test_state_init_array(self):
        js = build_state_init_script({"items": [1, 2, 3]})
        assert "[1, 2, 3]" in js

    def test_state_init_unicode(self):
        js = build_state_init_script({"name": "Kanishk"})
        assert "Kanishk" in js


class TestVDOMAttrs:
    def test_bind_attr(self):
        attrs = [("bind:value", "name")]
        result = transform_reactive_attrs(attrs)
        assert ("data-tw-bind", "name") in result

    def test_show_attr(self):
        attrs = [("show:visible", "count > 0")]
        result = transform_reactive_attrs(attrs)
        assert ("data-tw-show", "count > 0") in result

    def test_on_click_attr(self):
        attrs = [("on:click", "count++")]
        result = transform_reactive_attrs(attrs)
        assert any(k == "data-tw-on" for k, v in result)

    def test_tw_if_attr(self):
        attrs = [("tw-if", "show")]
        result = transform_reactive_attrs(attrs)
        assert ("data-tw-if", "show") in result

    def test_tw_else_attr(self):
        attrs = [("tw-else", "")]
        result = transform_reactive_attrs(attrs)
        assert ("data-tw-else", "") in result

    def test_tw_key_attr(self):
        attrs = [("tw-key", "item.id")]
        result = transform_reactive_attrs(attrs)
        assert ("data-tw-key", "item.id") in result

    def test_regular_attr_preserved(self):
        attrs = [("class", "card"), ("id", "main")]
        result = transform_reactive_attrs(attrs)
        assert ("class", "card") in result


class TestStateBlockParser:
    def test_basic_state(self):
        source = 'state {\n  count 0\n  name "hello"\n}'
        state = parse_state_block(source)
        assert state["count"] == 0
        assert state["name"] == "hello"

    def test_typed_state(self):
        source = 'state {\n  count: number = 0\n  name: string = "hello"\n}'
        state = parse_state_block(source)
        assert state["count"] == 0
        assert state["name"] == "hello"

    def test_array_state(self):
        source = 'state {\n  items []\n}'
        state = parse_state_block(source)
        assert state["items"] == []

    def test_no_state_block(self):
        state = parse_state_block('h1 "Hello"')
        assert state == {}


# ─── Lib System Tests ────────────────────────────────────────────────────────

class TestImportParser:
    def test_named_import(self):
        imports = parse_imports('import { getApps } from "@/lib/data"')
        assert len(imports) == 1
        assert imports[0]['named'] == [('getApps', 'getApps')]
        assert imports[0]['module'] == '@/lib/data'

    def test_multiple_named_imports(self):
        imports = parse_imports('import { a, b, c } from "@/lib/utils"')
        assert len(imports[0]['named']) == 3

    def test_import_with_alias(self):
        imports = parse_imports('import { foo as bar } from "@/lib/utils"')
        assert imports[0]['named'] == [('foo', 'bar')]

    def test_default_import(self):
        imports = parse_imports('import myFunc from "@/lib/func"')
        assert imports[0]['default'] == 'myFunc'

    def test_default_and_named(self):
        imports = parse_imports('import def, { named } from "@/lib/mod"')
        assert imports[0]['default'] == 'def'
        assert ('named', 'named') in imports[0]['named']

    def test_namespace_import(self):
        imports = parse_imports('import * as utils from "@/lib/utils"')
        assert imports[0]['namespace'] == 'utils'

    def test_relative_import(self):
        imports = parse_imports('import { foo } from "./utils"')
        assert imports[0]['module'] == './utils'

    def test_no_imports(self):
        assert parse_imports('h1 "Hello"') == []


class TestModuleResolution:
    def test_at_prefix(self, tmp_path):
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "data.twm").write_text("fn foo() { return 42 }")
        path = resolve_module_path("@/lib/data", str(tmp_path / "page.tw"), str(tmp_path))
        assert path is not None
        assert path.endswith("data.twm")

    def test_relative(self, tmp_path):
        (tmp_path / "utils.twm").write_text("fn foo() { return 42 }")
        path = resolve_module_path("./utils", str(tmp_path / "page.tw"), str(tmp_path))
        assert path is not None
        assert path.endswith("utils.twm")

    def test_not_found(self, tmp_path):
        path = resolve_module_path("@/lib/nonexistent", str(tmp_path / "page.tw"), str(tmp_path))
        assert path is None


class TestStripImports:
    def test_strip_single(self):
        source = 'import { foo } from "@/lib/utils"\n\nh1 "Hello"'
        cleaned = strip_imports(source)
        assert "import" not in cleaned
        assert "h1" in cleaned

    def test_strip_multiple(self):
        source = 'import { a } from "@/lib/a"\nimport { b } from "@/lib/b"\nh1 "Hi"'
        cleaned = strip_imports(source)
        assert cleaned.count("import") == 0


class TestClientFunctions:
    def test_extract_client_function(self):
        src = 'export client function formatPrice(n) {\n  return "Rs" + n.toFixed(2)\n}'
        fns = extract_client_functions(src)
        assert len(fns) == 1
        assert fns[0]['name'] == 'formatPrice'

    def test_extract_client_async(self):
        src = 'export client async function fetchData() {\n  return await fetch("/api")\n}'
        fns = extract_client_functions(src)
        assert len(fns) == 1
        assert fns[0]['is_async'] == True

    def test_no_client_functions(self):
        src = 'export function serverFunc() { return 42 }'
        fns = extract_client_functions(src)
        assert len(fns) == 0


class TestTypeAnnotationStripping:
    def test_strip_param_type(self):
        code = 'function foo(x: string) { return x }'
        result = strip_type_annotations(code)
        assert ': string' not in result

    def test_strip_return_type(self):
        code = 'function foo(x): Promise<App> { return x }'
        result = strip_type_annotations(code)
        assert 'Promise<App>' not in result

    def test_strip_var_type(self):
        code = 'let x: number = 5'
        result = strip_type_annotations(code)
        assert ': number' not in result

    def test_multiple_param_types(self):
        code = 'function add(a: number, b: number) { return a + b }'
        result = strip_type_annotations(code)
        assert ': number' not in result


class TestLibBackwardCompat:
    def test_execute_object_return(self):
        src = 'fn greet(name) {\n  return { message: "Hello, " + name + "!", name: name }\n}\n'
        result = execute_lib_function(src, "greet", '"Kanishk"', module_id="test")
        assert result["message"] == "Hello, Kanishk!"

    def test_execute_array_return(self):
        src = 'fn getApps() {\n  return [{name: "WhatsApp"}, {name: "Telegram"}]\n}\n'
        result = execute_lib_function(src, "getApps", "", module_id="test")
        assert len(result) == 2
        assert result[0]["name"] == "WhatsApp"

    def test_execute_number_return(self):
        src = 'fn calc(a, b) {\n  return a + b\n}\n'
        result = execute_lib_function(src, "calc", "5, 10", module_id="test")
        assert result == 15

    def test_execute_function_not_found(self):
        src = 'fn foo() {\n  return 42\n}\n'
        with pytest.raises(LibExecutionError, match="not found"):
            execute_lib_function(src, "bar", "", module_id="test")


# ─── Server Actions Tests ───────────────────────────────────────────────────

class TestServerActions:
    def test_extract_action_block(self):
        source = 'action createPost {\n    method POST\n    handler "createPost"\n    require_auth true\n}'
        actions = extract_server_actions(source)
        assert len(actions) == 1
        assert actions[0]['name'] == 'createPost'
        assert actions[0]['method'] == 'POST'
        assert actions[0]['require_auth'] == True

    def test_extract_multiple_actions(self):
        source = 'action createPost {\n    method POST\n}\naction deletePost {\n    method DELETE\n}'
        actions = extract_server_actions(source)
        assert len(actions) == 2

    def test_action_bindings_js(self):
        actions = [{'name': 'createPost', 'method': 'POST', 'handler': 'createPost', 'require_auth': True}]
        js = build_action_bindings_js(actions)
        assert "__twActions" in js
        assert "createPost" in js
        assert "/__tw/actions/createPost" in js

    def test_no_actions(self):
        actions = extract_server_actions('h1 "Hello"')
        assert len(actions) == 0
        assert build_action_bindings_js([]) == ""


# ─── Metadata API Tests ─────────────────────────────────────────────────────

class TestMetadata:
    def test_static_metadata(self):
        source = 'metadata {\n    title "My Page"\n    description "A great page"\n}'
        meta = extract_generate_metadata(source)
        assert meta is not None
        assert meta['type'] == 'static'
        assert meta['data']['title'] == 'My Page'

    def test_no_metadata(self):
        meta = extract_generate_metadata('h1 "Hello"')
        assert meta is None


# ─── ISR Tests ────────────────────────────────────────────────────────────────

class TestISR:
    def test_extract_isr_config(self):
        source = 'page {\n    title "Apps"\n    revalidate 60\n}'
        config = extract_isr_config(source)
        assert config is not None
        assert config['enabled'] == True
        assert config['seconds'] == 60

    def test_no_isr(self):
        config = extract_isr_config('h1 "Hello"')
        assert config is None


# ─── Integration: VDOM in compiled output ────────────────────────────────────

class TestVDOMIntegration:
    def test_static_page_compiles(self):
        source = 'page { title "Home" render static }\nbody { h1 "Hello World" }'
        html = _compile_page(source)
        assert isinstance(html, str)
        assert "Hello World" in html

    def test_interactive_page_has_vdom(self):
        source = 'page { title "Counter" render interactive }\nstate { count 0 }\nbody { button { on:click "count++" } }'
        html = _compile_page(source)
        assert "__tw" in html or "data-tw" in html

    def test_auto_detect_vdom(self):
        source = 'page { title "Auto" }\nstate { count 0 }\nbody { p { tw-text "count" } }'
        html = _compile_page(source)
        assert "__tw" in html or "data-tw" in html


# ─── Zero-JS preservation ────────────────────────────────────────────────────

class TestZeroJSPreservation:
    def test_pure_static_zero_js(self):
        source = 'page { title "Static" render static }\nbody { h1 "Hello" p "World" }'
        html = _compile_page(source)
        assert "<script" not in html, "Static page must have zero JS"

    def test_page_with_let_zero_js(self):
        source = 'page { title "With Let" render static }\nlet name = "Kanishk"\nbody { h1 "Hello {name}" }'
        html = _compile_page(source)
        assert "<script" not in html, "Page with let but no state should be zero-JS"

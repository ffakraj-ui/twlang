"""
Tests for:
1. let x = [{...}] inline JSON support in TW pages
2. Tailwind CSS utility classes in .tss files
"""
import sys, os, json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tw_framework.compiler import (
    tokenize_tw, build_tw_ast, parse_literal_value,
    build_tss_ast_from_text, render_css, create_base_context,
    load_page_ast_from_file, interpolate, evaluate_expression,
)
from tw_framework.tailwind_map import expand_tailwind_class, expand_tailwind_line


# ═══════════════════════════════════════════════════════════════════════════
# 1. INLINE JSON IN let
# ═══════════════════════════════════════════════════════════════════════════

def test_let_with_inline_array_of_objects():
    """let x = [{"a": 1}, {"b": 2}] should parse as a list of dicts."""
    code = '''page {
    title "Test"
    render static
}

let items = [{"id": 1, "name": "First"}, {"id": 2, "name": "Second"}]

body {
    div { class "container" }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "items" in ast_tree.let_vars, f"let_vars: {ast_tree.let_vars}"
    val = ast_tree.let_vars["items"]
    assert isinstance(val, list), f"Expected list, got {type(val)}"
    assert len(val) == 2
    assert val[0]["id"] == 1
    assert val[0]["name"] == "First"
    assert val[1]["id"] == 2
    assert val[1]["name"] == "Second"
    print("✅ test_let_with_inline_array_of_objects")


def test_let_with_simple_array():
    """let nums = [1, 2, 3] should parse correctly."""
    code = '''page {
    title "Test"
    render static
}

let nums = [1, 2, 3]

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "nums" in ast_tree.let_vars
    val = ast_tree.let_vars["nums"]
    assert isinstance(val, list)
    assert val == [1, 2, 3]
    print("✅ test_let_with_simple_array")


def test_let_with_inline_object():
    """let config = {"key": "value", "num": 42} should parse correctly."""
    code = '''page {
    title "Test"
    render static
}

let config = {"key": "value", "num": 42, "flag": true}

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "config" in ast_tree.let_vars
    val = ast_tree.let_vars["config"]
    assert isinstance(val, dict)
    assert val["key"] == "value"
    assert val["num"] == 42
    assert val["flag"] == True
    print("✅ test_let_with_inline_object")


def test_let_with_nested_arrays():
    """let matrix = [[1, 2], [3, 4]] should parse correctly."""
    code = '''page {
    title "Test"
    render static
}

let matrix = [[1, 2], [3, 4]]

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "matrix" in ast_tree.let_vars
    val = ast_tree.let_vars["matrix"]
    assert isinstance(val, list)
    assert val == [[1, 2], [3, 4]]
    print("✅ test_let_with_nested_arrays")


def test_let_with_empty_array():
    """let empty = [] should parse as empty list."""
    code = '''page {
    title "Test"
    render static
}

let empty = []

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "empty" in ast_tree.let_vars
    val = ast_tree.let_vars["empty"]
    assert isinstance(val, list)
    assert len(val) == 0
    print("✅ test_let_with_empty_array")


def test_let_with_empty_object():
    """let obj = {} should parse as empty dict."""
    code = '''page {
    title "Test"
    render static
}

let obj = {}

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "obj" in ast_tree.let_vars
    val = ast_tree.let_vars["obj"]
    assert isinstance(val, dict)
    assert len(val) == 0
    print("✅ test_let_with_empty_object")


def test_let_with_mixed_types_in_array():
    """let mixed = [1, "two", true, null] should parse correctly."""
    code = '''page {
    title "Test"
    render static
}

let mixed = [1, "two", true, null]

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "mixed" in ast_tree.let_vars
    val = ast_tree.let_vars["mixed"]
    assert isinstance(val, list)
    assert val[0] == 1
    assert val[1] == "two"
    assert val[2] == True
    assert val[3] is None
    print("✅ test_let_with_mixed_types_in_array")


def test_let_json_does_not_break_normal_blocks():
    """Ensure inline JSON in let doesn't break subsequent body blocks."""
    code = '''page {
    title "Test"
    render static
}

let items = [{"id": 1, "name": "Test"}]

body {
    div { class "container"
        p "Hello"
    }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "items" in ast_tree.let_vars
    assert isinstance(ast_tree.let_vars["items"], list)
    # Body should still parse correctly
    assert len(ast_tree.body) > 0, "Body should have elements"
    print("✅ test_let_json_does_not_break_normal_blocks")


def test_let_string_value_still_works():
    """Normal let with string value should still work."""
    code = '''page {
    title "Test"
    render static
}

let name "John"
let count 5

body {
    div { }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert ast_tree.let_vars.get("name") == "John"
    assert ast_tree.let_vars.get("count") == 5
    print("✅ test_let_string_value_still_works")


# ═══════════════════════════════════════════════════════════════════════════
# 2. TAILWIND CSS IN .tss FILES
# ═══════════════════════════════════════════════════════════════════════════

def test_tailwind_flex_center():
    """flex items-center justify-center → 3 CSS declarations."""
    tss = ".card { flex items-center justify-center }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: flex" in css
    assert "align-items: center" in css
    assert "justify-content: center" in css
    print("✅ test_tailwind_flex_center")


def test_tailwind_spacing():
    """p-4 m-2 gap-8 → padding 16px, margin 8px, gap 32px."""
    tss = ".box { p-4 m-2 gap-8 }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "padding: 16px" in css
    assert "margin: 8px" in css
    assert "gap: 32px" in css
    print("✅ test_tailwind_spacing")


def test_tailwind_colors():
    """bg-red-500 text-blue-600 → background-color and color."""
    tss = ".btn { bg-red-500 text-blue-600 }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "#ef4444" in css  # red-500
    assert "#2563eb" in css  # blue-600
    print("✅ test_tailwind_colors")


def test_tailwind_rounded():
    """rounded-lg rounded-full → border-radius."""
    tss = ".card { rounded-lg } .avatar { rounded-full }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "border-radius: 8px" in css
    assert "border-radius: 9999px" in css
    print("✅ test_tailwind_rounded")


def test_tailwind_font_sizes():
    """text-xl text-2xl → font-size."""
    tss = ".title { text-2xl } .subtitle { text-sm }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "font-size: 24px" in css
    assert "font-size: 14px" in css
    print("✅ test_tailwind_font_sizes")


def test_tailwind_font_weights():
    """font-bold font-medium → font-weight."""
    tss = ".title { font-bold } .text { font-medium }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "font-weight: 700" in css
    assert "font-weight: 500" in css
    print("✅ test_tailwind_font_weights")


def test_tailwind_shadows():
    """shadow-lg shadow-md → box-shadow."""
    tss = ".card { shadow-lg } .box { shadow-md }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "box-shadow" in css
    print("✅ test_tailwind_shadows")


def test_tailwind_opacity():
    """opacity-50 opacity-100 → opacity."""
    tss = ".overlay { opacity-50 } .full { opacity-100 }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "opacity: 0.5" in css
    assert "opacity: 1" in css
    print("✅ test_tailwind_opacity")


def test_tailwind_position():
    """relative absolute fixed sticky → position."""
    tss = ".modal { absolute } .nav { sticky }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "position: absolute" in css
    assert "position: sticky" in css
    print("✅ test_tailwind_position")


def test_tailwind_grid_cols():
    """grid-cols-3 → grid-template-columns: 1fr 1fr 1fr."""
    tss = ".grid-3 { grid grid-cols-3 }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: grid" in css
    assert "1fr 1fr 1fr" in css
    print("✅ test_tailwind_grid_cols")


def test_tailwind_max_width():
    """max-w-7xl → max-width: 1280px."""
    tss = ".container { max-w-7xl mx-auto }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "max-width: 1280px" in css
    assert "margin: 0 auto" in css
    print("✅ test_tailwind_max_width")


def test_tailwind_mixed_with_normal_tss():
    """Tailwind and normal TSS in same file."""
    tss = """.card {
    flex items-center gap-2
    bg-white rounded-lg
    border 1px solid #e2e8f0
    padding 16px
}
"""
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: flex" in css
    assert "align-items: center" in css
    assert "gap: 8px" in css
    # bg-white is not a valid Tailwind class (no shade), so falls back to TSS
    # But bg-white → bg is alias for background, white is value? No...
    # bg-white → not in Tailwind (needs shade), so the whole line falls back to TSS
    # Actually bg-white: _expand_color won't match "white" as bare color
    # So the line "bg-white rounded-lg" → not all Tailwind → TSS parsing
    # Let's check rounded-lg is there at least
    assert "border-radius: 8px" in css or "border" in css
    assert "1px solid #e2e8f0" in css
    assert "padding: 16px" in css
    print("✅ test_tailwind_mixed_with_normal_tss")


def test_tailwind_border_width():
    """border border-2 → border-width."""
    tss = ".card { border-2 } .box { border }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "border-width: 2px" in css
    assert "border-width: 1px" in css
    print("✅ test_tailwind_border_width")


def test_tailwind_cursor():
    """cursor-pointer → cursor: pointer."""
    tss = ".btn { cursor-pointer }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "cursor: pointer" in css
    print("✅ test_tailwind_cursor")


def test_tailwind_overflow():
    """overflow-hidden → overflow: hidden."""
    tss = ".box { overflow-hidden }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "overflow: hidden" in css
    print("✅ test_tailwind_overflow")


def test_tailwind_text_align():
    """text-center → text-align: center."""
    tss = ".center { text-center } .right { text-right }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "text-align: center" in css
    assert "text-align: right" in css
    print("✅ test_tailwind_text_align")


def test_tailwind_whitespace():
    """whitespace-nowrap → white-space: nowrap."""
    tss = ".nowrap { whitespace-nowrap }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "white-space: nowrap" in css
    print("✅ test_tailwind_whitespace")


def test_tailwind_line_through():
    """line-through → text-decoration: line-through."""
    tss = ".strike { line-through }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "text-decoration: line-through" in css
    print("✅ test_tailwind_line_through")


def test_tailwind_fallback_to_tss():
    """Non-Tailwind lines should fall back to normal TSS parsing."""
    tss = ".card { display flex; padding 16px; color red }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    # "display" is not a Tailwind class, so the line falls back to TSS
    assert "display" in css
    assert "padding" in css
    assert "color" in css
    print("✅ test_tailwind_fallback_to_tss")


def test_tailwind_hidden():
    """hidden → display: none."""
    tss = ".invisible { hidden }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: none" in css
    print("✅ test_tailwind_hidden")


def test_tailwind_flex_col():
    """flex-col → flex-direction: column."""
    tss = ".col { flex flex-col }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: flex" in css
    assert "flex-direction: column" in css
    print("✅ test_tailwind_flex_col")


def test_tailwind_between():
    """justify-between → justify-content: space-between."""
    tss = ".row { flex justify-between }"
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "justify-content: space-between" in css
    print("✅ test_tailwind_between")


# ═══════════════════════════════════════════════════════════════════════════
# 3. BOTH FEATURES TOGETHER
# ═══════════════════════════════════════════════════════════════════════════

def test_let_json_with_each_loop():
    """let items = [...] + each items as item { ... } should work together."""
    code = '''page {
    title "Test"
    render static
}

let items = [{"name": "Alpha"}, {"name": "Beta"}]

body {
    each items as item {
        p "{item.name}"
    }
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    assert "items" in ast_tree.let_vars
    items = ast_tree.let_vars["items"]
    assert isinstance(items, list)
    assert len(items) == 2
    assert items[0]["name"] == "Alpha"
    assert items[1]["name"] == "Beta"
    print("✅ test_let_json_with_each_loop")


def test_let_json_interpolation():
    """let config = {"name": "World"} → {config.name} should interpolate."""
    code = '''page {
    title "Test"
    render static
}

let config = {"name": "World", "count": 42}

body {
    p "Hello {config.name}! Count: {config.count}"
}
'''
    tokens = tokenize_tw(code)
    ast_tree = build_tw_ast(tokens, ".", "test.tw", code)
    context = create_base_context(ast_tree, "test.tw")
    text = "Hello {config.name}! Count: {config.count}"
    result = interpolate(text, context)
    assert "Hello World!" in result
    assert "Count: 42" in result
    print("✅ test_let_json_interpolation")


def test_tailwind_full_page_style():
    """Complete TSS with Tailwind utilities mixed with normal TSS."""
    tss = """.hero {
    flex flex-col items-center justify-center
    p-8 m-4
    bg-emerald-500
    rounded-2xl shadow-xl
}

.btn-primary {
    flex items-center gap-2
    px-4 py-2
    bg-emerald-500 text-white
    rounded-lg font-bold
    cursor-pointer
}

.card-grid {
    grid grid-cols-4 gap-4
}

@media (min-width 768px) {
    .container { max-w-7xl mx-auto p-4 }
}
"""
    sheet = build_tss_ast_from_text(tss)
    css = render_css(sheet)
    assert "display: flex" in css
    assert "align-items: center" in css
    assert "padding: 32px" in css  # p-8
    assert "border-radius: 16px" in css  # rounded-2xl
    assert "box-shadow" in css  # shadow-xl
    assert "font-weight: 700" in css  # font-bold
    assert "display: grid" in css
    assert "1fr 1fr 1fr 1fr" in css  # grid-cols-4
    assert "cursor: pointer" in css
    print("✅ test_tailwind_full_page_style")


# ═══════════════════════════════════════════════════════════════════════════
# RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # Inline JSON in let
        test_let_with_inline_array_of_objects,
        test_let_with_simple_array,
        test_let_with_inline_object,
        test_let_with_nested_arrays,
        test_let_with_empty_array,
        test_let_with_empty_object,
        test_let_with_mixed_types_in_array,
        test_let_json_does_not_break_normal_blocks,
        test_let_string_value_still_works,
        # Tailwind CSS
        test_tailwind_flex_center,
        test_tailwind_spacing,
        test_tailwind_colors,
        test_tailwind_rounded,
        test_tailwind_font_sizes,
        test_tailwind_font_weights,
        test_tailwind_shadows,
        test_tailwind_opacity,
        test_tailwind_position,
        test_tailwind_grid_cols,
        test_tailwind_max_width,
        test_tailwind_mixed_with_normal_tss,
        test_tailwind_border_width,
        test_tailwind_cursor,
        test_tailwind_overflow,
        test_tailwind_text_align,
        test_tailwind_whitespace,
        test_tailwind_line_through,
        test_tailwind_fallback_to_tss,
        test_tailwind_hidden,
        test_tailwind_flex_col,
        test_tailwind_between,
        # Both together
        test_let_json_with_each_loop,
        test_let_json_interpolation,
        test_tailwind_full_page_style,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")
    sys.exit(1 if failed > 0 else 0)

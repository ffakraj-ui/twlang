"""
Tests for Zero-JS feature — pure static pages should ship 0 KB of framework JS.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tw_framework.framework import build_hidden_site


def _build_page(tw_code):
    """Build a single-page site and return the generated HTML."""
    test_site = tempfile.mkdtemp()
    out_dir = tempfile.mkdtemp()
    home = os.path.join(test_site, "[home]")
    os.makedirs(os.path.join(home, "pages"), exist_ok=True)
    with open(os.path.join(home, "pages", "index.tw"), "w") as f:
        f.write(tw_code)
    build_hidden_site(test_site, out_dir, force=True)
    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "r") as f:
        return f.read()


def _count_framework_js(html):
    """Count framework JS markers in HTML."""
    return {
        "tw_data": "__TW_DATA__" in html,
        "tw_div": 'id="__TW__"' in html,
        "tw_runtime": "/_tw/" in html and "chunks" in html,
        "zero_marker": "Zero-JS" in html,
        "script_tags": len(re.findall(r"<script", html)),
    }


def test_pure_static_page_is_zero_js():
    """A page with only h1 + p should have zero framework JS."""
    html = _build_page('''page {
    title "Test"
    render static
}

body {
    h1 "Hello"
    p "Welcome"
}
''')
    info = _count_framework_js(html)
    assert not info["tw_data"], "__TW_DATA__ should be absent"
    assert not info["tw_div"], "__TW__ div should be absent"
    assert info["zero_marker"], "Zero-JS marker should be present"
    assert info["script_tags"] == 0, f"Expected 0 script tags, got {info['script_tags']}"
    print("✅ test_pure_static_page_is_zero_js")


def test_page_with_state_is_not_zero_js():
    """A page with state vars should have framework JS (reactivity runtime)."""
    html = _build_page('''page {
    title "Test"
    render static
}

state {
    count: number = 0
}

body {
    h1 "Counter"
}
''')
    info = _count_framework_js(html)
    assert info["tw_data"], "__TW_DATA__ should be present for reactive pages"
    print("✅ test_page_with_state_is_not_zero_js")


def test_page_with_events_is_not_zero_js():
    """A page with on:click events should have framework JS."""
    html = _build_page('''page {
    title "Test"
    render static
}

body {
    button { on:click "alert('hi')", "Click Me" }
}
''')
    info = _count_framework_js(html)
    assert info["tw_data"], "__TW_DATA__ should be present for pages with events"
    print("✅ test_page_with_events_is_not_zero_js")


def test_page_with_let_and_each_is_zero_js():
    """A data-driven page with let + each (no state/events) should be Zero-JS."""
    html = _build_page('''page {
    title "Test"
    render static
}

let items = [{"name": "A"}, {"name": "B"}, {"name": "C"}]

body {
    each items as item {
        p "{item.name}"
    }
}
''')
    info = _count_framework_js(html)
    assert not info["tw_data"], "__TW_DATA__ should be absent"
    assert not info["tw_div"], "__TW__ div should be absent"
    assert info["zero_marker"], "Zero-JS marker should be present"
    assert info["script_tags"] == 0, f"Expected 0 script tags, got {info['script_tags']}"
    print("✅ test_page_with_let_and_each_is_zero_js")


def test_page_with_user_script_keeps_user_js():
    """A page with user-written script { ... } should keep the user's JS
    but still skip framework JS (__TW_DATA__, __TW__ div, reactivity runtime)."""
    html = _build_page('''page {
    title "Test"
    render static
}

body {
    h1 "Hello"
    script {
        console.log("user JS");
    }
}
''')
    info = _count_framework_js(html)
    assert not info["tw_data"], "__TW_DATA__ should be absent (Zero-JS)"
    assert not info["tw_div"], "__TW__ div should be absent (Zero-JS)"
    assert info["zero_marker"], "Zero-JS marker should be present"
    # User script should be present (as external chunk or inline)
    assert "console.log" in html or "chunks" in html, "User JS should be in output"
    print("✅ test_page_with_user_script_keeps_user_js")


if __name__ == "__main__":
    test_pure_static_page_is_zero_js()
    test_page_with_state_is_not_zero_js()
    test_page_with_events_is_not_zero_js()
    test_page_with_let_and_each_is_zero_js()
    test_page_with_user_script_keeps_user_js()
    print("\n" + "=" * 60)
    print("Zero-JS tests: 5 passed, 0 failed, 5 total")
    print("=" * 60)

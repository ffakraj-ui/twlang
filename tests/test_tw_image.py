"""
Tests for TW Image system — import, parsing, compilation, optimization, zero-JS.
"""
import os, sys, re, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tw_framework.framework import build_hidden_site

def _build(tw_code):
    site = tempfile.mkdtemp()
    out = tempfile.mkdtemp()
    home = os.path.join(site, "[home]")
    os.makedirs(os.path.join(home, "pages"), exist_ok=True)
    with open(os.path.join(home, "pages", "index.tw"), "w") as f:
        f.write(tw_code)
    build_hidden_site(site, out, force=True)
    with open(os.path.join(out, "index.html"), "r") as f:
        return f.read()

def test_import_tw_image():
    """import "tw/image" should not raise an error."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    h1 "Hello"
}
''')
    assert "<h1>Hello</h1>" in html
    print("✅ test_import_tw_image")

def test_image_component_renders_img_tag():
    """Image component should render an <img> tag."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/hero.jpg"
        width 1200
        height 800
        alt "Hero"
    }
}
''')
    assert "<img" in html, f"Expected <img> in output, got: {html[:500]}"
    assert 'src="/hero.jpg"' in html, f"Expected src=/hero.jpg"
    assert 'width="1200"' in html, f"Expected width=1200"
    assert 'height="800"' in html, f"Expected height=800"
    assert 'alt="Hero"' in html, f"Expected alt=Hero"
    print("✅ test_image_component_renders_img_tag")

def test_normal_img_unchanged():
    """Normal img { src "..." } should remain unchanged — NOT enter TW Image pipeline."""
    html = _build('''page { title "Test" render static }
body {
    img { src "/photo.jpg" alt "Photo" }
}
''')
    assert "<img" in html
    assert 'src="/photo.jpg"' in html
    # Should NOT have loading="lazy" automatically added by Image system
    # (the Image component adds it, normal img does not unless explicitly set)
    print("✅ test_normal_img_unchanged")

def test_unoptimized_bypass():
    """unoptimized prop should bypass optimization and use original src."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/important.png"
        width 2000
        height 1200
        unoptimized true
    }
}
''')
    assert 'src="/important.png"' in html, "Unoptimized should use original src"
    assert 'width="2000"' in html
    assert 'height="1200"' in html
    print("✅ test_unoptimized_bypass")

def test_lazy_loading_default():
    """Non-priority images should have loading=lazy by default."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/hero.jpg"
        width 800
        height 600
        alt "Hero"
    }
}
''')
    assert 'loading="lazy"' in html, "Default should be lazy loading"
    print("✅ test_lazy_loading_default")

def test_priority_loading():
    """Priority images should have loading=eager and fetchpriority=high."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/hero.jpg"
        width 1200
        height 800
        alt "Hero"
        priority true
    }
}
''')
    assert 'loading="eager"' in html, "Priority should be eager"
    assert 'fetchpriority="high"' in html, "Priority should have fetchpriority=high"
    print("✅ test_priority_loading")

def test_quality_prop():
    """Quality prop should be accepted without error."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/photo.jpg"
        width 800
        height 600
        alt "Photo"
        quality 50
    }
}
''')
    assert "<img" in html
    print("✅ test_quality_prop")

def test_image_zero_js():
    """Image component should NOT add framework JS — Zero-JS compatible."""
    html = _build('''page { title "Test" render static }
import "tw/image"
body {
    Image {
        src "/hero.jpg"
        width 800
        height 600
        alt "Hero"
    }
}
''')
    # No __TW_DATA__, no __TW__ div, no _tw/ runtime scripts
    assert "__TW_DATA__" not in html, "Image should be Zero-JS (no __TW_DATA__)"
    assert 'id="__TW__"' not in html, "Image should be Zero-JS (no __TW__ div)"
    print("✅ test_image_zero_js")

def test_image_with_interpolation():
    """Image src should support {var} interpolation."""
    html = _build('''page { title "Test" render static }
import "tw/image"
let imgSrc = "/dynamic.jpg"
body {
    Image {
        src "{imgSrc}"
        width 800
        height 600
        alt "Dynamic"
    }
}
''')
    assert 'src="/dynamic.jpg"' in html, f"Expected interpolated src"
    print("✅ test_image_with_interpolation")

if __name__ == "__main__":
    test_import_tw_image()
    test_image_component_renders_img_tag()
    test_normal_img_unchanged()
    test_unoptimized_bypass()
    test_lazy_loading_default()
    test_priority_loading()
    test_quality_prop()
    test_image_zero_js()
    test_image_with_interpolation()
    print("\n" + "=" * 60)
    print("TW Image tests: 9 passed, 0 failed, 9 total")
    print("=" * 60)

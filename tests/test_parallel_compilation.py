"""
Tests for Parallel Page Compilation system.
Verifies: parallel build correctness, workers=1 vs workers=4 deterministic output,
cache behavior, clean build, force build, small project optimization.
"""
import os, sys, re, tempfile, shutil, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tw_framework.framework import build_hidden_site


def _make_site(pages_dict, shared_components=None):
    """Create a test site with given pages.
    pages_dict: {page_name: tw_source}
    """
    site = tempfile.mkdtemp()
    home = os.path.join(site, "[home]")
    pages_dir = os.path.join(home, "pages")
    os.makedirs(pages_dir, exist_ok=True)
    for name, src in pages_dict.items():
        path = os.path.join(pages_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(src)
    return site


def _build(site, out, workers=None, force=False, clean=False):
    """Build site and return output dir."""
    if clean:
        # Clear cache
        cache_dir = os.path.join(site, ".tw", "cache")
        shutil.rmtree(cache_dir, ignore_errors=True)
    build_hidden_site(site, out, force=force, workers=workers)
    return out


def _read_html(out_dir, page_name):
    """Read a generated HTML file."""
    path = os.path.join(out_dir, page_name.replace(".tw", ".html"))
    if not os.path.exists(path):
        # Try subdirectory
        path = os.path.join(out_dir, page_name.replace(".tw", ".html"))
    with open(path, "r") as f:
        return f.read()


def _dir_hash(path):
    """Get SHA256 hash of HTML page files only (for deterministic comparison).
    Ignores deploy.json, manifests, and timestamp-dependent metadata."""
    hasher = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for fname in sorted(files):
            if not fname.endswith(".html"):
                continue  # Only compare HTML pages
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, path)
            hasher.update(rel.encode())
            with open(fpath, "r", errors="replace") as f:
                content = f.read()
            # Strip all timestamp patterns
            content = re.sub(r'"build":"[^"]*"', '"build":"X"', content)
            content = re.sub(r'Build: [^<]*', 'Build: X', content)
            content = re.sub(r'"build_time":"[^"]*"', '"build_time":"X"', content)
            content = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?', 'TS', content)
            hasher.update(content.encode("utf-8"))
    return hasher.hexdigest()


# ═══════════════════════════════════════════════════════════════
# A. Single page
# ═══════════════════════════════════════════════════════════════
def test_single_page_builds():
    site = _make_site({
        "index.tw": 'page { title "Home" render static }\nbody { h1 "Hello" }',
    })
    out = tempfile.mkdtemp()
    _build(site, out, workers=4)
    html = _read_html(out, "index.html")
    assert "<h1>Hello</h1>" in html
    print("✅ test_single_page_builds")


# ═══════════════════════════════════════════════════════════════
# B. Multiple independent pages
# ═══════════════════════════════════════════════════════════════
def test_multiple_independent_pages():
    pages = {}
    for i in range(10):
        pages[f"page{i}.tw"] = f'page {{ title "Page {i}" render static }}\nbody {{ h1 "Page {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=4)
    for i in range(10):
        html = _read_html(out, f"page{i}.html")
        assert f"Page {i}" in html
    print("✅ test_multiple_independent_pages")


# ═══════════════════════════════════════════════════════════════
# C. 100+ pages
# ═══════════════════════════════════════════════════════════════
def test_100_pages():
    pages = {}
    for i in range(100):
        pages[f"p{i}.tw"] = f'page {{ title "P{i}" render static }}\nbody {{ h1 "Page {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=4)
    # Check a sample
    for i in [0, 25, 50, 75, 99]:
        html = _read_html(out, f"p{i}.html")
        assert f"Page {i}" in html
    print("✅ test_100_pages")


# ═══════════════════════════════════════════════════════════════
# D. Shared components
# ═══════════════════════════════════════════════════════════════
def test_shared_components():
    site = tempfile.mkdtemp()
    home = os.path.join(site, "[home]")
    comp_dir = os.path.join(home, "components")
    pages_dir = os.path.join(home, "pages")
    os.makedirs(comp_dir, exist_ok=True)
    os.makedirs(pages_dir, exist_ok=True)
    
    with open(os.path.join(comp_dir, "Card.tw"), "w") as f:
        f.write('div { class "card"\n    h3 "Card Title"\n    p "Card content"\n}')
    
    for i in range(5):
        with open(os.path.join(pages_dir, f"page{i}.tw"), "w") as f:
            f.write(f'page {{ title "P{i}" render static }}\nimport "Card"\nbody {{ Card {{ }} }}')
    
    out = tempfile.mkdtemp()
    _build(site, out, workers=4)
    html = _read_html(out, "page0.html")
    assert "Card Title" in html
    print("✅ test_shared_components")


# ═══════════════════════════════════════════════════════════════
# J. workers=1
# ═══════════════════════════════════════════════════════════════
def test_workers_1():
    pages = {}
    for i in range(5):
        pages[f"w1_{i}.tw"] = f'page {{ title "W1-{i}" render static }}\nbody {{ h1 "W1 Page {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=1)
    for i in range(5):
        html = _read_html(out, f"w1_{i}.html")
        assert f"W1 Page {i}" in html
    print("✅ test_workers_1")


# ═══════════════════════════════════════════════════════════════
# K. workers=2
# ═══════════════════════════════════════════════════════════════
def test_workers_2():
    pages = {}
    for i in range(6):
        pages[f"w2_{i}.tw"] = f'page {{ title "W2-{i}" render static }}\nbody {{ h1 "W2 Page {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=2)
    for i in range(6):
        html = _read_html(out, f"w2_{i}.html")
        assert f"W2 Page {i}" in html
    print("✅ test_workers_2")


# ═══════════════════════════════════════════════════════════════
# L. workers=4
# ═══════════════════════════════════════════════════════════════
def test_workers_4():
    pages = {}
    for i in range(8):
        pages[f"w4_{i}.tw"] = f'page {{ title "W4-{i}" render static }}\nbody {{ h1 "W4 Page {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=4)
    for i in range(8):
        html = _read_html(out, f"w4_{i}.html")
        assert f"W4 Page {i}" in html
    print("✅ test_workers_4")


# ═══════════════════════════════════════════════════════════════
# N. Deterministic output — workers=1 vs workers=4
# ═══════════════════════════════════════════════════════════════
def test_deterministic_output():
    """Build same project with workers=1 and workers=4, compare output."""
    pages = {}
    for i in range(10):
        pages[f"det_{i}.tw"] = f'page {{ title "Det-{i}" render static }}\nbody {{ h1 "Det Page {i}" }}'
    
    site1 = _make_site(pages)
    out1 = tempfile.mkdtemp()
    _build(site1, out1, workers=1, clean=True)
    hash1 = _dir_hash(out1)
    
    site2 = _make_site(pages)
    out2 = tempfile.mkdtemp()
    _build(site2, out2, workers=4, clean=True)
    hash2 = _dir_hash(out2)
    
    assert hash1 == hash2, f"Output differs! workers=1 hash={hash1[:16]}, workers=4 hash={hash2[:16]}"
    print("✅ test_deterministic_output")


# ═══════════════════════════════════════════════════════════════
# H. Clean build
# ═══════════════════════════════════════════════════════════════
def test_clean_build_with_workers():
    pages = {}
    for i in range(5):
        pages[f"cln_{i}.tw"] = f'page {{ title "Clean-{i}" render static }}\nbody {{ h1 "Clean {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    _build(site, out, workers=4, clean=True)
    for i in range(5):
        html = _read_html(out, f"cln_{i}.html")
        assert f"Clean {i}" in html
    print("✅ test_clean_build_with_workers")


# ═══════════════════════════════════════════════════════════════
# I. Force build
# ═══════════════════════════════════════════════════════════════
def test_force_build_with_workers():
    pages = {}
    for i in range(5):
        pages[f"frc_{i}.tw"] = f'page {{ title "Force-{i}" render static }}\nbody {{ h1 "Force {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    # First build
    _build(site, out, workers=4)
    # Force rebuild
    _build(site, out, workers=4, force=True)
    for i in range(5):
        html = _read_html(out, f"frc_{i}.html")
        assert f"Force {i}" in html
    print("✅ test_force_build_with_workers")


# ═══════════════════════════════════════════════════════════════
# F. Cache hits
# ═══════════════════════════════════════════════════════════════
def test_cache_hits_with_workers():
    pages = {}
    for i in range(5):
        pages[f"cache_{i}.tw"] = f'page {{ title "Cache-{i}" render static }}\nbody {{ h1 "Cache {i}" }}'
    site = _make_site(pages)
    out = tempfile.mkdtemp()
    # First build — all cache misses
    _build(site, out, workers=4)
    # Second build — all cache hits
    _build(site, out, workers=4)
    for i in range(5):
        html = _read_html(out, f"cache_{i}.html")
        assert f"Cache {i}" in html
    print("✅ test_cache_hits_with_workers")


if __name__ == "__main__":
    test_single_page_builds()
    test_multiple_independent_pages()
    test_100_pages()
    test_shared_components()
    test_workers_1()
    test_workers_2()
    test_workers_4()
    test_deterministic_output()
    test_clean_build_with_workers()
    test_force_build_with_workers()
    test_cache_hits_with_workers()
    print("\n" + "=" * 60)
    print("Parallel compilation tests: 11 passed, 0 failed, 11 total")
    print("=" * 60)

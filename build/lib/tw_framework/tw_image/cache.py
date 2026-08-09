"""Image cache for TW Image system."""
import os, hashlib, json, logging
logger = logging.getLogger(__name__)
_CACHE = {}
_CACHE_DIR = ""
_OUTPUT_DIR = ""

def set_cache_dirs(cache_dir, output_dir):
    global _CACHE_DIR, _OUTPUT_DIR
    _CACHE_DIR = cache_dir; _OUTPUT_DIR = output_dir
    os.makedirs(_CACHE_DIR, exist_ok=True)
    os.makedirs(os.path.join(_OUTPUT_DIR, "_tw", "img"), exist_ok=True)

def _cache_key(src, width, quality, fmt):
    return hashlib.sha256(f"{src}:{width}:{quality}:{fmt}".encode()).hexdigest()[:16]

def get_cached(src, width, quality, fmt):
    key = _cache_key(src, width, quality, fmt)
    if src in _CACHE and key in _CACHE[src]: return _CACHE[src][key]
    if _CACHE_DIR:
        dp = os.path.join(_CACHE_DIR, f"{key}.json")
        if os.path.exists(dp):
            try:
                with open(dp) as f: d = json.load(f)
                if src not in _CACHE: _CACHE[src] = {}
                _CACHE[src][key] = d.get("url","")
                return d.get("url","")
            except: pass
    return ""

def set_cached(src, width, quality, fmt, url):
    key = _cache_key(src, width, quality, fmt)
    if src not in _CACHE: _CACHE[src] = {}
    _CACHE[src][key] = url
    if _CACHE_DIR:
        try:
            with open(os.path.join(_CACHE_DIR, f"{key}.json"), "w") as f:
                json.dump({"src":src,"width":width,"quality":quality,"fmt":fmt,"url":url}, f)
        except: logger.debug("Failed to persist image cache", exc_info=True)

def clear_cache(): _CACHE.clear()
def is_cached(src, width, quality, fmt): return bool(get_cached(src, width, quality, fmt))

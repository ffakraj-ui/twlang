"""Image optimizer for TW Image system."""
import os, logging
logger = logging.getLogger(__name__)
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.info("Pillow not available; TW Image will skip pixel-level optimization")
from .formats import get_format_priority, get_extension, is_optimizable
from .cache import get_cached, set_cached, _OUTPUT_DIR

def _resolve_src_path(src, project_root=""):
    if not src: return ""
    if src.startswith(("http://","https://")): return ""
    if os.path.isabs(src) and os.path.exists(src): return src
    for base in [os.path.join(project_root,"public"),
                 os.path.join(project_root,"[home]","public"), project_root]:
        c = os.path.join(base, src.lstrip("/"))
        if os.path.exists(c): return c
    return ""

def optimize_image(src, width, height, quality=75, output_format="webp",
                   project_root="", output_dir=""):
    cached = get_cached(src, width, quality, output_format)
    if cached: return cached
    src_path = _resolve_src_path(src, project_root)
    if not src_path or not os.path.exists(src_path): return src
    if not HAS_PIL or not is_optimizable(src_path): return src
    try:
        with PILImage.open(src_path) as img:
            orig_w, orig_h = img.size
            if width and width < orig_w:
                ratio = width / orig_w
                img = img.resize((width, int(orig_h*ratio)), PILImage.LANCZOS)
            out_dir = output_dir or _OUTPUT_DIR or os.path.dirname(src_path)
            img_out = os.path.join(out_dir, "_tw", "img")
            os.makedirs(img_out, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(src))[0]
            out_name = f"{base_name}_{width}w_q{quality}.{output_format}"
            out_path = os.path.join(img_out, out_name)
            kwargs = {}
            if output_format in ("webp","jpeg"):
                kwargs["quality"] = quality; kwargs["optimize"] = True
            if output_format == "webp": kwargs["method"] = 4
            if output_format in ("jpeg","jpg") and img.mode in ("RGBA","P"):
                img = img.convert("RGB")
            img.save(out_path, format=output_format.upper(), **kwargs)
            url = f"/_tw/img/{out_name}"
            set_cached(src, width, quality, output_format, url)
            return url
    except Exception as e:
        logger.warning(f"TW Image optimization failed for {src}: {e}")
        return src

def generate_srcset(src, width, height, quality, project_root="", output_dir=""):
    if not HAS_PIL: return ""
    src_path = _resolve_src_path(src, project_root)
    if not src_path or not os.path.exists(src_path): return ""
    variants = []
    for mult, label in [(1.0,"1x"),(0.5,"2x"),(0.25,"3x")]:
        tw = int(width * mult)
        if tw < 50: continue
        url = optimize_image(src, tw, int(height*mult) if height else 0,
                             quality, "webp", project_root, output_dir)
        if url and url != src: variants.append(f"{url} {label}")
    return ", ".join(variants) if variants else ""

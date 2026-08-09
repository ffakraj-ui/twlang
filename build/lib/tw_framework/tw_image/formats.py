"""Image format support for TW Image system."""
import os

SUPPORTED_FORMATS = ["webp", "avif", "jpeg", "png", "gif"]
FORMAT_MIME = {"webp":"image/webp","avif":"image/avif","jpeg":"image/jpeg","jpg":"image/jpeg",
               "png":"image/png","gif":"image/gif","svg":"image/svg+xml"}
LOSSY_FORMATS = {"webp","avif","jpeg","jpg"}
LOSSLESS_FORMATS = {"png","gif","svg"}

def get_format_priority(src_path):
    ext = os.path.splitext(src_path)[1].lower().lstrip(".")
    if ext in ("webp","avif"): return [ext]
    if ext == "svg": return ["svg"]
    if ext == "gif": return ["gif"]
    return ["webp","avif", ext if ext in ("jpeg","jpg","png") else "jpeg"]

def get_extension(src_path):
    return os.path.splitext(src_path)[1].lower().lstrip(".")

def is_optimizable(src_path):
    return get_extension(src_path) not in ("svg","gif")

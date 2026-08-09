"""TW Image component — renders optimized <img> HTML."""
import os, logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Set of first-party tw/ component names
BUILTIN_IMAGE_COMPONENTS = {"tw/image", "Image"}

@dataclass
class ImageConfig:
    src: str = ""
    width: int = 0
    height: int = 0
    alt: str = ""
    quality: int = 75
    unoptimized: bool = False
    priority: bool = False
    original_format: bool = False
    loading: str = ""  # override: "lazy" or "eager"
    sizes: str = ""
    cls: str = ""  # CSS class

def _parse_props(props: List[Tuple[str, Any]]) -> ImageConfig:
    cfg = ImageConfig()
    for name, value in props:
        name = name.lower().strip()
        if name == "src": cfg.src = str(value)
        elif name == "width":
            try: cfg.width = int(value)
            except: cfg.width = int(str(value).replace('"','').strip())
        elif name == "height":
            try: cfg.height = int(value)
            except: cfg.height = int(str(value).replace('"','').strip())
        elif name == "alt": cfg.alt = str(value)
        elif name == "quality":
            try: cfg.quality = int(value)
            except: cfg.quality = 75
        elif name == "unoptimized": cfg.unoptimized = bool(value) if not isinstance(value, str) else value.lower() in ("true","1","yes")
        elif name == "priority": cfg.priority = bool(value) if not isinstance(value, str) else value.lower() in ("true","1","yes")
        elif name == "originalformat" or name == "original_format": cfg.original_format = bool(value) if not isinstance(value, str) else value.lower() in ("true","1","yes")
        elif name == "sizes": cfg.sizes = str(value)
        elif name == "class": cfg.cls = str(value)
        elif name == "loading": cfg.loading = str(value)
    return cfg

def render_image_component(props, context=None, project_root="", output_dir=""):
    """Render an Image component to HTML string.
    
    This produces a standard <img> tag with:
    - srcset for responsive images (when optimization available)
    - width/height to prevent layout shift
    - loading="lazy" by default (unless priority)
    - alt text for accessibility
    - No framework JS (Zero-JS compatible)
    """
    cfg = _parse_props(props)
    context = context or {}
    
    # Resolve interpolation
    if "{" in cfg.src and "}" in cfg.src:
        try:
            from ..compiler import interpolate
            cfg.src = interpolate(cfg.src, context)
        except: pass
    if "{" in cfg.alt and "}" in cfg.alt:
        try:
            from ..compiler import interpolate
            cfg.alt = interpolate(cfg.alt, context)
        except: pass
    
    # Build attributes
    attrs = []
    
    if cfg.unoptimized:
        # Bypass optimization — use original src
        attrs.append(f'src="{cfg.src}"')
    else:
        # Try optimization
        from .optimizer import optimize_image, generate_srcset, _resolve_src_path
        from .formats import get_format_priority
        
        src_path = _resolve_src_path(cfg.src, project_root)
        
        if src_path and os.path.exists(src_path):
            # Determine output format
            if cfg.original_format:
                from .formats import get_extension
                fmt = get_extension(cfg.src) or "jpeg"
            else:
                formats = get_format_priority(cfg.src)
                fmt = formats[0] if formats else "webp"
            
            # Optimize
            optimized_url = optimize_image(
                cfg.src, cfg.width, cfg.height,
                cfg.quality, fmt, project_root, output_dir
            )
            attrs.append(f'src="{optimized_url}"')
            
            # Generate srcset for responsive
            srcset = generate_srcset(
                cfg.src, cfg.width, cfg.height,
                cfg.quality, project_root, output_dir
            )
            if srcset:
                attrs.append(f'srcset="{srcset}"')
        else:
            # Can't resolve — use original src
            attrs.append(f'src="{cfg.src}"')
    
    # Width/height for layout shift prevention
    if cfg.width:
        attrs.append(f'width="{cfg.width}"')
    if cfg.height:
        attrs.append(f'height="{cfg.height}"')
    
    # Alt text
    if cfg.alt:
        attrs.append(f'alt="{cfg.alt}"')
    else:
        attrs.append('alt=""')
    
    # Loading strategy
    if cfg.priority:
        attrs.append('loading="eager"')
        attrs.append('fetchpriority="high"')
    elif cfg.loading:
        attrs.append(f'loading="{cfg.loading}"')
    else:
        # Default: lazy loading for non-priority images
        attrs.append('loading="lazy"')
        attrs.append('decoding="async"')
    
    # Sizes attribute
    if cfg.sizes:
        attrs.append(f'sizes="{cfg.sizes}"')
    
    # CSS class
    if cfg.cls:
        attrs.append(f'class="{cfg.cls}"')
    
    return f'<img {" ".join(attrs)}>'

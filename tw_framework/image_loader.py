"""
TW Framework - Custom Image Loader

Implements:
25. Custom Image Loader - Cloudinary, Imgix, etc. integration
"""

from __future__ import annotations

import os
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ImageLoaderConfig:
    """Configuration for an image loader."""
    provider: str = "default"  # default | cloudinary | imgix | vercel | custom
    base_url: str = ""
    default_quality: int = 75
    default_format: str = "auto"  # auto | webp | avif | jpeg | png
    breakpoints: List[int] = field(default_factory=lambda: [640, 750, 828, 1080, 1200, 1920, 2048, 3840])
    device_sizes: List[int] = field(default_factory=lambda: [640, 750, 828, 1080, 1200, 1920, 2048, 3840])
    image_sizes: List[int] = field(default_factory=lambda: [16, 32, 48, 64, 96, 128, 256, 384])
    min_screen_width: int = 320
    lazy_loading: bool = True
    placeholder: str = "blur"  # blur | empty | none
    blur_size: int = 8
    cache_busting: bool = True


class ImageLoader:
    """Custom image loader for optimized image delivery.

    Supports multiple providers:
    - Default: Serves images from the public directory
    - Cloudinary: Uses Cloudinary for on-the-fly transformation
    - Imgix: Uses Imgix for image optimization
    - Vercel: Uses Vercel's image optimization
    - Custom: User-defined loader function
    """

    def __init__(self, config: Optional[ImageLoaderConfig] = None):
        self.config = config or ImageLoaderConfig()
        self._custom_loader: Optional[Callable] = None
        self._loaders: Dict[str, Callable] = {
            "default": self._default_loader,
            "cloudinary": self._cloudinary_loader,
            "imgix": self._imgix_loader,
            "vercel": self._vercel_loader,
        }

    def set_provider(self, provider: str, base_url: str = "") -> None:
        """Set the image provider."""
        self.config.provider = provider
        if base_url:
            self.config.base_url = base_url

    def set_custom_loader(self, loader_fn: Callable[[str, int, int, int], str]) -> None:
        """Set a custom image loader function.

        Args:
            loader_fn: Function(src, width, height, quality) -> URL
        """
        self._custom_loader = loader_fn
        self.config.provider = "custom"

    def get_url(self, src: str, width: int = 0, height: int = 0,
                quality: int = 0) -> str:
        """Get the optimized image URL."""
        q = quality or self.config.default_quality

        if self.config.provider == "custom" and self._custom_loader:
            return self._custom_loader(src, width, height, q)

        loader = self._loaders.get(self.config.provider, self._default_loader)
        return loader(src, width, height, q)

    def get_srcset(self, src: str, widths: Optional[List[int]] = None) -> str:
        """Generate srcset for responsive images."""
        widths = widths or self.config.breakpoints
        parts: List[str] = []

        for w in widths:
            url = self.get_url(src, width=w)
            parts.append(f"{url} {w}w")

        return ", ".join(parts)

    def get_sizes(self, default: str = "100vw",
                  breakpoints: Optional[Dict[int, str]] = None) -> str:
        """Generate sizes attribute."""
        if not breakpoints:
            return default

        parts: List[str] = []
        for width, size in sorted(breakpoints.items(), reverse=True):
            parts.append(f"(max-width: {width}px) {size}")
        parts.append(default)

        return ", ".join(parts)

    def generate_img_tag(self, src: str, alt: str = "",
                         width: int = 0, height: int = 0,
                         quality: int = 0, loading: str = "",
                         sizes: str = "",
                         cls: str = "",
                         priority: bool = False) -> str:
        """Generate a complete <img> tag with optimization."""
        q = quality or self.config.default_quality
        l = loading or ("eager" if priority else ("lazy" if self.config.lazy_loading else "eager"))

        url = self.get_url(src, width, height, q)
        srcset = self.get_srcset(src)
        sizes_attr = sizes or self.get_sizes()

        attrs: List[str] = []
        attrs.append(f'src="{url}"')
        if srcset:
            attrs.append(f'srcset="{srcset}"')
        if sizes_attr:
            attrs.append(f'sizes="{sizes_attr}"')
        attrs.append(f'alt="{alt}"')
        if width:
            attrs.append(f'width="{width}"')
        if height:
            attrs.append(f'height="{height}"')
        attrs.append(f'loading="{l}"')
        if priority:
            attrs.append('fetchpriority="high"')
        if cls:
            attrs.append(f'class="{cls}"')
        attrs.append('decoding="async"')

        return f"<img {' '.join(attrs)}>"

    def _default_loader(self, src: str, width: int, height: int, quality: int) -> str:
        """Default loader - serves from public directory with query params."""
        if not self.config.base_url:
            return src

        params: List[str] = []
        if width: params.append(f"w={width}")
        if height: params.append(f"h={height}")
        if quality: params.append(f"q={quality}")
        params.append(f"f={self.config.default_format}")

        sep = "&" if "?" in src else "?"
        return f"{src}{sep}{'&'.join(params)}"

    def _cloudinary_loader(self, src: str, width: int, height: int, quality: int) -> str:
        """Cloudinary image loader."""
        base = self.config.base_url or "https://res.cloudinary.com"
        transformations: List[str] = []

        if width:
            transformations.append(f"w_{width}")
        if height:
            transformations.append(f"h_{height}")
        transformations.append(f"q_{quality}")
        transformations.append(f"f_{self.config.default_format}")
        transformations.append("c_limit")

        # If src is a full URL, use fetch; otherwise use upload
        if src.startswith("http"):
            return f"{base}/image/fetch/{','.join(transformations)}/{src}"
        else:
            return f"{base}/image/upload/{','.join(transformations)}/{src.lstrip('/')}"

    def _imgix_loader(self, src: str, width: int, height: int, quality: int) -> str:
        """Imgix image loader."""
        base = self.config.base_url or "https://assets.imgix.net"

        params: Dict[str, str] = {
            "w": str(width) if width else "auto",
            "h": str(height) if height else "auto",
            "q": str(quality),
            "auto": "format,compress",
        }

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        sep = "&" if "?" in src else "?"
        return f"{base}/{src.lstrip('/')}{sep}{param_str}"

    def _vercel_loader(self, src: str, width: int, height: int, quality: int) -> str:
        """Vercel image optimization loader."""
        params = {
            "w": str(width) if width else "0",
            "q": str(quality),
        }
        if height:
            params["h"] = str(height)

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        encoded_src = src.replace("?", "%3F").replace("&", "%26")
        return f"/_vercel/image?url={encoded_src}&{param_str}"

    def get_blur_placeholder(self, src: str) -> str:
        """Generate a blur data URL for placeholder."""
        url = self.get_url(src, width=self.config.blur_size, quality=10)
        # In real implementation, this would fetch and base64 encode
        return f"data:image/svg+xml;base64,{hashlib.md5(src.encode()).hexdigest()[:20]}"

    def get_info(self) -> Dict[str, Any]:
        return {
            "provider": self.config.provider,
            "base_url": self.config.base_url,
            "default_quality": self.config.default_quality,
            "default_format": self.config.default_format,
            "breakpoints": self.config.breakpoints,
            "lazy_loading": self.config.lazy_loading,
            "placeholder": self.config.placeholder,
        }


__all__ = ["ImageLoaderConfig", "ImageLoader"]

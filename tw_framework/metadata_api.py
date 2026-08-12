"""
TW Framework - Metadata API

Implements:
34. Metadata API (Extensive) - Open Graph, Twitter Cards, JSON-LD,
    robots, canonical URLs, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class OpenGraphMetadata:
    """Open Graph protocol metadata."""
    title: str = ""
    description: str = ""
    url: str = ""
    site_name: str = ""
    image: str = ""
    image_alt: str = ""
    image_width: int = 0
    image_height: int = 0
    type: str = "website"  # website | article | product | profile
    locale: str = "en_US"
    video: str = ""
    audio: str = ""

    def to_html(self) -> str:
        """Generate Open Graph meta tags."""
        tags: List[str] = []
        if self.title:
            tags.append(f'<meta property="og:title" content="{self.title}">')
        if self.description:
            tags.append(f'<meta property="og:description" content="{self.description}">')
        if self.url:
            tags.append(f'<meta property="og:url" content="{self.url}">')
        if self.site_name:
            tags.append(f'<meta property="og:site_name" content="{self.site_name}">')
        if self.image:
            tags.append(f'<meta property="og:image" content="{self.image}">')
        if self.image_alt:
            tags.append(f'<meta property="og:image:alt" content="{self.image_alt}">')
        if self.image_width:
            tags.append(f'<meta property="og:image:width" content="{self.image_width}">')
        if self.image_height:
            tags.append(f'<meta property="og:image:height" content="{self.image_height}">')
        tags.append(f'<meta property="og:type" content="{self.type}">')
        tags.append(f'<meta property="og:locale" content="{self.locale}">')
        if self.video:
            tags.append(f'<meta property="og:video" content="{self.video}">')
        if self.audio:
            tags.append(f'<meta property="og:audio" content="{self.audio}">')
        return "\n".join(tags)


@dataclass
class TwitterCardMetadata:
    """Twitter Card metadata."""
    card: str = "summary"  # summary | summary_large_image | app | player
    site: str = ""  # @username
    creator: str = ""  # @username
    title: str = ""
    description: str = ""
    image: str = ""
    image_alt: str = ""
    player: str = ""
    player_width: int = 0
    player_height: int = 0
    app_name_iphone: str = ""
    app_name_ipad: str = ""
    app_name_googleplay: str = ""
    app_id_iphone: str = ""
    app_id_ipad: str = ""
    app_id_googleplay: str = ""

    def to_html(self) -> str:
        tags: List[str] = []
        tags.append(f'<meta name="twitter:card" content="{self.card}">')
        if self.site:
            tags.append(f'<meta name="twitter:site" content="{self.site}">')
        if self.creator:
            tags.append(f'<meta name="twitter:creator" content="{self.creator}">')
        if self.title:
            tags.append(f'<meta name="twitter:title" content="{self.title}">')
        if self.description:
            tags.append(f'<meta name="twitter:description" content="{self.description}">')
        if self.image:
            tags.append(f'<meta name="twitter:image" content="{self.image}">')
        if self.image_alt:
            tags.append(f'<meta name="twitter:image:alt" content="{self.image_alt}">')
        if self.player:
            tags.append(f'<meta name="twitter:player" content="{self.player}">')
            if self.player_width:
                tags.append(f'<meta name="twitter:player:width" content="{self.player_width}">')
            if self.player_height:
                tags.append(f'<meta name="twitter:player:height" content="{self.player_height}">')
        if self.app_name_iphone:
            tags.append(f'<meta name="twitter:app:name:iphone" content="{self.app_name_iphone}">')
        if self.app_id_iphone:
            tags.append(f'<meta name="twitter:app:id:iphone" content="{self.app_id_iphone}">')
        return "\n".join(tags)


@dataclass
class JSONLDData:
    """JSON-LD structured data."""
    type: str = "WebPage"  # Schema.org type
    data: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        obj = {"@context": "https://schema.org", "@type": self.type}
        obj.update(self.data)
        return json.dumps(obj)

    def to_html(self) -> str:
        return f'<script type="application/ld+json">{self.to_json()}</script>'


@dataclass
class RobotsMetadata:
    """Robots meta directives."""
    index: bool = True
    follow: bool = True
    noarchive: bool = False
    nosnippet: bool = False
    noimageindex: bool = False
    nocache: bool = False
    unavailable_after: str = ""  # RFC 850 date format
    max_snippet: int = -1
    max_image_preview: str = ""  # none | standard | large
    max_video_preview: int = -1
    sitemap: str = ""

    def to_html(self) -> str:
        directives: List[str] = []
        directives.append("index" if self.index else "noindex")
        directives.append("follow" if self.follow else "nofollow")
        if self.noarchive: directives.append("noarchive")
        if self.nosnippet: directives.append("nosnippet")
        if self.noimageindex: directives.append("noimageindex")
        if self.nocache: directives.append("nocache")
        if self.unavailable_after:
            directives.append(f'unavailable_after: {self.unavailable_after}')
        if self.max_snippet >= 0:
            directives.append(f'max-snippet:{self.max_snippet}')
        if self.max_image_preview:
            directives.append(f'max-image-preview:{self.max_image_preview}')
        if self.max_video_preview >= 0:
            directives.append(f'max-video-preview:{self.max_video_preview}')

        tags = [f'<meta name="robots" content="{", ".join(directives)}">']
        if self.sitemap:
            tags.append(f'<link rel="sitemap" type="application/xml" href="{self.sitemap}">')
        return "\n".join(tags)


@dataclass
class CanonicalMetadata:
    """Canonical URL and alternate links."""
    canonical: str = ""
    alternates: Dict[str, str] = field(default_factory=dict)  # hreflang -> URL
    prev: str = ""
    next: str = ""
    shortlink: str = ""
    amphtml: str = ""

    def to_html(self) -> str:
        tags: List[str] = []
        if self.canonical:
            tags.append(f'<link rel="canonical" href="{self.canonical}">')
        for hreflang, url in self.alternates.items():
            tags.append(f'<link rel="alternate" hreflang="{hreflang}" href="{url}">')
        if self.prev:
            tags.append(f'<link rel="prev" href="{self.prev}">')
        if self.next:
            tags.append(f'<link rel="next" href="{self.next}">')
        if self.shortlink:
            tags.append(f'<link rel="shortlink" href="{self.shortlink}">')
        if self.amphtml:
            tags.append(f'<link rel="amphtml" href="{self.amphtml}">')
        return "\n".join(tags)


@dataclass
class PageMetadata:
    """Complete page metadata.

    Combines all metadata types into a single object that can be
    used to generate all meta tags for a page.
    """
    title: str = ""
    title_template: str = "%s | TW App"
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    author: str = ""
    generator: str = "TW Framework"
    application_name: str = ""
    referrer: str = "origin-when-cross-origin"
    theme_color: str = ""
    color_scheme: str = ""  # light | dark | light dark
    viewport: str = "width=device-width, initial-scale=1"
    charset: str = "utf-8"

    open_graph: Optional[OpenGraphMetadata] = None
    twitter: Optional[TwitterCardMetadata] = None
    json_ld: List[JSONLDData] = field(default_factory=list)
    robots: Optional[RobotsMetadata] = None
    canonical: Optional[CanonicalMetadata] = None

    custom_meta: Dict[str, str] = field(default_factory=dict)
    custom_links: List[Dict[str, str]] = field(default_factory=list)

    def set_title(self, title: str) -> None:
        """Set the page title (applies template if set)."""
        if self.title_template and "%s" in self.title_template:
            self.title = self.title_template % title
        else:
            self.title = title

    def add_json_ld(self, schema_type: str, data: Dict[str, Any]) -> None:
        """Add JSON-LD structured data."""
        self.json_ld.append(JSONLDData(type=schema_type, data=data))

    def set_open_graph(self, **kwargs) -> OpenGraphMetadata:
        """Set Open Graph metadata."""
        self.open_graph = OpenGraphMetadata(**kwargs)
        return self.open_graph

    def set_twitter(self, **kwargs) -> TwitterCardMetadata:
        """Set Twitter Card metadata."""
        self.twitter = TwitterCardMetadata(**kwargs)
        return self.twitter

    def set_robots(self, **kwargs) -> RobotsMetadata:
        """Set robots metadata."""
        self.robots = RobotsMetadata(**kwargs)
        return self.robots

    def set_canonical(self, url: str, **kwargs) -> CanonicalMetadata:
        """Set canonical URL."""
        kwargs["canonical"] = url
        self.canonical = CanonicalMetadata(**kwargs)
        return self.canonical

    def add_custom_meta(self, name: str, content: str) -> None:
        """Add a custom meta tag."""
        self.custom_meta[name] = content

    def add_custom_link(self, rel: str, href: str, **attrs) -> None:
        """Add a custom link tag."""
        link = {"rel": rel, "href": href}
        link.update(attrs)
        self.custom_links.append(link)

    def to_html(self) -> str:
        """Generate all meta tags as HTML."""
        tags: List[str] = []

        # Charset
        tags.append(f'<meta charset="{self.charset}">')

        # Viewport
        if self.viewport:
            tags.append(f'<meta name="viewport" content="{self.viewport}">')

        # Title
        if self.title:
            tags.append(f'<title>{self.title}</title>')

        # Description
        if self.description:
            tags.append(f'<meta name="description" content="{self.description}">')

        # Keywords
        if self.keywords:
            tags.append(f'<meta name="keywords" content="{", ".join(self.keywords)}">')

        # Author
        if self.author:
            tags.append(f'<meta name="author" content="{self.author}">')

        # Generator
        tags.append(f'<meta name="generator" content="{self.generator}">')

        # Application name
        if self.application_name:
            tags.append(f'<meta name="application-name" content="{self.application_name}">')

        # Referrer
        tags.append(f'<meta name="referrer" content="{self.referrer}">')

        # Theme color
        if self.theme_color:
            tags.append(f'<meta name="theme-color" content="{self.theme_color}">')

        # Color scheme
        if self.color_scheme:
            tags.append(f'<meta name="color-scheme" content="{self.color_scheme}">')

        # Open Graph
        if self.open_graph:
            tags.append(self.open_graph.to_html())

        # Twitter
        if self.twitter:
            tags.append(self.twitter.to_html())

        # JSON-LD
        for ld in self.json_ld:
            tags.append(ld.to_html())

        # Robots
        if self.robots:
            tags.append(self.robots.to_html())

        # Canonical
        if self.canonical:
            tags.append(self.canonical.to_html())

        # Custom meta
        for name, content in self.custom_meta.items():
            tags.append(f'<meta name="{name}" content="{content}">')

        # Custom links
        for link in self.custom_links:
            attrs = " ".join(f'{k}="{v}"' for k, v in link.items())
            tags.append(f'<link {attrs}>')

        return "\n".join(tags)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "keywords": self.keywords,
            "author": self.author,
            "open_graph": self.open_graph.__dict__ if self.open_graph else None,
            "twitter": self.twitter.__dict__ if self.twitter else None,
            "json_ld": [{"type": j.type, "data": j.data} for j in self.json_ld],
            "robots": self.robots.__dict__ if self.robots else None,
            "canonical": self.canonical.__dict__ if self.canonical else None,
        }


class MetadataRegistry:
    """Registry of metadata for all routes.

    Stores PageMetadata for each route and provides:
    - Route-specific metadata
    - Default/fallback metadata
    - Metadata inheritance (child routes inherit parent metadata)
    - Bulk export for build-time generation
    """

    def __init__(self):
        self._metadata: Dict[str, PageMetadata] = {}
        self._default = PageMetadata()
        self._inheritance: Dict[str, str] = {}  # child route -> parent route

    def set_default(self, metadata: PageMetadata) -> None:
        self._default = metadata

    def set_route(self, route: str, metadata: PageMetadata) -> None:
        self._metadata[route] = metadata

    def get_route(self, route: str) -> PageMetadata:
        """Get metadata for a route, with inheritance."""
        if route in self._metadata:
            return self._metadata[route]

        # Check inheritance
        parent = self._inheritance.get(route)
        if parent and parent in self._metadata:
            return self._metadata[parent]

        return self._default

    def set_inheritance(self, child_route: str, parent_route: str) -> None:
        self._inheritance[child_route] = parent_route

    def export_all(self) -> Dict[str, Dict[str, Any]]:
        return {route: meta.to_dict() for route, meta in self._metadata.items()}

    def get_all_routes(self) -> List[str]:
        return list(self._metadata.keys())


__all__ = [
    "OpenGraphMetadata", "TwitterCardMetadata", "JSONLDData",
    "RobotsMetadata", "CanonicalMetadata", "PageMetadata",
    "MetadataRegistry",
]

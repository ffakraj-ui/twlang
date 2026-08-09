"""
Metadata and SEO management for tw/metadata.

Provides structured metadata generation: Open Graph, Twitter Cards,
JSON-LD, canonical URLs, and sitemap generation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MetaTag:
    """A single meta tag."""
    attr: str  # "name" or "property"
    key: str   # tag key
    content: str

    def to_html(self) -> str:
        return f'  <meta {self.attr}="{self.key}" content="{self.content}">'


class MetadataManager:
    """Manages page-level and site-level metadata."""

    def __init__(self):
        self._title: str = ""
        self._description: str = ""
        self._canonical: str = ""
        self._og: Dict[str, str] = {}
        self._twitter: Dict[str, str] = {}
        self._json_ld: List[Dict[str, Any]] = []
        self._robots: str = ""
        self._extra: List[MetaTag] = []

    def set_title(self, title: str) -> None:
        self._title = title

    def set_description(self, desc: str) -> None:
        self._description = desc

    def set_canonical(self, url: str) -> None:
        self._canonical = url

    def set_og(self, key: str, value: str) -> None:
        self._og[key] = value

    def set_twitter(self, key: str, value: str) -> None:
        self._twitter[key] = value

    def add_json_ld(self, data: Dict[str, Any]) -> None:
        self._json_ld.append(data)

    def set_robots(self, directive: str) -> None:
        self._robots = directive

    def add_meta(self, attr: str, key: str, content: str) -> None:
        self._extra.append(MetaTag(attr=attr, key=key, content=content))

    def generate_meta_tags(self) -> str:
        """Generate all meta tags as HTML."""
        lines = []

        if self._description:
            lines.append(f'  <meta name="description" content="{self._description}">')
        if self._canonical:
            lines.append(f'  <link rel="canonical" href="{self._canonical}">')
        if self._robots:
            lines.append(f'  <meta name="robots" content="{self._robots}">')

        for key, value in self._og.items():
            lines.append(f'  <meta property="og:{key}" content="{value}">')
        for key, value in self._twitter.items():
            lines.append(f'  <meta name="twitter:{key}" content="{value}">')

        for tag in self._extra:
            lines.append(tag.to_html())

        for data in self._json_ld:
            lines.append(f'  <script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>')

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self._title,
            "description": self._description,
            "canonical": self._canonical,
            "og": self._og,
            "twitter": self._twitter,
            "robots": self._robots,
        }


def generate_meta_tags(metadata: Dict[str, Any]) -> str:
    """Generate meta tags from a metadata dict."""
    mgr = MetadataManager()
    mgr.set_title(metadata.get("title", ""))
    mgr.set_description(metadata.get("description", ""))
    mgr.set_canonical(metadata.get("canonical", ""))

    for key, value in metadata.get("og", {}).items():
        mgr.set_og(key, value)
    for key, value in metadata.get("twitter", {}).items():
        mgr.set_twitter(key, value)

    return mgr.generate_meta_tags()


def generate_sitemap(pages: List[Dict[str, Any]], base_url: str = "") -> str:
    """Generate a sitemap.xml from a list of pages."""
    urls = []
    for page in pages:
        route = page.get("route", page.get("path", ""))
        if base_url:
            loc = f"{base_url.rstrip('/')}{route}"
        else:
            loc = route
        lastmod = page.get("updated_at", "")
        changefreq = page.get("changefreq", "weekly")
        priority = page.get("priority", "0.8")
        urls.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


__all__ = ["MetaTag", "MetadataManager", "generate_meta_tags", "generate_sitemap"]

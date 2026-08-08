"""
Tailwind CSS utility class → CSS property:value mapping.

Allows writing Tailwind classes directly in .tss files:
    .card { flex items-center gap-2 p-4 rounded-lg }
Expands to:
    .card { display: flex; align-items: center; gap: 8px; padding: 16px; border-radius: 8px; }

If a line is NOT all-Tailwind, falls back to normal TSS parsing.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

Decl = Tuple[str, str]

# ─── Spacing scale (Tailwind default: 1 unit = 4px) ─────────────────────────
SPACING = {
    "0": "0", "px": "1px",
    "0.5": "2px", "1": "4px", "1.5": "6px",
    "2": "8px", "2.5": "10px", "3": "12px",
    "3.5": "14px", "4": "16px", "5": "20px",
    "6": "24px", "7": "28px", "8": "32px",
    "9": "36px", "10": "40px", "11": "44px",
    "12": "48px", "14": "56px", "16": "64px",
    "20": "80px", "24": "96px", "28": "112px",
    "32": "128px", "36": "144px", "40": "160px",
    "44": "176px", "48": "192px", "52": "208px",
    "56": "224px", "60": "240px", "64": "256px",
    "72": "288px", "80": "320px", "96": "384px",
}

# ─── Color palette ─────────────────────────────────────────────────────────
COLORS = {
    "slate":   {"50":"#f8fafc","100":"#f1f5f9","200":"#e2e8f0","300":"#cbd5e1","400":"#94a3b8","500":"#64748b","600":"#475569","700":"#334155","800":"#1e293b","900":"#0f172a","950":"#020617"},
    "gray":    {"50":"#f9fafb","100":"#f3f4f6","200":"#e5e7eb","300":"#d1d5db","400":"#9ca3af","500":"#6b7280","600":"#4b5563","700":"#374151","800":"#1f2937","900":"#111827","950":"#030712"},
    "zinc":    {"50":"#fafafa","100":"#f4f4f5","200":"#e4e4e7","300":"#d4d4d8","400":"#a1a1aa","500":"#71717a","600":"#52525b","700":"#3f3f46","800":"#27272a","900":"#18181b","950":"#09090b"},
    "neutral": {"50":"#fafafa","100":"#f5f5f5","200":"#e5e5e5","300":"#d4d4d4","400":"#a3a3a3","500":"#737373","600":"#525252","700":"#404040","800":"#262626","900":"#171717","950":"#0a0a0a"},
    "stone":   {"50":"#fafaf9","100":"#f5f5f4","200":"#e7e5e4","300":"#d6d3d1","400":"#a8a29e","500":"#78716c","600":"#57534e","700":"#44403c","800":"#292524","900":"#1c1917","950":"#0c0a09"},
    "red":     {"50":"#fef2f2","100":"#fee2e2","200":"#fecaca","300":"#fca5a5","400":"#f87171","500":"#ef4444","600":"#dc2626","700":"#b91c1c","800":"#991b1b","900":"#7f1d1d","950":"#450a0a"},
    "orange":  {"50":"#fff7ed","100":"#ffedd5","200":"#fed7aa","300":"#fdba74","400":"#fb923c","500":"#f97316","600":"#ea580c","700":"#c2410c","800":"#9a3412","900":"#7c2d12","950":"#431407"},
    "amber":   {"50":"#fffbeb","100":"#fef3c7","200":"#fde68a","300":"#fcd34d","400":"#fbbf24","500":"#f59e0b","600":"#d97706","700":"#b45309","800":"#92400e","900":"#78350f","950":"#451a03"},
    "yellow":  {"50":"#fefce8","100":"#fef9c3","200":"#fef08a","300":"#fde047","400":"#facc15","500":"#eab308","600":"#ca8a04","700":"#a16207","800":"#854d0e","900":"#713f12","950":"#422006"},
    "lime":    {"50":"#f7fee7","100":"#ecfccb","200":"#d9f99d","300":"#bef264","400":"#a3e635","500":"#84cc16","600":"#65a30d","700":"#4d7c0f","800":"#3f6212","900":"#365314","950":"#1a2e05"},
    "green":   {"50":"#f0fdf4","100":"#dcfce7","200":"#bbf7d0","300":"#86efac","400":"#4ade80","500":"#22c55e","600":"#16a34a","700":"#15803d","800":"#166534","900":"#14532d","950":"#052e16"},
    "emerald": {"50":"#ecfdf5","100":"#d1fae5","200":"#a7f3d0","300":"#6ee7b7","400":"#34d399","500":"#10b981","600":"#059669","700":"#047857","800":"#065f46","900":"#064e3b","950":"#022c22"},
    "teal":    {"50":"#f0fdfa","100":"#ccfbf1","200":"#99f6e4","300":"#5eead4","400":"#2dd4bf","500":"#14b8a6","600":"#0d9488","700":"#0f766e","800":"#115e59","900":"#134e4a","950":"#042f2e"},
    "cyan":    {"50":"#ecfeff","100":"#cffafe","200":"#a5f3fc","300":"#67e8f9","400":"#22d3ee","500":"#06b6d4","600":"#0891b2","700":"#0e7490","800":"#155e75","900":"#164e63","950":"#083344"},
    "sky":     {"50":"#f0f9ff","100":"#e0f2fe","200":"#bae6fd","300":"#7dd3fc","400":"#38bdf8","500":"#0ea5e9","600":"#0284c7","700":"#0369a1","800":"#075985","900":"#0c4a6e","950":"#082f49"},
    "blue":    {"50":"#eff6ff","100":"#dbeafe","200":"#bfdbfe","300":"#93c5fd","400":"#60a5fa","500":"#3b82f6","600":"#2563eb","700":"#1d4ed8","800":"#1e40af","900":"#1e3a8a","950":"#172554"},
    "indigo":  {"50":"#eef2ff","100":"#e0e7ff","200":"#c7d2fe","300":"#a5b4fc","400":"#818cf8","500":"#6366f1","600":"#4f46e5","700":"#4338ca","800":"#3730a3","900":"#312e81","950":"#1e1b4b"},
    "violet":  {"50":"#f5f3ff","100":"#ede9fe","200":"#ddd6fe","300":"#c4b5fd","400":"#a78bfa","500":"#8b5cf6","600":"#7c3aed","700":"#6d28d9","800":"#5b21b6","900":"#4c1d95","950":"#2e1065"},
    "purple":  {"50":"#faf5ff","100":"#f3e8ff","200":"#e9d5ff","300":"#d8b4fe","400":"#c084fc","500":"#a855f7","600":"#9333ea","700":"#7e22ce","800":"#6b21a8","900":"#581c87","950":"#3b0764"},
    "fuchsia": {"50":"#fdf4ff","100":"#fae8ff","200":"#f5d0fe","300":"#f0abfc","400":"#e879f9","500":"#d946ef","600":"#c026d3","700":"#a21caf","800":"#86198f","900":"#701a75","950":"#4a044e"},
    "pink":    {"50":"#fdf2f8","100":"#fce7f3","200":"#fbcfe8","300":"#f9a8d4","400":"#f472b6","500":"#ec4899","600":"#db2777","700":"#be185d","800":"#9d174d","900":"#831843","950":"#500724"},
    "rose":    {"50":"#fff1f2","100":"#ffe4e6","200":"#fecdd3","300":"#fda4af","400":"#fb7185","500":"#f43f5e","600":"#e11d48","700":"#be123c","800":"#9f1239","900":"#881337","950":"#4c0519"},
    "white":   {"500":"#ffffff"},
    "black":   {"500":"#000000"},
    "transparent": {"500":"transparent"},
    "inherit": {"500":"inherit"},
    "current": {"500":"currentColor"},
}

# ─── Static utility classes ────────────────────────────────────────────────
STATIC_MAP: dict[str, Decl] = {
    # Display
    "block": ("display", "block"),
    "inline-block": ("display", "inline-block"),
    "inline": ("display", "inline"),
    "flex": ("display", "flex"),
    "inline-flex": ("display", "inline-flex"),
    "table": ("display", "table"),
    "grid": ("display", "grid"),
    "inline-grid": ("display", "inline-grid"),
    "hidden": ("display", "none"),
    "contents": ("display", "contents"),

    # Flex direction
    "flex-row": ("flex-direction", "row"),
    "flex-row-reverse": ("flex-direction", "row-reverse"),
    "flex-col": ("flex-direction", "column"),
    "flex-col-reverse": ("flex-direction", "column-reverse"),

    # Flex wrap
    "flex-wrap": ("flex-wrap", "wrap"),
    "flex-wrap-reverse": ("flex-wrap", "wrap-reverse"),
    "flex-nowrap": ("flex-wrap", "nowrap"),

    # Align items
    "items-start": ("align-items", "flex-start"),
    "items-end": ("align-items", "flex-end"),
    "items-center": ("align-items", "center"),
    "items-baseline": ("align-items", "baseline"),
    "items-stretch": ("align-items", "stretch"),

    # Justify content
    "justify-start": ("justify-content", "flex-start"),
    "justify-end": ("justify-content", "flex-end"),
    "justify-center": ("justify-content", "center"),
    "justify-between": ("justify-content", "space-between"),
    "justify-around": ("justify-content", "space-around"),
    "justify-evenly": ("justify-content", "space-evenly"),

    # Align self
    "self-auto": ("align-self", "auto"),
    "self-start": ("align-self", "flex-start"),
    "self-end": ("align-self", "flex-end"),
    "self-center": ("align-self", "center"),
    "self-stretch": ("align-self", "stretch"),

    # Flex grow/shrink
    "flex-1": ("flex", "1 1 0%"),
    "flex-auto": ("flex", "1 1 auto"),
    "flex-initial": ("flex", "0 1 auto"),
    "flex-none": ("flex", "none"),
    "grow": ("flex-grow", "1"),
    "grow-0": ("flex-grow", "0"),
    "shrink": ("flex-shrink", "1"),
    "shrink-0": ("flex-shrink", "0"),

    # Position
    "static": ("position", "static"),
    "fixed": ("position", "fixed"),
    "absolute": ("position", "absolute"),
    "relative": ("position", "relative"),
    "sticky": ("position", "sticky"),

    # Text align
    "text-left": ("text-align", "left"),
    "text-center": ("text-align", "center"),
    "text-right": ("text-align", "right"),
    "text-justify": ("text-align", "justify"),

    # Text decoration
    "underline": ("text-decoration", "underline"),
    "line-through": ("text-decoration", "line-through"),
    "no-underline": ("text-decoration", "none"),

    # Text transform
    "uppercase": ("text-transform", "uppercase"),
    "lowercase": ("text-transform", "lowercase"),
    "capitalize": ("text-transform", "capitalize"),
    "normal-case": ("text-transform", "none"),

    # Font weight
    "font-thin": ("font-weight", "100"),
    "font-extralight": ("font-weight", "200"),
    "font-light": ("font-weight", "300"),
    "font-normal": ("font-weight", "400"),
    "font-medium": ("font-weight", "500"),
    "font-semibold": ("font-weight", "600"),
    "font-bold": ("font-weight", "700"),
    "font-extrabold": ("font-weight", "800"),
    "font-black": ("font-weight", "900"),

    # Font style
    "italic": ("font-style", "italic"),
    "not-italic": ("font-style", "normal"),

    # Overflow
    "overflow-auto": ("overflow", "auto"),
    "overflow-hidden": ("overflow", "hidden"),
    "overflow-visible": ("overflow", "visible"),
    "overflow-scroll": ("overflow", "scroll"),
    "overflow-x-auto": ("overflow-x", "auto"),
    "overflow-y-auto": ("overflow-y", "auto"),
    "overflow-x-hidden": ("overflow-x", "hidden"),
    "overflow-y-hidden": ("overflow-y", "hidden"),

    # White space
    "whitespace-normal": ("white-space", "normal"),
    "whitespace-nowrap": ("white-space", "nowrap"),
    "whitespace-pre": ("white-space", "pre"),
    "whitespace-pre-wrap": ("white-space", "pre-wrap"),

    # Word break
    "break-normal": ("word-break", "normal"),
    "break-words": ("overflow-wrap", "break-word"),
    "break-all": ("word-break", "break-all"),

    # Cursor
    "cursor-auto": ("cursor", "auto"),
    "cursor-default": ("cursor", "default"),
    "cursor-pointer": ("cursor", "pointer"),
    "cursor-wait": ("cursor", "wait"),
    "cursor-text": ("cursor", "text"),
    "cursor-move": ("cursor", "move"),
    "cursor-not-allowed": ("cursor", "not-allowed"),

    # Pointer events
    "pointer-events-none": ("pointer-events", "none"),
    "pointer-events-auto": ("pointer-events", "auto"),

    # User select
    "select-none": ("user-select", "none"),
    "select-text": ("user-select", "text"),
    "select-all": ("user-select", "all"),

    # Float
    "float-right": ("float", "right"),
    "float-left": ("float", "left"),
    "float-none": ("float", "none"),

    # Clear
    "clear-left": ("clear", "left"),
    "clear-right": ("clear", "right"),
    "clear-both": ("clear", "both"),

    # Box sizing
    "box-border": ("box-sizing", "border-box"),
    "box-content": ("box-sizing", "content-box"),

    # Border style
    "border-solid": ("border-style", "solid"),
    "border-dashed": ("border-style", "dashed"),
    "border-dotted": ("border-style", "dotted"),
    "border-none": ("border-style", "none"),

    # Opacity (static)
    "opacity-0": ("opacity", "0"),
    "opacity-5": ("opacity", "0.05"),
    "opacity-10": ("opacity", "0.1"),
    "opacity-20": ("opacity", "0.2"),
    "opacity-25": ("opacity", "0.25"),
    "opacity-30": ("opacity", "0.3"),
    "opacity-40": ("opacity", "0.4"),
    "opacity-50": ("opacity", "0.5"),
    "opacity-60": ("opacity", "0.6"),
    "opacity-70": ("opacity", "0.7"),
    "opacity-75": ("opacity", "0.75"),
    "opacity-80": ("opacity", "0.8"),
    "opacity-90": ("opacity", "0.9"),
    "opacity-100": ("opacity", "1"),

    # Visibility
    "visible": ("visibility", "visible"),
    "invisible": ("visibility", "hidden"),

    # Z-index (static common values)
    "z-0": ("z-index", "0"),
    "z-10": ("z-index", "10"),
    "z-20": ("z-index", "20"),
    "z-30": ("z-index", "30"),
    "z-40": ("z-index", "40"),
    "z-50": ("z-index", "50"),
    "z-auto": ("z-index", "auto"),
}

# ─── Font sizes ─────────────────────────────────────────────────────────────
FONT_SIZES = {
    "text-xs": ("font-size", "12px"),
    "text-sm": ("font-size", "14px"),
    "text-base": ("font-size", "16px"),
    "text-lg": ("font-size", "18px"),
    "text-xl": ("font-size", "20px"),
    "text-2xl": ("font-size", "24px"),
    "text-3xl": ("font-size", "30px"),
    "text-4xl": ("font-size", "36px"),
    "text-5xl": ("font-size", "48px"),
    "text-6xl": ("font-size", "60px"),
    "text-7xl": ("font-size", "72px"),
    "text-8xl": ("font-size", "96px"),
    "text-9xl": ("font-size", "128px"),
}

# ─── Line heights ──────────────────────────────────────────────────────────
LINE_HEIGHTS = {
    "leading-none": ("line-height", "1"),
    "leading-tight": ("line-height", "1.25"),
    "leading-snug": ("line-height", "1.375"),
    "leading-normal": ("line-height", "1.5"),
    "leading-relaxed": ("line-height", "1.625"),
    "leading-loose": ("line-height", "2"),
}

# ─── Border radius ──────────────────────────────────────────────────────────
RADIUS = {
    "rounded-none": ("border-radius", "0"),
    "rounded-sm": ("border-radius", "2px"),
    "rounded": ("border-radius", "4px"),
    "rounded-md": ("border-radius", "6px"),
    "rounded-lg": ("border-radius", "8px"),
    "rounded-xl": ("border-radius", "12px"),
    "rounded-2xl": ("border-radius", "16px"),
    "rounded-3xl": ("border-radius", "24px"),
    "rounded-full": ("border-radius", "9999px"),
}

# ─── Shadow ────────────────────────────────────────────────────────────────
SHADOWS = {
    "shadow-sm": ("box-shadow", "0 1px 2px 0 rgba(0,0,0,0.05)"),
    "shadow": ("box-shadow", "0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06)"),
    "shadow-md": ("box-shadow", "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)"),
    "shadow-lg": ("box-shadow", "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05)"),
    "shadow-xl": ("box-shadow", "0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04)"),
    "shadow-2xl": ("box-shadow", "0 25px 50px -12px rgba(0,0,0,0.25)"),
    "shadow-none": ("box-shadow", "none"),
}

# ─── Width/Height (fractional) ─────────────────────────────────────────────
WIDTH_HEIGHT_FRACTION = {
    "w-full": ("width", "100%"),
    "w-screen": ("width", "100vw"),
    "w-auto": ("width", "auto"),
    "h-full": ("height", "100%"),
    "h-screen": ("height", "100vh"),
    "h-auto": ("height", "auto"),
    "max-w-full": ("max-width", "100%"),
    "max-w-none": ("max-width", "none"),
    "min-w-full": ("min-width", "100%"),
    "min-h-full": ("min-height", "100%"),
    "min-h-screen": ("min-height", "100vh"),
    "w-1/2": ("width", "50%"),
    "w-1/3": ("width", "33.333%"),
    "w-2/3": ("width", "66.666%"),
    "w-1/4": ("width", "25%"),
    "w-3/4": ("width", "75%"),
    "w-1/5": ("width", "20%"),
    "w-2/5": ("width", "40%"),
    "w-3/5": ("width", "60%"),
    "w-4/5": ("width", "80%"),
    "h-1/2": ("height", "50%"),
    "h-1/3": ("height", "33.333%"),
    "h-2/3": ("height", "66.666%"),
    "h-1/4": ("height", "25%"),
    "h-3/4": ("height", "75%"),
}

# ─── Transition ────────────────────────────────────────────────────────────
TRANSITIONS = {
    "transition-none": ("transition", "none"),
    "transition-all": ("transition", "all 150ms cubic-bezier(0.4,0,0.2,1)"),
    "transition": ("transition", "all 150ms cubic-bezier(0.4,0,0.2,1)"),
    "transition-colors": ("transition", "color, background-color, border-color 150ms cubic-bezier(0.4,0,0.2,1)"),
    "transition-opacity": ("transition", "opacity 150ms cubic-bezier(0.4,0,0.2,1)"),
    "transition-transform": ("transition", "transform 150ms cubic-bezier(0.4,0,0.2,1)"),
}

# ─── Merge all static maps ─────────────────────────────────────────────────
ALL_STATIC = {}
for _m in (STATIC_MAP, FONT_SIZES, LINE_HEIGHTS, RADIUS, SHADOWS, WIDTH_HEIGHT_FRACTION, TRANSITIONS):
    ALL_STATIC.update(_m)
del _m

# ─── Dynamic pattern matchers ──────────────────────────────────────────────

def _expand_spacing(cls: str) -> Optional[Decl]:
    """p-4, px-4, pt-4, m-4, mx-auto, gap-2, etc."""
    m = re.match(r'^(p|px|py|pt|pr|pb|pl|m|mx|my|mt|mr|mb|ml|gap|gap-x|gap-y|w|h)-(\d+|px|auto|full|screen)$', cls)
    if not m:
        return None
    prefix, val = m.group(1), m.group(2)
    if val == "auto":
        if prefix == "mx":
            return ("margin", "0 auto")
        if prefix == "my":
            return ("margin", "auto 0")
        if prefix == "m":
            return ("margin", "auto")
        return None
    if val == "full":
        if prefix == "w": return ("width", "100%")
        if prefix == "h": return ("height", "100%")
        return None
    if val == "screen":
        if prefix == "w": return ("width", "100vw")
        if prefix == "h": return ("height", "100vh")
        return None
    if val == "px":
        px = "1px"
    else:
        px = SPACING.get(val, f"{val}px")

    prop_map = {
        "p": "padding", "px": "padding", "py": "padding",  # simplified
        "pt": "padding-top", "pr": "padding-right",
        "pb": "padding-bottom", "pl": "padding-left",
        "m": "margin", "mx": "margin", "my": "margin",
        "mt": "margin-top", "mr": "margin-right",
        "mb": "margin-bottom", "ml": "margin-left",
        "gap": "gap", "gap-x": "column-gap", "gap-y": "row-gap",
        "w": "width", "h": "height",
    }
    prop = prop_map.get(prefix)
    if not prop:
        return None
    # For px/py/mx/my, we'd need two declarations — handle mx-auto specially
    if prefix == "mx" and val == "auto":
        return ("margin", "0 auto")
    if prefix in ("px", "py", "mx", "my"):
        # These need two props; return first, caller handles rest
        # For simplicity, use shorthand
        if prefix == "px": return ("padding", f"0 {px}")
        if prefix == "py": return ("padding", f"{px} 0")
        if prefix == "mx": return ("margin", f"0 {px}")
        if prefix == "my": return ("margin", f"{px} 0")
    return (prop, px)


def _expand_border_width(cls: str) -> Optional[Decl]:
    """border, border-2, border-4, border-8"""
    if cls == "border":
        return ("border-width", "1px")
    m = re.match(r'^border-(0|2|4|8)$', cls)
    if m:
        return ("border-width", f"{m.group(1)}px")
    return None


def _expand_color(cls: str) -> Optional[Decl]:
    """bg-red-500, text-blue-600, border-gray-200"""
    # bg-{color}-{shade}
    m = re.match(r'^bg-(\w+)-(\d+)$', cls)
    if m:
        color, shade = m.group(1), m.group(2)
        if color in COLORS and shade in COLORS[color]:
            return ("background-color", COLORS[color][shade])
    # text-{color}-{shade}
    m = re.match(r'^text-(\w+)-(\d+)$', cls)
    if m:
        color, shade = m.group(1), m.group(2)
        if color in COLORS and shade in COLORS[color]:
            return ("color", COLORS[color][shade])
    # border-{color}-{shade}
    m = re.match(r'^border-(\w+)-(\d+)$', cls)
    if m:
        color, shade = m.group(1), m.group(2)
        if color in COLORS and shade in COLORS[color]:
            return ("border-color", COLORS[color][shade])
    # bg-{color} (bare color name)
    m = re.match(r'^bg-(\w+)$', cls)
    if m and m.group(1) in COLORS:
        return ("background-color", COLORS[m.group(1)].get("500", "#888"))
    # text-{color} (bare)
    m = re.match(r'^text-(\w+)$', cls)
    if m and m.group(1) in COLORS:
        return ("color", COLORS[m.group(1)].get("600", "#555"))
    return None


def _expand_max_width(cls: str) -> Optional[Decl]:
    """max-w-sm, max-w-md, max-w-lg, max-w-xl, max-w-2xl, etc."""
    sizes = {
        "sm": "384px", "md": "448px", "lg": "512px",
        "xl": "576px", "2xl": "672px", "3xl": "768px",
        "4xl": "896px", "5xl": "1024px", "6xl": "1152px",
        "7xl": "1280px",
    }
    m = re.match(r'^max-w-(sm|md|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl)$', cls)
    if m:
        return ("max-width", sizes[m.group(1)])
    return None


def _expand_grid_cols(cls: str) -> Optional[Decl]:
    """grid-cols-1, grid-cols-2, grid-cols-3, etc."""
    m = re.match(r'^grid-cols-(\d+)$', cls)
    if m:
        n = int(m.group(1))
        return ("grid-template-columns", " ".join(["1fr"] * n))
    return None


def _expand_inset(cls: str) -> Optional[Decl]:
    """top-0, right-0, bottom-0, left-0, inset-0"""
    m = re.match(r'^(top|right|bottom|left|inset)-(\d+)$', cls)
    if m:
        prop = m.group(1)
        val = SPACING.get(m.group(2), f"{m.group(2)}px")
        if prop == "inset":
            return ("top", val)  # simplified
        return (prop, val)
    return None


def _expand_aspect(cls: str) -> Optional[Decl]:
    """aspect-square, aspect-video"""
    if cls == "aspect-square":
        return ("aspect-ratio", "1 / 1")
    if cls == "aspect-video":
        return ("aspect-ratio", "16 / 9")
    return None


def _expand_object_fit(cls: str) -> Optional[Decl]:
    """object-contain, object-cover, object-fill, object-none"""
    m = {
        "object-contain": ("object-fit", "contain"),
        "object-cover": ("object-fit", "cover"),
        "object-fill": ("object-fit", "fill"),
        "object-none": ("object-fit", "none"),
        "object-scale-down": ("object-fit", "scale-down"),
    }
    return m.get(cls)


def _expand_transform(cls: str) -> Optional[Decl]:
    if cls == "transform":
        return ("transform", "translate(0,0)")
    return None


# ─── Ordered list of dynamic expanders ─────────────────────────────────────
_DYNAMIC_EXPANDERS = [
    _expand_spacing,
    _expand_border_width,
    _expand_color,
    _expand_max_width,
    _expand_grid_cols,
    _expand_inset,
    _expand_aspect,
    _expand_object_fit,
    _expand_transform,
]


def expand_tailwind_class(cls: str) -> Optional[Decl]:
    """Expand a single Tailwind utility class to (prop, value) or None."""
    if cls in ALL_STATIC:
        return ALL_STATIC[cls]
    for expander in _DYNAMIC_EXPANDERS:
        result = expander(cls)
        if result:
            return result
    return None


def expand_tailwind_line(line: str) -> Optional[List[Decl]]:
    """
    Try to expand a full line as Tailwind utility classes.

    Returns list of (prop, val) tuples if ALL words are valid Tailwind classes.
    Returns None if any word is not a Tailwind class (caller should use TSS parsing).

    Example:
        "flex items-center gap-2 p-4" → [("display","flex"), ("align-items","center"), ("gap","8px"), ("padding","16px")]
        "display flex" → None (display is not a Tailwind class)
    """
    line = line.strip().strip(";").strip()
    if not line:
        return None
    words = line.split()
    if not words:
        return None

    results: List[Decl] = []
    for w in words:
        expanded = expand_tailwind_class(w)
        if not expanded:
            return None  # Not all words are Tailwind → fall back to TSS
        results.append(expanded)
    return results if results else None

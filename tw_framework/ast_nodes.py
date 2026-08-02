from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Attribute:
    name: str
    value: Any


def attribute_to_dict(attribute: Any) -> Dict[str, Any]:
    if isinstance(attribute, Attribute):
        return {
            "name": attribute.name,
            "value": serialize_value(attribute.value),
        }
    return {
        "name": getattr(attribute, "name", ""),
        "value": serialize_value(getattr(attribute, "value", None)),
    }


def serialize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Attribute):
        return attribute_to_dict(value)
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_value(item) for item in value]
    if is_dataclass(value):
        return serialize_value(asdict(value))
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return serialize_value(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "rules") and isinstance(getattr(value, "rules"), list):
        return {
            "kind": value.__class__.__name__,
            "rules": [serialize_value(rule) for rule in getattr(value, "rules", [])],
        }
    if hasattr(value, "selector") and hasattr(value, "declarations"):
        return {
            "kind": value.__class__.__name__,
            "selector": getattr(value, "selector", ""),
            "declarations": [serialize_value(item) for item in getattr(value, "declarations", [])],
            "children": [serialize_value(item) for item in getattr(value, "children", [])],
        }
    if hasattr(value, "__dict__"):
        raw = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            raw[key] = serialize_value(item)
        if raw:
            raw.setdefault("kind", value.__class__.__name__)
            return raw
    return repr(value)


@dataclass
class HeadModel:
    metas: List[Dict[str, Any]] = field(default_factory=list)
    icon: Optional[str] = None
    seo: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PageMeta:
    title: str = ""
    layout: Optional[str] = None
    layouts: List[str] = field(default_factory=list)
    render_mode: str = "static"
    revalidate: Optional[int] = None
    redirect_to: Optional[str] = None
    rewrite_to: Optional[str] = None
    responsive: bool = False


@dataclass
class BaseNode:
    kind: str


@dataclass
class TextNode(BaseNode):
    value: str

    def __init__(self, value: str):
        super().__init__("text")
        self.value = value


@dataclass
class LetNode(BaseNode):
    name: str
    value: Any

    def __init__(self, name: str, value: Any):
        super().__init__("let")
        self.name = name
        self.value = value


@dataclass
class IfNode(BaseNode):
    condition: str
    children: List[BaseNode] = field(default_factory=list)
    else_children: List[BaseNode] = field(default_factory=list)

    def __init__(self, condition: str, children: Optional[List[BaseNode]] = None, else_children: Optional[List[BaseNode]] = None):
        super().__init__("if")
        self.condition = condition
        self.children = children or []
        self.else_children = else_children or []


@dataclass
class ForNode(BaseNode):
    var_name: str
    iterable: str
    children: List[BaseNode] = field(default_factory=list)

    def __init__(self, var_name: str, iterable: str, children: Optional[List[BaseNode]] = None):
        super().__init__("for")
        self.var_name = var_name
        self.iterable = iterable
        self.children = children or []


@dataclass
class ScriptNode(BaseNode):
    raw_js: str

    def __init__(self, raw_js: str):
        super().__init__("script")
        self.raw_js = raw_js


@dataclass
class ElementNode(BaseNode):
    tag: str
    text: Optional[str] = None
    attrs: List[Attribute] = field(default_factory=list)
    styles: List[Attribute] = field(default_factory=list)
    events: List[Attribute] = field(default_factory=list)
    router: Dict[str, Any] = field(default_factory=dict)
    children: List[BaseNode] = field(default_factory=list)

    def __init__(
        self,
        tag: str,
        text: Optional[str] = None,
        attrs: Optional[List[Attribute]] = None,
        styles: Optional[List[Attribute]] = None,
        events: Optional[List[Attribute]] = None,
        router: Optional[Dict[str, Any]] = None,
        children: Optional[List[BaseNode]] = None,
    ):
        super().__init__("element")
        self.tag = tag
        self.text = text
        self.attrs = attrs or []
        self.styles = styles or []
        self.events = events or []
        self.router = router or {}
        self.children = children or []


@dataclass
class ComponentNode(BaseNode):
    name: str
    props: List[Attribute] = field(default_factory=list)
    children: List[BaseNode] = field(default_factory=list)

    def __init__(self, name: str, props: Optional[List[Attribute]] = None, children: Optional[List[BaseNode]] = None):
        super().__init__("component")
        self.name = name
        self.props = props or []
        self.children = children or []


@dataclass
class Program:
    meta: PageMeta = field(default_factory=PageMeta)
    head: HeadModel = field(default_factory=HeadModel)
    lets: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    body: List[BaseNode] = field(default_factory=list)
    loaded_sheets: List[Any] = field(default_factory=list)
    loaded_json: List[Dict[str, Any]] = field(default_factory=list)
    source_path: str = ""
    legacy_page: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": {
                "title": self.meta.title,
                "layout": self.meta.layout,
                "layouts": list(self.meta.layouts),
                "render_mode": self.meta.render_mode,
                "revalidate": self.meta.revalidate,
                "redirect_to": self.meta.redirect_to,
                "rewrite_to": self.meta.rewrite_to,
                "responsive": self.meta.responsive,
            },
            "head": {
                "metas": list(self.head.metas),
                "icon": self.head.icon,
                "seo": dict(self.head.seo),
            },
            "lets": serialize_value(self.lets),
            "state": serialize_value(self.state),
            "body": [node_to_dict(node) for node in self.body],
            "loaded_sheets": serialize_value(self.loaded_sheets),
            "loaded_json": serialize_value(self.loaded_json),
            "source_path": self.source_path,
        }


def node_to_dict(node: BaseNode) -> Dict[str, Any]:
    if isinstance(node, TextNode):
        return {"kind": node.kind, "value": node.value}
    if isinstance(node, LetNode):
        return {"kind": node.kind, "name": node.name, "value": serialize_value(node.value)}
    if isinstance(node, IfNode):
        return {
            "kind": node.kind,
            "condition": node.condition,
            "children": [node_to_dict(child) for child in node.children],
            "else_children": [node_to_dict(child) for child in node.else_children],
        }
    if isinstance(node, ForNode):
        return {
            "kind": node.kind,
            "var_name": node.var_name,
            "iterable": node.iterable,
            "children": [node_to_dict(child) for child in node.children],
        }
    if isinstance(node, ScriptNode):
        return {"kind": node.kind, "raw_js": node.raw_js}
    if isinstance(node, ElementNode):
        return {
            "kind": node.kind,
            "tag": node.tag,
            "text": node.text,
            "attrs": [attribute_to_dict(attr) for attr in node.attrs],
            "styles": [attribute_to_dict(attr) for attr in node.styles],
            "events": [attribute_to_dict(attr) for attr in node.events],
            "router": serialize_value(node.router),
            "children": [node_to_dict(child) for child in node.children],
        }
    if isinstance(node, ComponentNode):
        return {
            "kind": node.kind,
            "name": node.name,
            "props": [attribute_to_dict(prop) for prop in node.props],
            "children": [node_to_dict(child) for child in node.children],
        }
    return {"kind": getattr(node, "kind", "unknown"), "repr": repr(node)}


__all__ = [
    "Attribute",
    "BaseNode",
    "ComponentNode",
    "ElementNode",
    "ForNode",
    "HeadModel",
    "IfNode",
    "LetNode",
    "PageMeta",
    "Program",
    "ScriptNode",
    "TextNode",
    "attribute_to_dict",
    "node_to_dict",
    "serialize_value",
]

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IRNode:
    kind: str


@dataclass
class IRText(IRNode):
    value: str

    def __init__(self, value: str):
        super().__init__("text")
        self.value = value


@dataclass
class IRLet(IRNode):
    name: str
    value: Any

    def __init__(self, name: str, value: Any):
        super().__init__("let")
        self.name = name
        self.value = value


@dataclass
class IRIf(IRNode):
    condition: str
    children: List[IRNode] = field(default_factory=list)
    else_children: List[IRNode] = field(default_factory=list)

    def __init__(self, condition: str, children=None, else_children=None):
        super().__init__("if")
        self.condition = condition
        self.children = children or []
        self.else_children = else_children or []


@dataclass
class IRFor(IRNode):
    var_name: str
    iterable: str
    children: List[IRNode] = field(default_factory=list)

    def __init__(self, var_name: str, iterable: str, children=None):
        super().__init__("for")
        self.var_name = var_name
        self.iterable = iterable
        self.children = children or []


@dataclass
class IRScript(IRNode):
    raw_js: str

    def __init__(self, raw_js: str):
        super().__init__("script")
        self.raw_js = raw_js


@dataclass
class IRElement(IRNode):
    tag: str
    text: Optional[str] = None
    attrs: List[Dict[str, Any]] = field(default_factory=list)
    styles: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    router: Dict[str, Any] = field(default_factory=dict)
    children: List[IRNode] = field(default_factory=list)

    def __init__(self, tag: str, text=None, attrs=None, styles=None, events=None, router=None, children=None):
        super().__init__("element")
        self.tag = tag
        self.text = text
        self.attrs = attrs or []
        self.styles = styles or []
        self.events = events or []
        self.router = router or {}
        self.children = children or []


@dataclass
class IRComponent(IRNode):
    name: str
    props: List[Dict[str, Any]] = field(default_factory=list)
    children: List[IRNode] = field(default_factory=list)

    def __init__(self, name: str, props=None, children=None):
        super().__init__("component")
        self.name = name
        self.props = props or []
        self.children = children or []


@dataclass
class IRProgram:
    meta: Dict[str, Any]
    head: Dict[str, Any]
    lets: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)
    body: List[IRNode] = field(default_factory=list)

    def to_dict(self):
        return {
            "meta": dict(self.meta),
            "head": dict(self.head),
            "lets": dict(self.lets),
            "state": dict(self.state),
            "body": [ir_node_to_dict(node) for node in self.body],
        }


def ir_node_to_dict(node: IRNode):
    if isinstance(node, IRText):
        return {"kind": node.kind, "value": node.value}
    if isinstance(node, IRLet):
        return {"kind": node.kind, "name": node.name, "value": node.value}
    if isinstance(node, IRIf):
        return {
            "kind": node.kind,
            "condition": node.condition,
            "children": [ir_node_to_dict(child) for child in node.children],
            "else_children": [ir_node_to_dict(child) for child in node.else_children],
        }
    if isinstance(node, IRFor):
        return {
            "kind": node.kind,
            "var_name": node.var_name,
            "iterable": node.iterable,
            "children": [ir_node_to_dict(child) for child in node.children],
        }
    if isinstance(node, IRScript):
        return {"kind": node.kind, "raw_js": node.raw_js}
    if isinstance(node, IRElement):
        return {
            "kind": node.kind,
            "tag": node.tag,
            "text": node.text,
            "attrs": list(node.attrs),
            "styles": list(node.styles),
            "events": list(node.events),
            "router": dict(node.router),
            "children": [ir_node_to_dict(child) for child in node.children],
        }
    if isinstance(node, IRComponent):
        return {
            "kind": node.kind,
            "name": node.name,
            "props": list(node.props),
            "children": [ir_node_to_dict(child) for child in node.children],
        }
    return {"kind": getattr(node, "kind", "unknown"), "repr": repr(node)}


__all__ = [
    "IRComponent",
    "IRElement",
    "IRFor",
    "IRIf",
    "IRLet",
    "IRProgram",
    "IRScript",
    "IRText",
    "ir_node_to_dict",
]

"""
TW Framework - React Server Components (RSC) Payload System

Implements:
1. RSC Payload - Binary representation of Server Components for client DOM updates
2. "use client" Directive - Server/Client Component boundary
3. "use server" Directive - Server Actions boundary
4. RSC Payload Streaming - Server Components streaming with SSR
"""

from __future__ import annotations

import json
import struct
import hashlib
import time
import os
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Set
import gzip
import datetime

logger = logging.getLogger(__name__)

RSC_PAYLOAD_VERSION = 1
RSC_MAGIC_BYTES = b"TWRC"

USE_CLIENT = "use client"
USE_SERVER = "use server"
USE_CACHE = "use cache"

TYPE_SERVER_COMPONENT = 0x01
TYPE_CLIENT_COMPONENT = 0x02
TYPE_TEXT = 0x03
TYPE_FRAGMENT = 0x04
TYPE_SUSPENSE = 0x05
TYPE_ERROR = 0x06
TYPE_REDIRECT = 0x07
TYPE_RAW = 0x08
TYPE_ACTION = 0x09
TYPE_PROMISE = 0x0A
TYPE_SLOT = 0x0B


@dataclass
class DirectiveInfo:
    """Parsed directive information from a source file."""
    directive: str
    line: int = 0
    exports: List[str] = field(default_factory=list)
    is_default: bool = False


class DirectiveParser:
    """Parses use client, use server, use cache directives from source code."""

    DIRECTIVE_PATTERNS = {
        USE_CLIENT: re.compile(r"""^['"]use client['"]""", re.MULTILINE),
        USE_SERVER: re.compile(r"""^['"]use server['"]""", re.MULTILINE),
        USE_CACHE: re.compile(r"""^['"]use cache['"]""", re.MULTILINE),
    }
    EXPORT_PATTERN = re.compile(
        r'(?:export\s+)?(?:default\s+)?(?:function|const|class|async\s+function)\s+(\w+)',
        re.MULTILINE
    )

    def parse_source(self, source: str) -> DirectiveInfo:
        directive = ""
        for name, pattern in self.DIRECTIVE_PATTERNS.items():
            if pattern.search(source):
                directive = name
                break
        exports = self.EXPORT_PATTERN.findall(source)
        is_default = bool(re.search(r'export\s+default\b', source))
        return DirectiveInfo(directive=directive, exports=exports, is_default=is_default)

    def parse_file(self, filepath: str) -> DirectiveInfo:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()
            return self.parse_source(source)
        except (OSError, UnicodeDecodeError):
            return DirectiveInfo(directive="")

    def scan_directory(self, dir_path: str) -> Dict[str, DirectiveInfo]:
        results: Dict[str, DirectiveInfo] = {}
        if not os.path.isdir(dir_path):
            return results
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in sorted(files):
                if not fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
                    continue
                fpath = os.path.join(root, fname)
                info = self.parse_file(fpath)
                if info.directive:
                    results[os.path.relpath(fpath, dir_path)] = info
        return results

    def get_client_components(self, dir_path: str) -> List[str]:
        return [p for p, i in self.scan_directory(dir_path).items() if i.directive == USE_CLIENT]

    def get_server_actions(self, dir_path: str) -> List[str]:
        return [p for p, i in self.scan_directory(dir_path).items() if i.directive == USE_SERVER]

    def get_cache_directives(self, dir_path: str) -> List[str]:
        return [p for p, i in self.scan_directory(dir_path).items() if i.directive == USE_CACHE]


@dataclass
class RSCNode:
    """A node in the RSC payload tree."""
    type: int
    component_name: str = ""
    module_id: str = ""
    props: Dict[str, Any] = field(default_factory=dict)
    children: List["RSCNode"] = field(default_factory=list)
    text: str = ""
    fallback: Optional["RSCNode"] = None
    error_message: str = ""
    action_id: str = ""
    redirect_url: str = ""
    slot_id: str = ""
    is_client: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type, "name": self.component_name}
        if self.module_id:
            d["module"] = self.module_id
        if self.props:
            d["props"] = self.props
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        if self.text:
            d["text"] = self.text
        if self.fallback:
            d["fallback"] = self.fallback.to_dict()
        if self.error_message:
            d["error"] = self.error_message
        if self.action_id:
            d["actionId"] = self.action_id
        if self.redirect_url:
            d["redirect"] = self.redirect_url
        if self.slot_id:
            d["slotId"] = self.slot_id
        if self.is_client:
            d["client"] = True
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RSCNode":
        node = cls(
            type=d.get("type", TYPE_FRAGMENT),
            component_name=d.get("name", ""),
            module_id=d.get("module", ""),
            props=d.get("props", {}),
            text=d.get("text", ""),
            error_message=d.get("error", ""),
            action_id=d.get("actionId", ""),
            redirect_url=d.get("redirect", ""),
            slot_id=d.get("slotId", ""),
            is_client=d.get("client", False),
        )
        for child_d in d.get("children", []):
            node.children.append(cls.from_dict(child_d))
        if d.get("fallback"):
            node.fallback = cls.from_dict(d["fallback"])
        return node


class RSCPayloadBuilder:
    """Builds RSC payloads from component trees."""

    def __init__(self):
        self._module_registry: Dict[str, str] = {}
        self._action_registry: Dict[str, str] = {}
        self._client_boundaries: Set[str] = set()

    def register_module(self, module_path: str) -> str:
        if module_path not in self._module_registry:
            self._module_registry[module_path] = "m" + str(len(self._module_registry))
        return self._module_registry[module_path]

    def register_action(self, action_name: str) -> str:
        if action_name not in self._action_registry:
            aid = "a" + str(len(self._action_registry)) + "_" + hashlib.sha256(action_name.encode()).hexdigest()[:8]
            self._action_registry[action_name] = aid
        return self._action_registry[action_name]

    def mark_client_component(self, module_path: str) -> None:
        self._client_boundaries.add(module_path)

    def create_server_component(self, name: str, module_path: str = "",
                                 props=None, children=None) -> RSCNode:
        mid = self.register_module(module_path or name)
        return RSCNode(type=TYPE_SERVER_COMPONENT, component_name=name,
                       module_id=mid, props=props or {}, children=children or [])

    def create_client_component(self, name: str, module_path: str,
                                props=None, children=None) -> RSCNode:
        self.mark_client_component(module_path)
        mid = self.register_module(module_path)
        return RSCNode(type=TYPE_CLIENT_COMPONENT, component_name=name,
                       module_id=mid, props=self._serialize_props(props or {}),
                       children=children or [], is_client=True)

    def create_text(self, text: str) -> RSCNode:
        return RSCNode(type=TYPE_TEXT, text=text)

    def create_fragment(self, children: List[RSCNode]) -> RSCNode:
        return RSCNode(type=TYPE_FRAGMENT, children=children)

    def create_suspense(self, fallback: RSCNode, children: List[RSCNode]) -> RSCNode:
        return RSCNode(type=TYPE_SUSPENSE, fallback=fallback, children=children)

    def create_error(self, message: str) -> RSCNode:
        return RSCNode(type=TYPE_ERROR, error_message=message)

    def create_redirect(self, url: str) -> RSCNode:
        return RSCNode(type=TYPE_REDIRECT, redirect_url=url)

    def create_action(self, action_name: str, args=None) -> RSCNode:
        aid = self.register_action(action_name)
        return RSCNode(type=TYPE_ACTION, component_name=action_name,
                       action_id=aid, props={"args": args or []})

    def create_slot(self, slot_id: str, children: List[RSCNode]) -> RSCNode:
        return RSCNode(type=TYPE_SLOT, slot_id=slot_id, children=children)

    def _serialize_props(self, props: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_serialize(props)

    def _safe_serialize(self, obj: Any) -> Any:
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._safe_serialize(i) for i in obj]
        if isinstance(obj, dict):
            return {k: self._safe_serialize(v) for k, v in obj.items()}
        if isinstance(obj, set):
            return {"__type": "set", "value": [self._safe_serialize(v) for v in obj]}
        import datetime
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return {"__type": "date", "value": obj.isoformat()}
        if callable(obj):
            aid = self.register_action(getattr(obj, "__name__", "anonymous"))
            return {"__type": "action", "actionId": aid}
        if hasattr(obj, "__dict__"):
            return {"__type": "object", "class": type(obj).__name__,
                    "value": self._safe_serialize(obj.__dict__)}
        return str(obj)

    def build_payload(self, root: RSCNode) -> "RSCPayload":
        return RSCPayload(root=root, modules=dict(self._module_registry),
                          actions=dict(self._action_registry),
                          client_boundaries=set(self._client_boundaries))


@dataclass
class RSCPayload:
    """A complete RSC payload."""
    root: RSCNode
    modules: Dict[str, str] = field(default_factory=dict)
    actions: Dict[str, str] = field(default_factory=dict)
    client_boundaries: Set[str] = field(default_factory=set)
    build_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "version": RSC_PAYLOAD_VERSION,
            "buildId": self.build_id,
            "timestamp": self.timestamp,
            "modules": self.modules,
            "actions": self.actions,
            "clientBoundaries": sorted(self.client_boundaries),
            "root": self.root.to_dict(),
        }, separators=(",", ":"))

    def to_json_pretty(self) -> str:
        return json.dumps({
            "version": RSC_PAYLOAD_VERSION,
            "buildId": self.build_id,
            "timestamp": self.timestamp,
            "modules": self.modules,
            "actions": self.actions,
            "clientBoundaries": sorted(self.client_boundaries),
            "root": self.root.to_dict(),
        }, indent=2)

    def to_binary(self) -> bytes:
        json_data = self.to_json().encode("utf-8")
        if len(json_data) > 1024:
            import gzip
            payload_data = gzip.compress(json_data, compresslevel=9)
            compressed = True
        else:
            payload_data = json_data
            compressed = False
        header = (
            RSC_MAGIC_BYTES
            + struct.pack("B", RSC_PAYLOAD_VERSION)
            + struct.pack("?", compressed)
            + struct.pack("I", len(self.build_id))
            + self.build_id.encode("utf-8")
            + struct.pack("d", self.timestamp)
            + struct.pack("I", len(payload_data))
        )
        return header + payload_data

    @classmethod
    def from_json(cls, json_str: str) -> "RSCPayload":
        data = json.loads(json_str)
        return cls(root=RSCNode.from_dict(data["root"]),
                   modules=data.get("modules", {}),
                   actions=data.get("actions", {}),
                   client_boundaries=set(data.get("clientBoundaries", [])),
                   build_id=data.get("buildId", ""),
                   timestamp=data.get("timestamp", 0.0))

    @classmethod
    def from_binary(cls, data: bytes) -> "RSCPayload":
        if len(data) < 22 or data[:4] != RSC_MAGIC_BYTES:
            raise ValueError("Invalid RSC binary payload")
        version = data[4]
        compressed = bool(data[5])
        build_id_len = struct.unpack("I", data[6:10])[0]
        build_id = data[10:10+build_id_len].decode("utf-8")
        offset = 10 + build_id_len
        timestamp = struct.unpack("d", data[offset:offset+8])[0]
        offset += 8
        payload_len = struct.unpack("I", data[offset:offset+4])[0]
        offset += 4
        payload_data = data[offset:offset+payload_len]
        if compressed:
            import gzip
            json_data = gzip.decompress(payload_data).decode("utf-8")
        else:
            json_data = payload_data.decode("utf-8")
        return cls.from_json(json_data)

    def get_size(self) -> Dict[str, int]:
        j = len(self.to_json())
        b = len(self.to_binary())
        return {"json_bytes": j, "binary_bytes": b,
                "json_kb": round(j/1024, 2), "binary_kb": round(b/1024, 2),
                "module_count": len(self.modules),
                "action_count": len(self.actions),
                "client_boundary_count": len(self.client_boundaries)}


@dataclass
class RSCStreamChunk:
    """A single chunk in an RSC stream."""
    chunk_id: int
    data: bytes
    is_final: bool = False
    slot_id: str = ""
    timestamp: float = field(default_factory=time.time)


class RSCPayloadStreamer:
    """Streams RSC payloads in chunks for progressive rendering."""

    def __init__(self, builder=None):
        self.builder = builder or RSCPayloadBuilder()
        self._chunks: List[RSCStreamChunk] = []
        self._chunk_counter = 0
        self._pending_slots: Dict[str, RSCNode] = {}
        self._on_chunk_callback: Optional[Callable] = None

    def on_chunk(self, callback: Callable[[RSCStreamChunk], None]) -> None:
        self._on_chunk_callback = callback

    def create_initial_shell(self, static_nodes: List[RSCNode],
                              dynamic_slots: Dict[str, RSCNode]) -> RSCPayload:
        children = list(static_nodes)
        for slot_id, fallback in dynamic_slots.items():
            suspense = self.builder.create_suspense(fallback=fallback, children=[])
            suspense.slot_id = slot_id
            children.append(suspense)
            self._pending_slots[slot_id] = fallback
        root = self.builder.create_fragment(children)
        return self.builder.build_payload(root)

    def stream_initial(self, payload: RSCPayload) -> RSCStreamChunk:
        return self._make_chunk(payload.to_binary(), is_final=False)

    def stream_slot(self, slot_id: str, content: RSCNode) -> RSCStreamChunk:
        slot_payload = RSCPayload(root=content,
                                   build_id=self.builder._module_registry.get(slot_id, ""))
        chunk = self._make_chunk(slot_payload.to_binary(), is_final=False, slot_id=slot_id)
        self._pending_slots.pop(slot_id, None)
        return chunk

    def stream_final(self) -> RSCStreamChunk:
        return self._make_chunk(b"", is_final=True)

    def stream_all(self, payload: RSCPayload,
                    resolved_slots: Dict[str, RSCNode]) -> List[RSCStreamChunk]:
        chunks = [self.stream_initial(payload)]
        for slot_id, content in resolved_slots.items():
            chunks.append(self.stream_slot(slot_id, content))
        chunks.append(self.stream_final())
        return chunks

    def _make_chunk(self, data: bytes, is_final: bool = False,
                    slot_id: str = "") -> RSCStreamChunk:
        self._chunk_counter += 1
        chunk = RSCStreamChunk(chunk_id=self._chunk_counter, data=data,
                                is_final=is_final, slot_id=slot_id)
        self._chunks.append(chunk)
        if self._on_chunk_callback:
            try:
                self._on_chunk_callback(chunk)
            except Exception as e:
                logger.warning("Stream callback error: %s", e)
        return chunk

    def get_all_chunks(self) -> List[RSCStreamChunk]:
        return list(self._chunks)

    def get_pending_slots(self) -> List[str]:
        return list(self._pending_slots.keys())

    def get_stats(self) -> Dict[str, Any]:
        total = sum(len(c.data) for c in self._chunks)
        return {"total_chunks": len(self._chunks), "total_bytes": total,
                "total_kb": round(total/1024, 2),
                "pending_slots": len(self._pending_slots),
                "chunk_sizes": [len(c.data) for c in self._chunks]}


class RSCClientRenderer:
    """Client-side RSC payload renderer."""

    def __init__(self):
        self._module_cache: Dict[str, Any] = {}
        self._action_handlers: Dict[str, Callable] = {}

    def register_action_handler(self, action_id: str, handler: Callable) -> None:
        self._action_handlers[action_id] = handler

    def render_to_html(self, payload: RSCPayload) -> str:
        return self._render_node(payload.root, payload)

    def _render_node(self, node: RSCNode, payload: RSCPayload) -> str:
        if node.type == TYPE_TEXT:
            return self._escape_html(node.text)
        if node.type == TYPE_FRAGMENT:
            return "".join(self._render_node(c, payload) for c in node.children)
        if node.type == TYPE_SERVER_COMPONENT:
            ch = "".join(self._render_node(c, payload) for c in node.children)
            return '<div data-tw-component="' + node.component_name + '">' + ch + '</div>'
        if node.type == TYPE_CLIENT_COMPONENT:
            ch = "".join(self._render_node(c, payload) for c in node.children)
            pj = json.dumps(node.props, separators=(",", ":"))
            return ('<div data-tw-client="' + node.module_id + '" '
                    'data-tw-name="' + node.component_name + '" '
                    'data-tw-props=\'' + pj + '\'>' + ch + '</div>')
        if node.type == TYPE_SUSPENSE:
            fb = self._render_node(node.fallback, payload) if node.fallback else ""
            sid = node.slot_id or hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]
            return ('<tw-suspense data-tw-slot="' + sid + '">'
                    '<template data-tw-fallback>' + fb + '</template>'
                    '<div data-tw-loading>' + fb + '</div></tw-suspense>')
        if node.type == TYPE_ERROR:
            return '<div class="tw-error" role="alert">' + self._escape_html(node.error_message) + '</div>'
        if node.type == TYPE_REDIRECT:
            return '<meta http-equiv="refresh" content="0;url=' + node.redirect_url + '">'
        if node.type == TYPE_ACTION:
            return '<button data-tw-action="' + node.action_id + '">Action</button>'
        if node.type == TYPE_SLOT:
            ch = "".join(self._render_node(c, payload) for c in node.children)
            return '<div data-tw-slot-content="' + node.slot_id + '">' + ch + '</div>'
        return ""

    def generate_hydration_script(self, payload: RSCPayload) -> str:
        pj = payload.to_json()
        mm = json.dumps(payload.modules)
        am = json.dumps(payload.actions)
        js_lines = [
            "<script>",
            "(function() {",
            "  var payload = " + pj + ";",
            "  var modules = " + mm + ";",
            "  var actions = " + am + ";",
            "  var clientBoundaries = document.querySelectorAll('[data-tw-client]');",
            "  var total = clientBoundaries.length;",
            "  var hydrated = 0;",
            "  clientBoundaries.forEach(function(el) {",
            "    var moduleId = el.getAttribute('data-tw-client');",
            "    var name = el.getAttribute('data-tw-name');",
            "    var propsJson = el.getAttribute('data-tw-props');",
            "    var props = propsJson ? JSON.parse(propsJson) : {};",
            "    var component = window.__tw_modules__ && window.__tw_modules__[moduleId];",
            "    if (component && typeof component.render === 'function') {",
            "      try {",
            "        el.innerHTML = component.render(props);",
            "        el.setAttribute('data-tw-hydrated', 'true');",
            "        hydrated++;",
            "      } catch(e) {",
            "        console.error('[RSC] Hydration failed', name, e);",
            "      }",
            "    }",
            "  });",
            "  var actionButtons = document.querySelectorAll('[data-tw-action]');",
            "  actionButtons.forEach(function(btn) {",
            "    var actionId = btn.getAttribute('data-tw-action');",
            "    btn.addEventListener('click', function(e) {",
            "      e.preventDefault();",
            "      fetch('/__tw/action', {",
            "        method: 'POST',",
            "        headers: { 'Content-Type': 'application/json' },",
            "        body: JSON.stringify({ actionId: actionId })",
            "      }).then(function(r) { return r.json(); })",
            "        .then(function(result) {",
            "          if (result.redirect) window.location.href = result.redirect;",
            "          document.dispatchEvent(new CustomEvent('tw:action-complete', {",
            "            detail: { actionId: actionId, result: result }",
            "          }));",
            "        }).catch(function(err) { console.error('[RSC] Action failed', err); });",
            "    });",
            "  });",
            "  window.__tw_resolve_slot = function(slotId, html) {",
            "    var el = document.querySelector('[data-tw-slot="' + slotId + '"]');",
            "    if (el) {",
            "      var loading = el.querySelector('[data-tw-loading]');",
            "      if (loading) { loading.innerHTML = html; loading.setAttribute('data-tw-loaded', 'true'); }",
            "    }",
            "  };",
            "  console.log('[RSC] Hydrated ' + hydrated + '/' + total + ' client components');",
            "})();",
            "</script>",
        ]
        return "\n".join(js_lines)

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters using chr() to avoid quote conflicts."""
        return (
            text.replace(chr(38), chr(38) + "amp;")
            .replace(chr(60), chr(60) + "lt;")
            .replace(chr(62), chr(62) + "gt;")
            .replace(chr(34), chr(38) + "quot;")
            .replace(chr(39), chr(38) + "#x27;")
        )
    def get_render_stats(self, payload: RSCPayload) -> Dict[str, Any]:
        counts = {"nodes": 0, "client": 0, "suspense": 0, "action": 0}
        def _count(n):
            counts["nodes"] += 1
            if n.type == TYPE_CLIENT_COMPONENT: counts["client"] += 1
            if n.type == TYPE_SUSPENSE: counts["suspense"] += 1
            if n.type == TYPE_ACTION: counts["action"] += 1
            for c in n.children: _count(c)
            if n.fallback: _count(n.fallback)
        _count(payload.root)
        return {**counts, "modules": len(payload.modules),
                "actions": len(payload.actions), "payload_size": payload.get_size()}


@dataclass
class RSCManifestEntry:
    """Entry in the RSC manifest for a single route."""
    route: str
    components: List[str] = field(default_factory=list)
    client_boundaries: List[str] = field(default_factory=list)
    server_actions: List[str] = field(default_factory=list)
    is_static: bool = False
    has_suspense: bool = False


class RSCManifest:
    """Build-time manifest of all RSC routes and their component trees."""

    def __init__(self):
        self._entries: Dict[str, RSCManifestEntry] = {}
        self._global_client_components: Set[str] = set()
        self._global_server_actions: Set[str] = set()
        self._build_id: str = ""

    def add_route(self, route: str, components: List[str],
                  client_boundaries: List[str], server_actions: List[str],
                  is_static: bool = False, has_suspense: bool = False) -> None:
        self._entries[route] = RSCManifestEntry(
            route=route, components=components,
            client_boundaries=client_boundaries, server_actions=server_actions,
            is_static=is_static, has_suspense=has_suspense)
        self._global_client_components.update(client_boundaries)
        self._global_server_actions.update(server_actions)

    def get_route(self, route: str) -> Optional[RSCManifestEntry]:
        return self._entries.get(route)

    def get_all_client_components(self) -> List[str]:
        return sorted(self._global_client_components)

    def get_all_server_actions(self) -> List[str]:
        return sorted(self._global_server_actions)

    def get_static_routes(self) -> List[str]:
        return [r for r, e in self._entries.items() if e.is_static]

    def get_streaming_routes(self) -> List[str]:
        return [r for r, e in self._entries.items() if e.has_suspense]

    def set_build_id(self, build_id: str) -> None:
        self._build_id = build_id

    def to_json(self) -> str:
        return json.dumps({
            "buildId": self._build_id,
            "routes": {r: {"components": e.components, "clientBoundaries": e.client_boundaries,
                            "serverActions": e.server_actions, "static": e.is_static,
                            "streaming": e.has_suspense}
                       for r, e in self._entries.items()},
            "globalClientComponents": sorted(self._global_client_components),
            "globalServerActions": sorted(self._global_server_actions),
        }, indent=2)

    def to_file(self, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(self.to_json())
        return output_path

    def get_summary(self) -> Dict[str, Any]:
        return {"build_id": self._build_id, "total_routes": len(self._entries),
                "static_routes": len(self.get_static_routes()),
                "streaming_routes": len(self.get_streaming_routes()),
                "client_components": len(self._global_client_components),
                "server_actions": len(self._global_server_actions)}


class RSCMiddleware:
    """Middleware for RSC payload processing."""

    RSC_ACCEPT = "text/x-tw-rsc"
    RSC_HEADER = "X-TW-RSC"

    def __init__(self, manifest=None):
        self.manifest = manifest or RSCManifest()
        self._builder = RSCPayloadBuilder()
        self._renderer = RSCClientRenderer()
        self._enabled = True

    def is_rsc_request(self, headers: Dict[str, str]) -> bool:
        accept = headers.get("accept", "") or headers.get("Accept", "")
        rsc_h = headers.get(self.RSC_HEADER.lower(), "") or headers.get(self.RSC_HEADER, "")
        return self.RSC_ACCEPT in accept or rsc_h == "1"

    def process_response(self, route: str, rendered_html: str,
                          request_headers: Dict[str, str]) -> Dict[str, Any]:
        if not self._enabled or not self.is_rsc_request(request_headers):
            return {"content": rendered_html, "content_type": "text/html; charset=utf-8",
                    "headers": {}, "is_rsc": False}
        text_node = RSCNode(type=TYPE_TEXT, text=rendered_html)
        payload = self._builder.build_payload(text_node)
        return {"content": payload.to_binary(), "content_type": self.RSC_ACCEPT,
                "headers": {self.RSC_HEADER: "1", "X-TW-RSC-Version": str(RSC_PAYLOAD_VERSION)},
                "is_rsc": True}

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def get_info(self) -> Dict[str, Any]:
        return {"enabled": self._enabled, "rsc_accept_type": self.RSC_ACCEPT,
                "rsc_header": self.RSC_HEADER, "manifest_summary": self.manifest.get_summary()}


__all__ = [
    "RSC_PAYLOAD_VERSION", "RSC_MAGIC_BYTES",
    "USE_CLIENT", "USE_SERVER", "USE_CACHE",
    "TYPE_SERVER_COMPONENT", "TYPE_CLIENT_COMPONENT", "TYPE_TEXT",
    "TYPE_FRAGMENT", "TYPE_SUSPENSE", "TYPE_ERROR", "TYPE_REDIRECT",
    "TYPE_RAW", "TYPE_ACTION", "TYPE_PROMISE", "TYPE_SLOT",
    "DirectiveInfo", "DirectiveParser",
    "RSCNode", "RSCPayloadBuilder", "RSCPayload",
    "RSCStreamChunk", "RSCPayloadStreamer",
    "RSCClientRenderer", "RSCManifestEntry", "RSCManifest", "RSCMiddleware",
]

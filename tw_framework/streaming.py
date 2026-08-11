"""
Streaming SSR support for TW Framework.

Provides a generator that yields HTML chunks as they become available,
enabling progressive rendering and faster Time-to-First-Byte.
"""

import html
import logging
from typing import Any, Dict, Generator, List, Optional

from .ir import IRComponent, IRElement, IRFor, IRIf, IRLet, IRProgram, IRScript, IRText
from .runtime_values import RuntimeEnvironment

logger = logging.getLogger(__name__)


def _interpolate(value, context) -> Any:
    from . import compiler
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return compiler.interpolate(value, context)


def _evaluate(expr: str, context) -> Any:
    from . import compiler
    return compiler.evaluate_expression(expr, context)


def render_node_streaming(node: Any, env: RuntimeEnvironment) -> Generator[str, None, None]:
    """Yield HTML chunks for a single IR node."""
    context = env.to_context()
    if isinstance(node, IRText):
        yield html.escape(str(_interpolate(node.value, context)))
    elif isinstance(node, IRLet):
        env.set(node.name, _interpolate(node.value, context))
    elif isinstance(node, IRIf):
        branch = node.children if _evaluate(node.condition, context) else node.else_children
        for child in branch:
            yield from render_node_streaming(child, env.child())
    elif isinstance(node, IRFor):
        items = _evaluate(node.iterable, context)
        for item in items or []:
            loop_env = env.child({node.var_name: item})
            for child in node.children:
                yield from render_node_streaming(child, loop_env)
    elif isinstance(node, IRScript):
        yield f"<script>{node.raw_js}</script>"
    elif isinstance(node, IRComponent):
        props = {prop["name"]: _interpolate(prop["value"], context) for prop in node.props}
        stack = context.get("__tw_component_stack__", ())
        if node.name in stack:
            chain = " -> ".join(stack + (node.name,))
            logger.error("Circular component reference detected: %s", chain)
            yield (
                f'<div data-tw-component-error="circular" data-tw-component="{html.escape(node.name, quote=True)}">'
                f"Circular component reference: {html.escape(chain)}"
                f"</div>"
            )
            return
        from .render_html import _load_component_ir
        component_ir = _load_component_ir(node.name)
        if component_ir is None:
            children_html = "".join(render_node_streaming(child, env.child()) for child in node.children)
            props_html = "".join(
                f'<li><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</li>'
                for key, value in props.items()
            )
            logger.warning("Component `%s` could not be resolved; rendering placeholder.", node.name)
            yield (
                f'<div data-tw-component-error="not-found" data-tw-component="{html.escape(node.name, quote=True)}">'
                f"<div>Component not found: {html.escape(node.name)}</div>"
                f"<ul>{props_html}</ul>{children_html}</div>"
            )
            return
        component_env = RuntimeEnvironment(
            values={
                **dict(component_ir.lets),
                **dict(component_ir.state),
                **props,
                "__tw_component_stack__": stack + (node.name,),
            }
        )
        for child in component_ir.body:
            yield from render_node_streaming(child, component_env)
    elif isinstance(node, IRElement):
        attrs = _render_attrs(node.attrs, env)
        style_attr = _render_style(node.styles, env)
        event_attrs = _render_attrs(node.events, env)
        text = html.escape(str(_interpolate(node.text, context))) if node.text is not None else ""
        children = "".join(render_node_streaming(child, env.child()) for child in node.children)
        if node.tag in {"br", "hr", "img", "input", "meta", "link"}:
            yield f"<{node.tag}{attrs}{style_attr}{event_attrs}>"
        else:
            yield f"<{node.tag}{attrs}{style_attr}{event_attrs}>{text}{children}</{node.tag}>"


def _render_attrs(attrs, env) -> Any:
    parts = []
    context = env.to_context()
    for attr in attrs:
        value = _interpolate(attr["value"], context)
        if value is True:
            parts.append(attr["name"])
            continue
        if value in {False, None}:
            continue
        parts.append(f'{attr["name"]}="{html.escape(str(value), quote=True)}"')
    return f" {' '.join(parts)}" if parts else ""


def _render_style(styles, env) -> Any:
    resolved = []
    context = env.to_context()
    for item in styles:
        value = _interpolate(item["value"], context)
        resolved.append(f'{item["name"]}: {value}')
    return f' style="{html.escape("; ".join(resolved), quote=True)}"' if resolved else ""


def render_program_streaming(program: IRProgram, context: Optional[Dict] = None) -> Generator[str, None, None]:
    """Yield HTML chunks for the entire program."""
    env = RuntimeEnvironment(values={**dict(program.lets), **dict(program.state), **dict(context or {})})
    yield "<!DOCTYPE html><html><head>"
    title = html.escape(str(program.meta.get("title") or "TW Program"))
    yield f"<title>{title}</title>"
    yield "</head><body>"
    for node in program.body:
        yield from render_node_streaming(node, env)
    yield "</body></html>"


__all__ = ["render_program_streaming", "render_node_streaming"]


# === v0.9.08: SSE Streaming + Skeleton ===

STREAMING_CLIENT_SCRIPT = """
<script>
(function() {
    var eventSource = new EventSource("/__tw/stream?url=" + encodeURIComponent(window.location.pathname));
    var skeleton = document.getElementById("tw-skeleton");
    var root = document.getElementById("tw-root");
    var receivedChunks = false;

    eventSource.addEventListener("chunk", function(e) {
        if (!receivedChunks) {
            receivedChunks = true;
            if (skeleton) skeleton.style.display = "none";
            if (root) root.style.display = "block";
        }
        var data = JSON.parse(e.data);
        if (root) root.insertAdjacentHTML("beforeend", data.html || "");
    });

    eventSource.addEventListener("done", function(e) {
        eventSource.close();
    });

    eventSource.addEventListener("error", function(e) {
        eventSource.close();
    });
})();
</script>
"""


def get_streaming_script() -> str:
    return STREAMING_CLIENT_SCRIPT


def generate_skeleton(loader_text: str = "Loading...") -> str:
    css_parts = [
        '<style id="tw-skeleton-style">',
        '#tw-skeleton{display:flex;align-items:center;justify-content:center;',
        'min-height:100vh;background:#f8f9fa;}',
        '#tw-skeleton .tw-loader{text-align:center;font-family:system-ui,sans-serif;color:#6c757d;}',
        '#tw-skeleton .tw-spinner{width:40px;height:40px;border:4px solid #e9ecef;',
        'border-top:4px solid #007bff;border-radius:50%;animation:tw-spin 1s linear infinite;',
        'margin:0 auto 16px;}',
        '@keyframes tw-spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}',
        '#tw-root{display:none}',
        '</style>',
    ]
    css = "".join(css_parts)
    html_parts = [
        '<div id="tw-skeleton">',
        '<div class="tw-loader">',
        '<div class="tw-spinner"></div>',
        '<p>' + loader_text + '</p>',
        '</div></div>',
        '<div id="tw-root"></div>',
    ]
    return css + "".join(html_parts)


class StreamChunk:
    def __init__(self, html: str):
        self.html = html

    def to_sse(self) -> str:
        import json as _json
        return "event: chunk\ndata: " + _json.dumps({"html": self.html}) + "\n\n"


class StreamDone:
    def to_sse(self) -> str:
        return "event: done\ndata: {}\n\n"


class StreamError:
    def __init__(self, message: str):
        self.message = message

    def to_sse(self) -> str:
        import json as _json
        return "event: error\ndata: " + _json.dumps({"error": self.message}) + "\n\n"

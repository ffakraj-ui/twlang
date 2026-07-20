from __future__ import annotations

import html
import logging
import os
from typing import Dict, Iterable, List, Optional

from .ir import IRComponent, IRElement, IRFor, IRIf, IRLet, IRProgram, IRScript, IRText
from .runtime_values import RuntimeEnvironment

logger = logging.getLogger(__name__)


def _legacy():
    from . import compiler

    return compiler


VOID_TAGS = {"br", "hr", "img", "input", "meta", "link"}

# Cache of resolved-and-lowered component IR, keyed by resolved file path.
# This avoids re-parsing the same component `.tw` file every time it is used
# on a page (e.g. a `Button` used 20 times in a list).
_COMPONENT_PROGRAM_CACHE: Dict[str, IRProgram] = {}


def _interpolate(value, context):
    compiler = _legacy()
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return compiler.interpolate(value, context)


def _evaluate(expr: str, context):
    compiler = _legacy()
    return compiler.evaluate_expression(expr, context)


def build_runtime_context(program, context: Optional[Dict] = None) -> Dict:
    compiler = _legacy()
    runtime_context: Dict = {}
    runtime_context.update(dict(program.lets))
    runtime_context.update(dict(program.state))
    if getattr(program, "legacy_page", None) is not None and getattr(program, "source_path", ""):
        try:
            base_context = compiler.create_base_context(program.legacy_page, program.source_path)
            runtime_context.update(base_context)
        except Exception as err:
            logger.exception("Failed to create base runtime context for %s", getattr(program, "source_path", ""))
    runtime_context.update(dict(context or {}))
    return runtime_context


def _render_attrs(attrs: Iterable[Dict], env: RuntimeEnvironment) -> str:
    parts: List[str] = []
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


def _render_style(styles: Iterable[Dict], env: RuntimeEnvironment) -> str:
    resolved = []
    context = env.to_context()
    for item in styles:
        value = _interpolate(item["value"], context)
        resolved.append(f'{item["name"]}: {value}')
    return f' style="{html.escape("; ".join(resolved), quote=True)}"' if resolved else ""


def _load_component_ir(name: str) -> Optional[IRProgram]:
    """
    Resolve a component name (e.g. "Button" or "ui/Button") to its `.tw` file,
    parse it, and lower it into IR so it can actually be rendered.

    Returns None if the component file cannot be found or fails to parse;
    the caller is responsible for falling back to a visible error placeholder
    instead of silently producing empty output.
    """
    compiler = _legacy()
    try:
        path = compiler.resolve_component_path(name)
    except Exception:
        logger.exception("Failed to resolve component path for `%s`", name)
        return None

    if not path or not os.path.exists(path):
        return None

    cached = _COMPONENT_PROGRAM_CACHE.get(path)
    if cached is not None:
        return cached

    # Local imports to avoid circular import issues at module load time.
    from .lowering import lower_program
    from .parser import parse_file

    try:
        program = parse_file(path)
        ir_program = lower_program(program)
    except Exception:
        logger.exception("Failed to parse/lower component `%s` at %s", name, path)
        return None

    _COMPONENT_PROGRAM_CACHE[path] = ir_program
    return ir_program


def render_node(node, env: RuntimeEnvironment) -> str:
    context = env.to_context()
    if isinstance(node, IRText):
        return html.escape(str(_interpolate(node.value, context)))
    if isinstance(node, IRLet):
        env.set(node.name, _interpolate(node.value, context))
        return ""
    if isinstance(node, IRIf):
        branch = node.children if _evaluate(node.condition, context) else node.else_children
        return "".join(render_node(child, env.child()) for child in branch)
    if isinstance(node, IRFor):
        rendered = []
        items = _evaluate(node.iterable, context)
        for item in items or []:
            loop_env = env.child({node.var_name: item})
            rendered.append("".join(render_node(child, loop_env) for child in node.children))
        return "".join(rendered)
    if isinstance(node, IRScript):
        return f"<script>{node.raw_js}</script>"
    if isinstance(node, IRComponent):
        # Props are evaluated against the *caller's* context, since expressions
        # like `label "{count}"` refer to the caller's scope, not the component's.
        props = {prop["name"]: _interpolate(prop["value"], context) for prop in node.props}

        stack = context.get("__tw_component_stack__", ())
        if node.name in stack:
            chain = " -> ".join(stack + (node.name,))
            logger.error("Circular component reference detected: %s", chain)
            return (
                f'<div data-tw-component-error="circular" data-tw-component="{html.escape(node.name, quote=True)}">'
                f"Circular component reference: {html.escape(chain)}"
                f"</div>"
            )

        component_ir = _load_component_ir(node.name)
        if component_ir is None:
            # Fallback placeholder so a missing/broken component fails loudly
            # and visibly instead of silently breaking the page layout.
            children_html = "".join(render_node(child, env.child()) for child in node.children)
            props_html = "".join(
                f'<li><strong>{html.escape(str(key))}</strong>: {html.escape(str(value))}</li>'
                for key, value in props.items()
            )
            logger.warning("Component `%s` could not be resolved; rendering placeholder.", node.name)
            return (
                f'<div data-tw-component-error="not-found" data-tw-component="{html.escape(node.name, quote=True)}">'
                f"<div>Component not found: {html.escape(node.name)}</div>"
                f"<ul>{props_html}</ul>{children_html}</div>"
            )

        # Render the component's own body with its own lets/state plus the
        # props passed in by the caller. This is a fresh scope on purpose:
        # a component should not implicitly see the caller's unrelated variables.
        component_env = RuntimeEnvironment(
            values={
                **dict(component_ir.lets),
                **dict(component_ir.state),
                **props,
                "__tw_component_stack__": stack + (node.name,),
            }
        )
        return "".join(render_node(child, component_env) for child in component_ir.body)
    if isinstance(node, IRElement):
        attrs = _render_attrs(node.attrs, env)
        style_attr = _render_style(node.styles, env)
        event_attrs = _render_attrs(node.events, env)
        text = html.escape(str(_interpolate(node.text, context))) if node.text is not None else ""
        children = "".join(render_node(child, env.child()) for child in node.children)
        if node.tag in VOID_TAGS:
            return f"<{node.tag}{attrs}{style_attr}{event_attrs}>"
        return f"<{node.tag}{attrs}{style_attr}{event_attrs}>{text}{children}</{node.tag}>"
    return ""


def render_program(program: IRProgram, context: Optional[Dict] = None) -> str:
    env = RuntimeEnvironment(values={**dict(program.lets), **dict(program.state), **dict(context or {})})
    body = "".join(render_node(node, env) for node in program.body)
    title = html.escape(str(program.meta.get("title") or "TW Program"))
    return (
        "<!DOCTYPE html>"
        "<html>"
        "<head>"
        f"<title>{title}</title>"
        "</head>"
        f"<body>{body}</body>"
        "</html>"
    )


def render_program_document(ir_program: IRProgram, *, page_program=None, context: Optional[Dict] = None, css_href: Optional[str] = None) -> str:
    compiler = _legacy()
    merged_context = build_runtime_context(page_program, context=context) if page_program is not None else dict(context or {})
    if page_program is not None and getattr(page_program, "legacy_page", None) is not None:
        resolved_css = css_href
        if resolved_css is None:
            try:
                resolved_css, _ = compiler.read_global_stylesheet()
            except Exception as err:
                logger.exception("Failed to read global stylesheet")
                resolved_css = ""
        return compiler.render_html(page_program.legacy_page, merged_context, resolved_css or "")
    return render_program(ir_program, context=merged_context)


__all__ = ["build_runtime_context", "render_node", "render_program", "render_program_document"]

from __future__ import annotations

from .ast_nodes import ComponentNode, ElementNode, ForNode, IfNode, LetNode, Program, ScriptNode, TextNode
from .ir import IRComponent, IRElement, IRFor, IRIf, IRLet, IRProgram, IRScript, IRText


def lower_node(node):
    if isinstance(node, TextNode):
        return IRText(node.value)
    if isinstance(node, LetNode):
        return IRLet(node.name, node.value)
    if isinstance(node, IfNode):
        return IRIf(
            condition=node.condition,
            children=[lower_node(child) for child in node.children],
            else_children=[lower_node(child) for child in node.else_children],
        )
    if isinstance(node, ForNode):
        return IRFor(
            var_name=node.var_name,
            iterable=node.iterable,
            children=[lower_node(child) for child in node.children],
        )
    if isinstance(node, ScriptNode):
        return IRScript(node.raw_js)
    if isinstance(node, ComponentNode):
        return IRComponent(
            name=node.name,
            props=[{"name": prop.name, "value": prop.value} for prop in node.props],
            children=[lower_node(child) for child in node.children],
        )
    if isinstance(node, ElementNode):
        return IRElement(
            tag=node.tag,
            text=node.text,
            attrs=[{"name": attr.name, "value": attr.value} for attr in node.attrs],
            styles=[{"name": attr.name, "value": attr.value} for attr in node.styles],
            events=[{"name": attr.name, "value": attr.value} for attr in node.events],
            router=dict(node.router),
            children=[lower_node(child) for child in node.children],
        )
    raise TypeError(f"Unsupported AST node: {type(node)!r}")


def lower_program(program: Program) -> IRProgram:
    return IRProgram(
        meta={
            "title": program.meta.title,
            "layout": program.meta.layout,
            "layouts": list(program.meta.layouts),
            "render_mode": program.meta.render_mode,
            "revalidate": program.meta.revalidate,
            "redirect_to": program.meta.redirect_to,
            "rewrite_to": program.meta.rewrite_to,
            "responsive": program.meta.responsive,
        },
        head={
            "metas": list(program.head.metas),
            "icon": program.head.icon,
            "seo": dict(program.head.seo),
        },
        lets=dict(program.lets),
        state=dict(program.state),
        body=[lower_node(node) for node in program.body],
    )


__all__ = ["lower_node", "lower_program"]

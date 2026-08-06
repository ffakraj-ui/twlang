"""
TW Language Server Protocol (LSP) Server

Provides autocomplete and live diagnostics for .tw and .tss files in VS Code.

Run standalone:
    python -m tw_framework.lsp_server

The VS Code extension launches this automatically — no manual setup needed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from typing import Any, Dict, List, Optional


class LSPServer:
    """Minimal LSP server over stdio — JSON-RPC 2.0."""

    def __init__(self):
        self.root_uri: Optional[str] = None
        self.root_path: Optional[str] = None
        self.documents: Dict[str, str] = {}
        # Defer imports so the module loads even if the full compiler isn't present
        self._compiler = None
        self._semantic = None

    # ── Lazy framework imports ──────────────────────────────────────

    def _ensure_compiler(self):
        if self._compiler is None:
            try:
                from . import compiler
                self._compiler = compiler
            except Exception:
                self._compiler = False
        return self._compiler if self._compiler is not False else None

    def _ensure_semantic(self):
        if self._semantic is None:
            try:
                from . import semantic
                self._semantic = semantic
            except Exception:
                self._semantic = False
        return self._semantic if self._semantic is not False else None

    # ── JSON-RPC plumbing ────────────────────────────────────────────

    def _read_message(self) -> Optional[Dict]:
        try:
            headers = {}
            while True:
                line = sys.stdin.readline()
                if not line:
                    return None
                line = line.strip()
                if not line:
                    break
                if ":" in line:
                    key, _, val = line.partition(":")
                    headers[key.strip().lower()] = val.strip()
            length = int(headers.get("content-length", 0))
            if length <= 0:
                return None
            body = sys.stdin.read(length)
            return json.loads(body)
        except Exception:
            return None

    def _write_message(self, msg: Dict):
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n"
        sys.stdout.buffer.write(header.encode("utf-8"))
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()

    def _send_response(self, request_id: Any, result: Any):
        self._write_message({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        })

    def _send_notification(self, method: str, params: Dict):
        self._write_message({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })

    # ── Main loop ───────────────────────────────────────────────────

    def run(self):
        while True:
            msg = self._read_message()
            if msg is None:
                break
            method = msg.get("method", "")
            params = msg.get("params", {}) or {}
            request_id = msg.get("id")

            try:
                handler = getattr(self, f"_on_{method.replace('/', '_')}", None)
                if handler:
                    result = handler(params)
                    if request_id is not None:
                        self._send_response(request_id, result)
                elif method == "initialized":
                    pass  # ack, no response needed
                elif request_id is not None:
                    self._send_response(request_id, None)
            except Exception as e:
                if request_id is not None:
                    self._send_response(request_id, {
                        "error": {
                            "code": -32603,
                            "message": str(e),
                            "data": traceback.format_exc(),
                        }
                    })

    # ── LSP method handlers ─────────────────────────────────────────

    def _on_initialize(self, params: Dict) -> Dict:
        self.root_uri = params.get("rootUri") or params.get("rootPath", "")
        if self.root_uri:
            self.root_path = self.root_uri.replace("file://", "") if self.root_uri.startswith("file://") else self.root_uri
        return {
            "capabilities": {
                "textDocumentSync": 1,  # full document sync
                "completionProvider": {
                    "resolveProvider": False,
                    "triggerCharacters": [".", " ", "{"],
                },
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "openDiagnostics": True,
                },
                "hoverProvider": True,
                "definitionProvider": True,
                "documentFormattingProvider": False,
            },
            "serverInfo": {
                "name": "tw-language-server",
                "version": "0.1.0",
            },
        }

    def _on_textDocument_didOpen(self, params: Dict) -> None:
        doc = params.get("textDocument", {})
        uri = doc.get("uri", "")
        text = doc.get("text", "")
        self.documents[uri] = text
        self._publish_diagnostics(uri, text)

    def _on_textDocument_didChange(self, params: Dict) -> None:
        changes = params.get("contentChanges", [])
        if not changes:
            return
        uri = params.get("textDocument", {}).get("uri", "")
        # Full sync — last change wins
        text = changes[-1].get("text", "")
        self.documents[uri] = text
        self._publish_diagnostics(uri, text)

    def _on_textDocument_didClose(self, params: Dict) -> None:
        uri = params.get("textDocument", {}).get("uri", "")
        self.documents.pop(uri, None)
        # Clear diagnostics
        self._send_notification("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": [],
        })

    def _on_textDocument_completion(self, params: Dict) -> Dict:
        uri = params.get("textDocument", {}).get("uri", "")
        text = self.documents.get(uri, "")
        pos = params.get("position", {})
        line = pos.get("line", 0)
        char = pos.get("character", 0)
        items = self._get_completions(text, line, char, uri)
        return {"isIncomplete": False, "items": items}

    def _on_textDocument_hover(self, params: Dict) -> Optional[Dict]:
        uri = params.get("textDocument", {}).get("uri", "")
        text = self.documents.get(uri, "")
        pos = params.get("position", {})
        line = pos.get("line", 0)
        char = pos.get("character", 0)
        hover_text = self._get_hover(text, line, char)
        if hover_text:
            return {
                "contents": {"kind": "markdown", "value": hover_text},
            }
        return None

    def _on_textDocument_definition(self, params: Dict) -> Optional[Dict]:
        # Placeholder — full go-to-definition requires project index
        return None

    # ── Diagnostic engine ──────────────────────────────────────────

    def _publish_diagnostics(self, uri: str, text: str):
        diagnostics = []
        ext = uri.rsplit(".", 1)[-1].lower() if "." in uri else ""

        if ext in ("tw", "twm"):
            diagnostics = self._diagnose_tw(text, uri)
        elif ext == "tss":
            diagnostics = self._diagnose_tss(text, uri)

        self._send_notification("textDocument/publishDiagnostics", {
            "uri": uri,
            "diagnostics": diagnostics,
        })

    def _diagnose_tw(self, text: str, uri: str) -> List[Dict]:
        compiler = self._ensure_compiler()
        if not compiler:
            return []

        diagnostics: List[Dict] = []
        try:
            tokens = compiler.tokenize(text, allow_inline_scripts=True)
        except compiler.CompilerError as e:
            diagnostics.append(self._compiler_error_to_diagnostic(e, uri))
            return diagnostics
        except Exception:
            return diagnostics

        # Check for unterminated strings
        for token in tokens:
            if token.type == "STRING" and not token.value:
                diagnostics.append({
                    "range": self._token_range(token),
                    "severity": 1,
                    "source": "tw",
                    "message": "Empty or malformed string literal",
                })

        # Try full parse for deeper diagnostics
        try:
            nodes, _ = compiler.build_elements(
                compiler.tokenize(text, allow_inline_scripts=True),
                0,
                uri,
                text,
            )
        except compiler.CompilerError as e:
            diagnostics.append(self._compiler_error_to_diagnostic(e, uri))
        except Exception:
            pass

        # Check for unclosed braces
        brace_count = 0
        for token in tokens:
            if token.type == "BRACE":
                if token.value == "{":
                    brace_count += 1
                elif token.value == "}":
                    brace_count -= 1
        if brace_count != 0:
            diagnostics.append({
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
                "severity": 1,
                "source": "tw",
                "message": f"Unmatched braces — {'open' if brace_count > 0 else 'close'} brace missing ({abs(brace_count)} unmatched)",
            })

        return diagnostics

    def _diagnose_tss(self, text: str, uri: str) -> List[Dict]:
        compiler = self._ensure_compiler()
        if not compiler:
            return []

        diagnostics: List[Dict] = []
        try:
            sheet = compiler.build_tss_ast_from_text(text)
            css = compiler.render_css(sheet, context={})
        except compiler.CompilerError as e:
            diagnostics.append(self._compiler_error_to_diagnostic(e, uri))
        except Exception:
            pass

        # Check for broken 'true' values (the v0.4.2 multi-line bug)
        for i, line in enumerate(text.splitlines()):
            stripped = line.strip()
            if stripped.endswith(":") and not stripped.startswith("//") and not stripped.startswith("/*"):
                diagnostics.append({
                    "range": {
                        "start": {"line": i, "character": 0},
                        "end": {"line": i, "character": len(line)},
                    },
                    "severity": 2,
                    "source": "tw",
                    "message": "Property value starts on next line — consider putting the value on the same line to avoid parsing issues",
                })

        return diagnostics

    def _compiler_error_to_diagnostic(self, err, uri: str) -> Dict:
        line = 0
        char = 0
        if hasattr(err, "token") and err.token:
            line = max(0, (err.token.line or 1) - 1)
            char = max(0, (err.token.col or 1) - 1)
        elif hasattr(err, "line") and err.line:
            line = max(0, err.line - 1)
        message = err.message if hasattr(err, "message") else str(err)
        if hasattr(err, "suggestion") and err.suggestion:
            message += f"\n\nSuggestion: {err.suggestion}"
        return {
            "range": {
                "start": {"line": line, "character": char},
                "end": {"line": line, "character": char + 1},
            },
            "severity": 1,
            "source": "tw",
            "message": message,
        }

    # ── Completion engine ───────────────────────────────────────────

    def _get_completions(self, text: str, line: int, char: int, uri: str) -> List[Dict]:
        lines = text.splitlines()
        if line >= len(lines):
            return []
        current_line = lines[line][:char]
        ext = uri.rsplit(".", 1)[-1].lower() if "." in uri else ""

        if ext == "tss":
            return self._tss_completions(current_line)
        elif ext in ("tw", "twm"):
            return self._tw_completions(current_line, text)
        return []

    def _tw_completions(self, current_line: str, full_text: str) -> List[Dict]:
        stripped = current_line.strip()
        items: List[Dict] = []

        # Top-level directives inside page {} block
        page_keywords = ["title", "layout", "render", "revalidate", "redirect", "rewrite"]
        if stripped and not stripped.startswith("{") and not stripped.startswith("}"):
            # Check if we're typing a keyword
            word = stripped.split()[0].rstrip(":").lower() if stripped.split() else ""
            for kw in page_keywords:
                if kw.startswith(word) or word == "":
                    items.append({
                        "label": kw,
                        "kind": 14,  # Keyword
                        "detail": f"page directive",
                        "insertText": f'{kw} ',
                    })

        # HTML tags
        html_tags = [
            "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
            "a", "img", "ul", "ol", "li", "table", "tr", "td", "th",
            "form", "input", "button", "label", "select", "option",
            "section", "article", "header", "footer", "nav", "aside",
            "main", "figure", "figcaption", "video", "audio", "source",
            "canvas", "svg", "br", "hr", "meta", "link", "script", "style",
        ]
        for tag in html_tags:
            items.append({
                "label": tag,
                "kind": 7,  # Class — closest LSP kind for tags
                "detail": "HTML element",
                "insertText": tag,
            })

        # TW-specific constructs
        tw_keywords = [
            "page", "head", "body", "section", "layout", "load",
            "if", "else", "each", "for", "while",
            "on:click", "on:submit", "on:input", "on:change",
            "bind:value", "bind:checked", "bind:src",
            "text", "class", "id", "href", "src", "alt",
        ]
        for kw in tw_keywords:
            items.append({
                "label": kw,
                "kind": 14,  # Keyword
                "detail": "TW keyword",
                "insertText": kw,
            })

        # render modes
        render_modes = ["static", "server", "edge"]
        if "render" in current_line:
            for mode in render_modes:
                items.append({
                    "label": mode,
                    "kind": 21,  # Enum member
                    "detail": "render mode",
                    "insertText": mode,
                })

        return items

    def _tss_completions(self, current_line: str) -> List[Dict]:
        items: List[Dict] = []
        stripped = current_line.strip()

        # CSS property completions
        compiler = self._ensure_compiler()
        if compiler:
            for prop in sorted(compiler.CSS_PROPERTIES):
                items.append({
                    "label": prop,
                    "kind": 14,  # Keyword
                    "detail": "CSS property",
                    "insertText": f"{prop}: ",
                })

            # CSS aliases
            for alias, real in compiler.CSS_ALIASES.items():
                items.append({
                    "label": alias,
                    "kind": 14,
                    "detail": f"alias for {real}",
                    "insertText": f"{alias}: ",
                })

        # Common CSS values
        css_values = {
            "display": ["block", "flex", "grid", "inline", "inline-block", "none", "inline-flex"],
            "position": ["relative", "absolute", "fixed", "sticky", "static"],
            "flex-direction": ["row", "column", "row-reverse", "column-reverse"],
            "justify-content": ["center", "flex-start", "flex-end", "space-between", "space-around"],
            "align-items": ["center", "flex-start", "flex-end", "stretch", "baseline"],
            "text-align": ["left", "center", "right", "justify"],
            "overflow": ["hidden", "visible", "auto", "scroll"],
        }
        if ":" in current_line:
            prop_name = current_line.split(":")[0].strip().lower()
            if prop_name in css_values:
                for val in css_values[prop_name]:
                    items.append({
                        "label": val,
                        "kind": 21,  # Enum member
                        "detail": f"{prop_name} value",
                        "insertText": val,
                    })

        return items

    # ── Hover engine ────────────────────────────────────────────────

    def _get_hover(self, text: str, line: int, char: int) -> Optional[str]:
        lines = text.splitlines()
        if line >= len(lines):
            return None
        current_line = lines[line]
        word = self._extract_word(current_line, char)
        if not word:
            return None

        compiler = self._ensure_compiler()
        if not compiler:
            return None

        # HTML tag hover
        html_descriptions = {
            "div": "Block-level container element",
            "span": "Inline container element",
            "p": "Paragraph element",
            "a": "Anchor / link element — use `href` for the URL",
            "img": "Image element — use `src` for the image URL",
            "form": "Form element — wraps inputs and buttons",
            "input": "Input field — use `type` for the input type",
            "button": "Clickable button element",
            "ul": "Unordered (bulleted) list",
            "ol": "Ordered (numbered) list",
            "li": "List item — goes inside `ul` or `ol`",
            "h1": "Heading level 1",
            "h2": "Heading level 2",
            "h3": "Heading level 3",
            "section": "Thematic grouping of content",
            "header": "Page or section header",
            "footer": "Page or section footer",
            "nav": "Navigation links container",
        }
        if word.lower() in html_descriptions:
            return f"**{word}** — {html_descriptions[word.lower()]}"

        # CSS property hover
        if word in compiler.CSS_PROPERTIES:
            return f"**{word}** — CSS property"
        if word in compiler.CSS_ALIASES:
            return f"**{word}** — CSS alias for `{compiler.CSS_ALIASES[word]}`"

        # TW keyword hover
        tw_descriptions = {
            "page": "Defines page metadata: title, layout, render mode",
            "layout": "Specifies which layout file to use (from [home]/layouts/)",
            "render": "Sets the rendering mode: `static`, `server`, or `edge`",
            "load": "Imports a component, stylesheet, or JSON file",
            "on:click": "Binds a click handler to the element",
            "bind:value": "Two-way binds an input value to a variable",
            "if": "Conditional rendering — shows element only if condition is true",
            "each": "Loop rendering — repeats element for each item in a list",
        }
        if word in tw_descriptions:
            return f"**{word}** — {tw_descriptions[word]}"

        return None

    # ── Helpers ──────────────────────────────────────────────────────

    def _extract_word(self, line: str, char: int) -> str:
        if char > len(line):
            char = len(line)
        left = char
        while left > 0 and (line[left - 1].isalnum() or line[left - 1] in "-:_"):
            left -= 1
        right = char
        while right < len(line) and (line[right].isalnum() or line[right] in "-:_"):
            right += 1
        return line[left:right]

    def _token_range(self, token) -> Dict:
        line = max(0, (getattr(token, "line", 1) or 1) - 1)
        col = max(0, (getattr(token, "col", 1) or 1) - 1)
        return {
            "start": {"line": line, "character": col},
            "end": {"line": line, "character": col + max(1, len(getattr(token, "value", "")))},
        }


def main():
    server = LSPServer()
    server.run()


if __name__ == "__main__":
    main()

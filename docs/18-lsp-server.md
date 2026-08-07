# LSP and Editor Support

## LSP Server

TW Framework includes a built-in Language Server Protocol server at `tw_framework/lsp_server.py`.

### Features

- **Autocomplete** for `.tw` files (HTML tags, TW keywords, page directives, render modes)
- **Autocomplete** for `.tss` files (CSS properties, aliases, common values)
- **Live diagnostics** — real-time error checking as you type
- **Hover info** — documentation on hover for HTML tags, CSS properties, TW keywords

### Running the LSP Server

The LSP server runs over stdio (JSON-RPC 2.0):

```bash
python -m tw_framework.lsp_server
```

### VS Code Extension

The `vscode-tw/` folder contains a VS Code extension:

1. Copy `vscode-tw/` to `~/.vscode/extensions/tw-language/`
2. Restart VS Code
3. Open any `.tw` or `.tss` file

Features:
- Syntax highlighting (TextMate grammars)
- Autocomplete via LSP
- Live error diagnostics
- Hover documentation
- No auto-closing braces (disabled in v0.4.5+)

### ACode (Android) Plugin

The `tw-language-acode.zip` plugin works with ACode editor on Android:

1. Install `tw-framework` in Termux: `pip install tw-framework`
2. ACode → Settings → Language servers → Add custom server
3. Server ID: `tw`, Language IDs: `tw, twm, tss`
4. Type: `STDIO`, Install method: `Manual binary`
5. Binary: `/data/data/com.termux/files/usr/bin/python3`
6. Args: `["-m", "tw_framework.lsp_server"]`

### LSP Capabilities

```json
{
  "textDocumentSync": 1,
  "completionProvider": {
    "triggerCharacters": [".", " ", "{"]
  },
  "diagnosticProvider": true,
  "hoverProvider": true,
  "definitionProvider": true
}
```

### Diagnostic Severity

| Severity | Meaning |
|---|---|
| 1 (Error) | Syntax errors, unclosed braces, parse failures |
| 2 (Warning) | Multi-line CSS values, potential issues |

### Known Limitations

- File resolution errors (`load "missing.tss"`) are suppressed in LSP context
- Go-to-definition is not yet implemented (returns null)
- Document formatting is not supported

const { spawn } = require("child_process");
const {
  createConnection,
  TextDocuments,
  Diagnostic,
  DiagnosticSeverity,
  ProposedFeatures,
  InitializeResult,
  TextDocumentSyncKind,
  CompletionItem,
  CompletionItemKind,
  Hover,
  MarkupKind,
} = require("vscode-languageserver/node");

const { TextDocument } = require("vscode-languageserver-textdocument");

// Find the Python executable — prefer python3, fall back to python
function findPython() {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      require("child_process").execSync(`${cmd} --version`, { stdio: "pipe" });
      return cmd;
    } catch (e) {
      // try next
    }
  }
  return "python3";
}

const pythonBin = findPython();
const lspModule = "-m tw_framework.lsp_server";

// Spawn the Python LSP server
const py = spawn(pythonBin, ["-u", lspModule], {
  stdio: ["pipe", "pipe", "pipe"],
});

let pyBuffer = Buffer.alloc(0);

// Create connection over stdio
const connection = createConnection(ProposedFeatures.all);
const documents = new TextDocuments(TextDocument);
documents.listen(connection);

connection.onInitialize((params) => {
  return {
    capabilities: {
      textDocumentSync: TextDocumentSyncKind.Full,
      completionProvider: {
        resolveProvider: false,
        triggerCharacters: [".", " ", "{"],
      },
      hoverProvider: true,
      definitionProvider: true,
    },
    serverInfo: {
      name: "tw-language-server",
      version: "0.1.0",
    },
  };
});

// Forward document changes to Python LSP
function sendToPython(message) {
  const body = JSON.stringify(message);
  const header = `Content-Length: ${Buffer.byteLength(body)}\r\n\r\n`;
  py.stdin.write(header + body);
}

documents.onDidChangeContent((change) => {
  sendToPython({
    jsonrpc: "2.0",
    method: "textDocument/didChange",
    params: {
      textDocument: { uri: change.document.uri },
      contentChanges: [{ text: change.document.getText() }],
    },
  });
});

connection.onCompletion((textDocumentPosition) => {
  const uri = textDocumentPosition.textDocument.uri;
  const doc = documents.get(uri);
  if (!doc) return [];

  // Use the built-in JS completion logic as fallback
  const text = doc.getText();
  const lines = text.split(/\r?\n/);
  const line = textDocumentPosition.position.line;
  const char = textDocumentPosition.position.character;
  const currentLine = (lines[line] || "").substring(0, char);
  const ext = uri.split(".").pop().toLowerCase();

  let items = [];

  if (ext === "tss") {
    // CSS property completions
    const cssProps = [
      "display", "position", "top", "right", "bottom", "left",
      "width", "height", "min-width", "max-width", "min-height", "max-height",
      "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
      "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
      "border", "border-radius", "border-color", "border-style", "border-width",
      "box-shadow", "box-sizing", "outline",
      "background", "background-color", "background-image", "background-size",
      "background-position", "background-repeat", "background-attachment",
      "color", "font", "font-size", "font-family", "font-weight", "font-style",
      "line-height", "letter-spacing", "word-spacing",
      "text-align", "text-decoration", "text-transform", "text-shadow",
      "white-space", "word-break", "word-wrap",
      "flex", "flex-direction", "flex-wrap", "flex-flow",
      "justify-content", "align-items", "align-self", "align-content",
      "flex-grow", "flex-shrink", "flex-basis", "order", "gap",
      "grid", "grid-template", "grid-template-columns", "grid-template-rows",
      "grid-column", "grid-row", "grid-gap", "column-gap", "row-gap",
      "transition", "animation", "transform", "opacity", "cursor",
      "list-style", "pointer-events", "user-select", "content",
      "overflow", "overflow-x", "overflow-y", "z-index", "visibility",
      "float", "clear",
    ];

    for (const prop of cssProps) {
      items.push({
        label: prop,
        kind: CompletionItemKind.Keyword,
        detail: "CSS property",
        insertText: `${prop}: `,
      });
    }

    // CSS value completions after colon
    if (currentLine.includes(":")) {
      const prop = currentLine.split(":")[0].trim().toLowerCase();
      const valueMap = {
        display: ["block", "flex", "grid", "inline", "inline-block", "none", "inline-flex"],
        position: ["relative", "absolute", "fixed", "sticky", "static"],
        "flex-direction": ["row", "column", "row-reverse", "column-reverse"],
        "justify-content": ["center", "flex-start", "flex-end", "space-between", "space-around"],
        "align-items": ["center", "flex-start", "flex-end", "stretch", "baseline"],
        "text-align": ["left", "center", "right", "justify"],
        overflow: ["hidden", "visible", "auto", "scroll"],
      };
      if (valueMap[prop]) {
        for (const val of valueMap[prop]) {
          items.push({
            label: val,
            kind: CompletionItemKind.EnumMember,
            detail: `${prop} value`,
            insertText: val,
          });
        }
      }
    }
  } else if (ext === "tw" || ext === "twm") {
    // TW keywords
    const keywords = [
      "page", "head", "body", "section", "layout", "load",
      "title", "render", "revalidate", "redirect", "rewrite",
      "if", "else", "each", "for", "while",
    ];
    for (const kw of keywords) {
      items.push({
        label: kw,
        kind: CompletionItemKind.Keyword,
        detail: "TW keyword",
        insertText: `${kw} `,
      });
    }

    // HTML tags
    const tags = [
      "div", "span", "p", "h1", "h2", "h3", "h4", "h5", "h6",
      "a", "img", "ul", "ol", "li", "table", "tr", "td", "th",
      "form", "input", "button", "label", "select", "option",
      "section", "article", "header", "footer", "nav", "aside",
      "main", "figure", "figcaption", "video", "audio", "source",
      "canvas", "svg", "br", "hr", "meta", "link", "script", "style",
    ];
    for (const tag of tags) {
      items.push({
        label: tag,
        kind: CompletionItemKind.Class,
        detail: "HTML element",
        insertText: tag,
      });
    }

    // TW event/bind attributes
    const attrs = [
      "on:click", "on:submit", "on:input", "on:change",
      "bind:value", "bind:checked", "bind:src",
      "text", "class", "id", "href", "src", "alt",
    ];
    for (const attr of attrs) {
      items.push({
        label: attr,
        kind: CompletionItemKind.Keyword,
        detail: "TW attribute",
        insertText: attr,
      });
    }

    // render modes
    if (currentLine.includes("render")) {
      for (const mode of ["static", "server", "edge"]) {
        items.push({
          label: mode,
          kind: CompletionItemKind.EnumMember,
          detail: "render mode",
          insertText: mode,
        });
      }
    }
  }

  return items;
});

connection.onHover((params) => {
  const uri = params.textDocument.uri;
  const doc = documents.get(uri);
  if (!doc) return null;

  const text = doc.getText();
  const lines = text.split(/\r?\n/);
  const line = params.position.line;
  const char = params.position.character;
  const currentLine = lines[line] || "";

  // Extract word at position
  let left = char;
  while (left > 0 && /[\w:-]/.test(currentLine[left - 1])) left--;
  let right = char;
  while (right < currentLine.length && /[\w:-]/.test(currentLine[right])) right++;
  const word = currentLine.substring(left, right);

  if (!word) return null;

  const descriptions = {
    div: "Block-level container element",
    span: "Inline container element",
    p: "Paragraph element",
    a: "Anchor / link element — use `href` for the URL",
    img: "Image element — use `src` for the image URL",
    form: "Form element — wraps inputs and buttons",
    input: "Input field — use `type` for the input type",
    button: "Clickable button element",
    ul: "Unordered (bulleted) list",
    ol: "Ordered (numbered) list",
    li: "List item — goes inside `ul` or `ol`",
    page: "Defines page metadata: title, layout, render mode",
    layout: "Specifies which layout file to use (from [home]/layouts/)",
    render: "Sets the rendering mode: `static`, `server`, or `edge`",
    load: "Imports a component, stylesheet, or JSON file",
    "on:click": "Binds a click handler to the element",
    "bind:value": "Two-way binds an input value to a variable",
    if: "Conditional rendering — shows element only if condition is true",
    each: "Loop rendering — repeats element for each item in a list",
  };

  const desc = descriptions[word] || descriptions[word.toLowerCase()];
  if (desc) {
    return {
      contents: {
        kind: MarkupKind.Markdown,
        value: `**${word}** — ${desc}`,
      },
    };
  }

  return null;
});

// Listen for Python stderr (for debugging)
py.stderr.on("data", (data) => {
  connection.console.warn(`Python LSP stderr: ${data.toString()}`);
});

// Listen for Python stdout — parse JSON-RPC and forward diagnostics
py.stdout.on("data", (chunk) => {
  pyBuffer = Buffer.concat([pyBuffer, chunk]);
  while (true) {
    const headerEnd = pyBuffer.indexOf("\r\n\r\n");
    if (headerEnd === -1) break;
    const headerStr = pyBuffer.slice(0, headerEnd).toString();
    const match = headerStr.match(/Content-Length:\s*(\d+)/i);
    if (!match) break;
    const contentLength = parseInt(match[1], 10);
    const bodyStart = headerEnd + 4;
    if (pyBuffer.length < bodyStart + contentLength) break;
    const bodyStr = pyBuffer.slice(bodyStart, bodyStart + contentLength).toString();
    pyBuffer = pyBuffer.slice(bodyStart + contentLength);

    try {
      const msg = JSON.parse(bodyStr);
      if (msg.method === "textDocument/publishDiagnostics") {
        const uri = msg.params.uri;
        const diagnostics = (msg.params.diagnostics || []).map((d) => ({
          severity: d.severity === 1 ? DiagnosticSeverity.Error : d.severity === 2 ? DiagnosticSeverity.Warning : DiagnosticSeverity.Information,
          range: d.range,
          message: d.message,
          source: d.source || "tw",
        }));
        connection.sendDiagnostics({ uri, diagnostics });
      }
    } catch (e) {
      // Ignore parse errors
    }
  }
});

py.on("error", (err) => {
  connection.console.error(`Failed to spawn Python LSP server: ${err.message}`);
});

py.on("exit", (code) => {
  connection.console.warn(`Python LSP server exited with code ${code}`);
});

connection.listen();

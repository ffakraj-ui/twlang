const { join } = require("path");
const { workspace, window, ExtensionContext, LanguageClient, TransportKind } = require("vscode");

let client;

function activate(context) {
  const serverModule = join(context.extensionPath, "server.js");

  const serverOptions = {
    run: { module: serverModule, transport: TransportKind.stdio },
    debug: { module: serverModule, transport: TransportKind.stdio },
  };

  const clientOptions = {
    documentSelector: [
      { scheme: "file", language: "tw" },
      { scheme: "file", language: "tss" },
    ],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher("**/.{tw,tss,twm}"),
    },
  };

  client = new LanguageClient(
    "twLanguageServer",
    "TW Language Server",
    serverOptions,
    clientOptions
  );

  client.start();
}

function deactivate() {
  if (!client) return undefined;
  return client.stop();
}

module.exports = { activate, deactivate };

"use strict";
const vm = require("vm");
const pluginName = process.argv[2];
const hookName = process.argv[3];
const contextJson = process.argv[4] || "{}";
const ctx = JSON.parse(contextJson);
const sandbox = {
  console: {
    log: function() { process.stdout.write("[plugin:" + pluginName + "] " + Array.from(arguments).join(" ") + "\n"); },
    warn: function() { process.stderr.write("[plugin:" + pluginName + " WARNING] " + Array.from(arguments).join(" ") + "\n"); },
    error: function() { process.stderr.write("[plugin:" + pluginName + " ERROR] " + Array.from(arguments).join(" ") + "\n"); },
  },
  JSON: JSON,
  plugin: { register: function() {}, action: function() {}, filter: function() {} },
  tw: { log: function(m) { console.log(m); }, warn: function(m) { console.warn(m); } },
  ctx: {
    hook: hookName,
    log: function(m) { console.log(m); },
    warn: function(m) { console.warn(m); },
    error: function(m) { console.error(m); },
    redirect: function(url, status) { ctx.redirect = {url: url, status: status || 302}; },
    pages: ctx.pages || [],
    config: ctx.config || {},
    output_dir: ctx.output_dir || "dist",
    request: ctx.request || {},
    response: ctx.response || {},
  },
};
try {
  vm.createContext(sandbox);
  let body = "";
  process.stdin.on("data", function(chunk) { body += chunk; });
  process.stdin.on("end", function() {
    try {
      vm.runInContext(body, sandbox, { timeout: 5000 });
      process.stdout.write("\n__TW_RESULT__" + JSON.stringify({redirect: ctx.redirect, modified: true}) + "\n");
    } catch(e) {
      process.stderr.write("Plugin error: " + e.message + "\n");
      process.exit(1);
    }
  });
} catch(e) {
  process.stderr.write("Sandbox error: " + e.message + "\n");
  process.exit(1);
}

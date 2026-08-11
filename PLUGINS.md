# TW Framework Plugins (v0.9.08)

TW Framework ka plugin system WordPress-inspired hai. Plugins `.twp` (TW Plugin) format me hote hain aur restricted sandbox me run hote hain. Plugins sirf TW ke andar kaam karte hain — `plugin.register()`, `ctx`, `tw` sirf TW-specific APIs hain.

## Plugin Format (.twp)

Ek plugin ki structure:

```
.tw/plugins/
  my-plugin/
    plugin.json    # metadata
    plugin.twp     # plugin code (JS-like syntax)
```

### plugin.json

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My awesome TW plugin",
  "author": "Your Name",
  "permissions": ["read", "write"],
  "requires": []
}
```

### plugin.twp

```javascript
// Register hooks
plugin.register("beforeBuild", function(ctx) {
    ctx.log("Build starting...");
    // Modify pages, config, etc.
});

plugin.register("afterBuild", function(ctx) {
    ctx.log("Build complete!");
    // Post-build tasks
});

plugin.register("beforeRequest", function(ctx) {
    // Intercept requests
    var path = ctx.request.path;
    if (path === "/old-url") {
        ctx.redirect("/new-url");
    }
});

plugin.register("onRouteMatch", function(ctx) {
    // Custom route handling
    ctx.log("Route matched: " + ctx.request.path);
});
```

## Hooks

| Hook | When | Context |
|------|------|---------|
| `beforeBuild` | Build se pehle | `project_root`, `output_dir`, `pages`, `config` |
| `afterBuild` | Build ke baad | `project_root`, `output_dir`, `pages`, `config` |
| `beforeRequest` | Har request se pehle | `request`, `response`, `redirect()` |
| `afterRequest` | Har request ke baad | `request`, `response` |
| `onRouteMatch` | Route match hone par | `request`, `response` |

## Context Object (ctx)

Plugin hooks me `ctx` object milta hai:

```javascript
plugin.register("beforeBuild", function(ctx) {
    // Read project files
    var content = ctx.readFile("app/index.tw");

    // Write files
    ctx.writeFile("dist/custom.txt", "Hello");

    // Check file exists
    if (ctx.fileExists("config.json")) {
        // ...
    }

    // Access pages
    ctx.pages.forEach(function(page) {
        ctx.log("Page: " + page);
    });

    // Access config
    var title = ctx.config.title;

    // Output directory
    var outDir = ctx.output_dir;

    // Request/Response (in request hooks)
    var path = ctx.request.path;
    ctx.response.headers["X-Custom"] = "value";

    // Redirect (in request hooks)
    ctx.redirect("/new-url", 302);

    // Logging
    ctx.log("Info message");
    ctx.warn("Warning message");
    ctx.error("Error message");
});
```

## CLI Commands

### Plugin Install

```bash
# Registry se plugin install
tw plugin add my-plugin

# Alias
tw plugin install my-plugin
```

### Plugin Remove

```bash
tw plugin remove my-plugin

# Alias
tw plugin rm my-plugin
```

### Plugin List

```bash
# Installed plugins dekho
tw plugin list

# Alias
tw plugin ls
```

### Plugin Search

```bash
# Registry me available plugins dekho
tw plugin search
```

## Plugin Registry

Plugins `tw-origin/tw-plugins` GitHub repo me distribute hote hain. Registry ka URL:

```
https://raw.githubusercontent.com/tw-origin/tw-plugins/main/registry.json
```

Registry format:

```json
{
  "plugins": [
    {
      "name": "seo-booster",
      "version": "1.2.0",
      "description": "Automatic SEO meta tags and sitemap",
      "url": "plugins/seo-booster/"
    },
    {
      "name": "analytics",
      "version": "0.9.0",
      "description": "Privacy-first analytics integration",
      "url": "plugins/analytics/"
    }
  ]
}
```

## Permissions (Auto-Yes)

TW plugin system me **koi yes/no permission prompt nahi hai**. Agar plugin install kiya gaya hai, to saari permissions auto-granted hain. User ne explicit decision liya install karte time — baad me koi interrupt nahi.

`plugin.json` me `permissions` field sirf documentation ke liye hai — runtime pe koi check nahi karta.

## Security

1. **Sandbox Execution**: Plugins restricted namespace me run hote hain. `plugin`, `ctx`, `tw`, `console`, `JSON` sirf available APIs hain.

2. **Path Traversal Protection**: `ctx.readFile()` aur `ctx.writeFile()` project root ke bahar nahi ja sakte.

3. **Checksum Verification**: Future me plugin checksum verify hoga (planned for v0.10).

4. **.tw/ Auto-gitignore**: TW automatically `.tw/` ko `.gitignore` me add karta hai — plugins git me commit nahi hote.

## Plugin Dependencies

`plugin.json` me `requires` field se dependencies specify karo:

```json
{
  "name": "blog-suite",
  "version": "1.0.0",
  "requires": ["seo-booster", "analytics"]
}
```

Agar required plugin install nahi hai, to plugin load nahi hoga aur warning milegi.

## Creating Your Own Plugin

1. `.tw/plugins/` directory banao (agar nahi hai)

2. Plugin folder banao: `.tw/plugins/my-plugin/`

3. `plugin.json` banao:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "My custom plugin",
  "permissions": ["read", "write"]
}
```

4. `plugin.twp` banao:

```javascript
plugin.register("beforeBuild", function(ctx) {
    ctx.log("My plugin is running!");
});

plugin.register("afterBuild", function(ctx) {
    // Add custom file to output
    ctx.writeFile("dist/plugin-info.txt", "Generated by my-plugin");
});
```

5. Build karo: `tw build` — plugin automatically load hoga!

## Plugin API Reference

### plugin.register(hook, callback)
Hook register karo. Valid hooks: `beforeBuild`, `afterBuild`, `beforeRequest`, `afterRequest`, `onRouteMatch`.

### plugin.action(hook, callback)
Alias for `register()`.

### plugin.filter(name, callback)
Filter register karo (future use).

### tw.log(msg) / tw.warn(msg)
TW-specific logging.

### console.log(...) / console.warn(...) / console.error(...)
Standard console logging.

### JSON.stringify(obj) / JSON.parse(str)
JSON utilities.

## Differences from WordPress

| Feature | WordPress | TW Framework |
|---------|-----------|-------------|
| Plugin format | PHP files | `.twp` files (JS-like) |
| Hooks | Actions + Filters | Register + Actions |
| Distribution | WP.org repo | GitHub repo (PR-based) |
| Permissions | User approves per-action | Auto-yes (no prompts) |
| Sandbox | None | Restricted namespace |
| Storage | `wp-content/plugins/` | `.tw/plugins/` (gitignored) |

## Example Plugins

### SEO Booster

```javascript
plugin.register("beforeBuild", function(ctx) {
    ctx.pages.forEach(function(page) {
        ctx.log("Adding SEO meta to: " + page);
    });
});

plugin.register("afterBuild", function(ctx) {
    ctx.writeFile("dist/sitemap.xml", '<?xml version="1.0"?>\n<urlset></urlset>');
});
```

### Analytics

```javascript
plugin.register("afterBuild", function(ctx) {
    var script = '<script>window.tw_analytics=window.tw_analytics||[];</script>';
    ctx.writeFile("dist/analytics.js", script);
});
```

### Custom Redirects

```javascript
plugin.register("beforeRequest", function(ctx) {
    var redirects = {
        "/old-home": "/",
        "/legacy": "/new-page"
    };
    var path = ctx.request.path;
    if (redirects[path]) {
        ctx.redirect(redirects[path], 301);
    }
});
```

## Migration from v0.9.07

v0.9.07 se v0.9.08 me upgrade karte time:

1. Koi breaking change nahi hai — existing projects as-is work karenge.
2. Plugin system optional hai — agar `.tw/plugins/` nahi hai, to koi effect nahi.
3. Naye endpoints (`/__tw/revalidate`, `/__tw/db`, `/__tw/hmr`) automatically available hain.

## FAQ

**Q: Kya plugins production me run hote hain?**
A: `beforeBuild` aur `afterBuild` hooks build time pe run hote hain (production build me). `beforeRequest` aur `afterRequest` dev server pe run hote hain.

**Q: Plugin uninstall karne se kya hoga?**
A: Plugin folder delete ho jayega aur next build pe plugin load nahi hoga. Koi data loss nahi.

**Q: Multiple plugins same hook register karein to?**
A: Sab plugins execution order me run honge. Har plugin ka output next plugin ko input milta hai.

**Q: Plugin error se build fail hoga?**
A: Nahi — plugin errors catch hote hain aur warning show hoti hai. Build continue rehta hai.

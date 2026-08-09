# Migration Guide: v0.8.0 → v0.8.1

This guide helps you upgrade your TW Framework project from v0.8.0 to v0.8.1.

## Overview

v0.8.1 is a **fully backward-compatible** release. No code changes are required for existing projects — all changes are additive. The main additions are:

1. NPM Package Manager (`tw install`, `tw add`, `tw remove`, `tw list`)
2. React Compatibility Layer
3. Security Module (CSP, CSRF, sanitization, secure headers)
4. Enhanced Lib System (npm package resolution in .twm files)
5. Enhanced JS Interop (import maps generation)

## Step 1: Update the Framework

```bash
cd your-project
pip install tw-framework --upgrade
```

Or if you installed from a package:

```bash
pip install --upgrade tw-framework==0.8.1
```

## Step 2: Verify Your Project

```bash
# Check project health
tw doctor

# Build to verify everything still works
tw build
```

Your existing `.tw` pages, `.tss` styles, `.twm` modules, and API routes will work exactly as before.

## Step 3: Install NPM Packages (Optional)

v0.8.1 adds full npm package management. You can now install packages like Next.js:

```bash
# Install a single package
tw install react

# Install multiple packages
tw install react react-dom axios

# Install a specific version
tw install react@18.2.0

# Install as devDependency
tw install --save-dev jest

# Install all dependencies from package.json
tw install

# List installed packages
tw list
tw list --detailed

# Remove a package
tw remove lodash
```

When you install packages, TW automatically:
- Updates `package.json` with the dependency
- Runs `npm install` to fetch the package
- Updates `tw.config` `server.external_packages` to allow the package
- Detects React and provides setup hints

## Step 4: Use NPM Packages in .twm Files

You can now import npm packages directly in your `.twm` server-side modules:

```javascript
// [home]/lib/data.twm
import { fetchData } from "@/lib/api"

// Import npm packages (v0.8.1)
import axios from "axios"

export async function getProducts() {
    const response = await axios.get("https://api.example.com/products")
    return response.data
}

export client function formatPrice(price) {
    return "₹" + price.toFixed(2)
}
```

If a package is not installed, you'll get a helpful error:

```
Package 'axios' is not installed.
  Install it with: tw install axios
  Or: npm install axios
```

## Step 5: Use React (Optional)

v0.8.1 adds React compatibility. You can use React for specific interactive components while keeping TW's Zero-JS for static pages:

```bash
tw install react react-dom
```

Create a React component in a `.twm` file:

```javascript
// [home]/lib/counter-component.twm
import React, { useState } from "react"

export client function Counter() {
    const [count, setCount] = useState(0)
    return React.createElement("div", { className: "counter" },
        React.createElement("h2", null, "React Counter"),
        React.createElement("p", null, "Count: " + count),
        React.createElement("button", {
            onClick: () => setCount(count + 1)
        }, "Increment")
    )
}
```

Use it in a `.tw` page:

```tw
import { Counter } from "@/lib/counter-component"

page {
    title "React Demo"
    render interactive
}

body {
    div { id "react-root" }
    script { on:load "__tw.react.mount('Counter', 'react-root')" }
}
```

## Step 6: Use Security Features (Optional)

v0.8.1 adds a comprehensive security module:

### CSP Nonce

```python
from tw_framework.security import generate_csp_nonce, build_csp_header

nonce = generate_csp_nonce()
csp_header = build_csp_header(nonce=nonce)
# Use in your HTTP responses or HTML meta tags
```

### Secure Headers

```python
from tw_framework.security import get_secure_headers

headers = get_secure_headers(csp_nonce="your-nonce")
# Returns list of (name, value) tuples for HTTP response headers
```

### Input Sanitization

```python
from tw_framework.security import sanitize_html, sanitize_url, sanitize_js_string

safe_html = sanitize_html(user_input)
safe_url = sanitize_url(user_url)  # Blocks javascript: URLs
safe_js = sanitize_js_string(user_input)
```

### CSRF Protection

```python
from tw_framework.security import generate_csrf_token, validate_csrf_token

token = generate_csrf_token()
# Include in form, then validate on submit
if validate_csrf_token(submitted_token, expected_token):
    # Process form
    pass
```

## Step 7: Use Import Maps (Optional)

v0.8.1 generates ES Module import maps for client-side package resolution:

```python
from tw_framework.js_interop import JSInterop

interop = JSInterop(project_root=".")
import_map = interop.generate_import_map(imports, output_dir="dist")
script_tag = interop.render_import_map_script(import_map)
# Include in your HTML <head>
```

## What Changed

### New CLI Commands
| Command | Description |
|---------|-------------|
| `tw install <pkg>` | Install npm package(s) |
| `tw add <pkg>` | Alias for install |
| `tw install --dev <pkg>` | Install as devDependency |
| `tw install --exact <pkg>@ver` | Install exact version |
| `tw remove <pkg>` | Remove npm package |
| `tw rm <pkg>` | Alias for remove |
| `tw list` | List installed packages |
| `tw ls` | Alias for list |
| `tw list --detailed` | Show installed versions |

### New Modules
- `tw_framework/npm_manager.py` — NPM package management
- `tw_framework/react_compat.py` — React compatibility layer
- `tw_framework/security.py` — Security utilities (CSP, CSRF, sanitization)

### Enhanced Modules
- `tw_framework/lib_executor.py` — npm package resolution, better Node.js bridge
- `tw_framework/js_interop.py` — import maps generation, better npm loaders
- `tw_framework/twm_api_runner.js` — better package helper, install hints
- `tw_framework/cli.py` — new install/add/remove/list commands

### Breaking Changes

**None.** All changes are additive and backward compatible.

The only behavioral change is that `resolve_module_path()` in `lib_executor.py` now checks `node_modules` for npm-style package names before trying the project root. This only affects package names like `react`, `chart.js`, `axios` — not `@/lib/data` or `./utils` paths.

## Troubleshooting

### "Package not found" error in .twm files

If you see an error like:
```
Package 'axios' is not installed.
  Install it with: tw install axios
```

Run the suggested command:
```bash
tw install axios
```

### React not mounting

Make sure React is installed:
```bash
tw install react react-dom
tw list  # Verify they're installed
```

### tw.config not updating

The `tw.config` file is automatically updated when you use `tw install`. If it doesn't update, check that the file is writable and has a `server { }` block.

### Tests failing after upgrade

Run:
```bash
pip install tw-framework
python -m pytest tests/ -v
```

All 543 tests (474 existing + 69 new) should pass.

## Need Help?

- Check the [README.md](README.md) for full documentation
- See the [CHANGELOG.md](CHANGELOG.md) for all changes
- Run `tw doctor` for project health checks

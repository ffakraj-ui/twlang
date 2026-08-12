# NPM Packages & External Dependencies

TW Framework v0.9.30 adds full npm package management — just like Next.js. You can install, remove, and list npm packages directly from the TW CLI.

## Installing Packages

### Install a single package
```bash
tw install react
```

### Install multiple packages
```bash
tw install react react-dom axios
```

### Install a specific version
```bash
tw install react@18.2.0
```

### Install as devDependency
```bash
tw install --save-dev jest
```

### Install exact version (no ^ prefix)
```bash
tw install --exact react@18.2.0
```

### Install all dependencies from package.json
```bash
tw install
```

### Using `tw add` (alias)
```bash
tw add lodash
```

## Removing Packages

```bash
tw remove lodash
tw rm lodash          # alias
```

## Listing Packages

```bash
tw list
tw ls                 # alias
tw list --detailed    # show installed versions
```

## How It Works

When you run `tw install <package>`:

1. **package.json** is updated with the dependency
2. **npm install** is run to fetch the package
3. **tw.config** `server.external_packages` is auto-updated
4. The package is available in `.twm` files immediately

## Using NPM Packages in .twm Files

### Server-side (build-time execution)

```javascript
// [home]/lib/data.twm
import axios from "axios"

export async function getProducts() {
    const response = await axios.get("https://api.example.com/products")
    return response.data
}
```

### Client-side (shipped to browser)

```javascript
// [home]/lib/utils.twm
import { format } from "date-fns"

export client function formatDate(date) {
    return format(new Date(date), "dd/MM/yyyy")
}
```

## Package Manager Detection

TW auto-detects your package manager from lockfiles:

| Lockfile | Package Manager |
|----------|----------------|
| `package-lock.json` | npm |
| `pnpm-lock.yaml` | pnpm |
| `yarn.lock` | yarn |
| `bun.lockb` | bun |

If no lockfile exists, TW uses whatever is available on PATH (defaults to npm).

## tw.config Integration

When you install packages, TW automatically updates your `tw.config`:

```
server {
  external_packages [
    "react",
    "react-dom",
    "axios"
  ]
}
```

This tells the build system these packages are allowed and should be resolved from `node_modules`.

## Error Messages

If you try to use a package that isn't installed, you'll get a helpful error:

```
Package 'axios' is not installed.
  Install it with: tw install axios
  Or: npm install axios
```

## Import Maps

For client-side ESM resolution, TW generates import maps:

```html
<script type="importmap">
{
  "imports": {
    "react": "/_tw/chunks/npm/react.abc123.js",
    "react-dom": "/_tw/chunks/npm/react-dom.def456.js"
  }
}
</script>
```

This allows browser-native ESM imports like:
```javascript
import React from "react"
```

## See Also

- [React Usage Guide](REACT_USAGE.md)
- [Migration Guide](MIGRATION_V0.8.1.md)
- [Security Features](SECURITY.md)

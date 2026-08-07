# Lifecycle Hooks

## on load init

Run initialization code when a page loads:

```tw
on load init "setupPage"
on load init "loadUserData"

body {
    h1 "Welcome"
}
```

The handler functions are defined in `script {}` blocks:

```tw
script {
    function setupPage() {
        document.title = "My Page"
    }

    function loadUserData() {
        const user = JSON.parse(localStorage.getItem('user'))
        if (user) {
            // Update UI
        }
    }
}
```

## Hook Resolution

Hooks reference functions by name. TW resolves them in this order:
1. Inline `script {}` block in the same `.tw` file
2. Loaded `.twm` modules
3. Global functions on `window`

## Multiple Hooks

```tw
on load init "checkAuth"
on load init "loadTheme"
on load init "registerServiceWorker"
```

Hooks run in order - first declared, first executed.

## Hook in Layouts

Hooks defined in layouts run before page-level hooks:

```tw
// [home]/layouts/main.tw
on load init "initLayout"

html {
    body { {children} }
}
```

Execution order: layout hooks first, then page hooks.

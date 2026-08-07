# Getting Started

## Install

```bash
pip install tw-framework
```

Requires Python 3.9+. No Node.js, no npm.

## Create a Project

```bash
tw create my-site
cd my-site
tw dev
```

Open `http://127.0.0.1:3000` — live-reloading dev server.

## Your First Page

`[home]/pages/index.tw`:

```tw
page {
    title "Hello World"
    layout "main"
    render static
}

body {
    div {
        class "hero"
        h1 "Built with TW Framework"
        p "Zero JavaScript. Pure HTML."
    }
}
```

## Add Styles

`[home]/style.tss`:

```css
.hero {
    text-align: center
    padding: 80px 20px
}
```

## Build and Deploy

```bash
tw build --prod
tw deploy
```

## Next Steps

- [TW Syntax](./02-tw-syntax.md)
- [TSS Syntax](./03-tss-syntax.md)
- [CLI Reference](./05-cli-reference.md)
- [Routing](./06-routing.md)

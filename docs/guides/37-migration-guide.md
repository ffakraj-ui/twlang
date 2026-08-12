# Migration Guide

## From HTML/CSS

TW's syntax is HTML-like, so migration is straightforward:

### Before (HTML)
```html
<div class="card">
    <h1>Hello World</h1>
    <p>Welcome to my site</p>
    <a href="/about" class="btn">Learn More</a>
</div>
```

### After (TW)
```tw
div {
    class "card"
    h1 "Hello World"
    p "Welcome to my site"
    a "Learn More" { href "/about", class "btn" }
}
```

### CSS to TSS

Remove semicolons, use aliases:

```css
/* Before */
.card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
```

```css
/* After (TSS) */
.card {
    bg #fff
    radius 12px
    shadow 0 2px 8px rgba(0,0,0,0.1)
}
```

## From Next.js

### Page structure

**Next.js:**
```jsx
// pages/index.js
export default function Home() {
    return (
        <div className="container">
            <h1>Hello World</h1>
        </div>
    );
}
```

**TW:**
```tw
// [home]/index.tw
page { title "Home", render static }

body {
    div {
        class "container"
        h1 "Hello World"
    }
}
```

### Components

**Next.js:**
```jsx
// components/Button.jsx
export default function Button({ text, onClick }) {
    return <button onClick={onClick} className="btn">{text}</button>;
}
```

**TW:**
```tw
// [home]/components/Button.tw
button "{text}" {
    class "btn"
    on:click "{onClick}"
}
```

### API Routes

**Next.js:**
```js
// pages/api/hello.js
export default function handler(req, res) {
    res.status(200).json({ message: "Hello" });
}
```

**TW:**
```js
// [home]/api/hello.twm
export function GET(request) {
    return { status: 200, json: { message: "Hello" } };
}
```

### Styles

**Next.js:** CSS Modules, styled-components, Tailwind
**TW:** `.tss` files with simplified syntax

### Key differences

| Next.js | TW |
|---|---|
| JSX (HTML in JS) | `.tw` (HTML-like syntax) |
| `npm install` | `pip install` |
| React runtime (~90KB) | Zero JS by default |
| `useState` hook | `let` + `bind:value` |
| `useEffect` | `script {}` block |
| `getServerSideProps` | `render server` |

## From Astro

TW and Astro share similar philosophy (zero JS by default). Migration is easier:

| Astro | TW |
|---|---|
| `.astro` files | `.tw` files |
| `---` code fence | `let` at top level |
| `client:visible` | `on:click` / `bind:value` |
| `npm` ecosystem | `pip` ecosystem |
| Node.js required | Python (runs on mobile) |

# Migrating from React / Next.js

Moving from React to TW Framework? This guide maps React concepts to TW equivalents.

## Philosophy Shift

| React / Next.js | TW Framework |
|-----------------|--------------|
| Component = JS function | Component = `.tw` file |
| JSX syntax | TW syntax (HTML-like) |
| Virtual DOM | Direct HTML compilation |
| Client-side hydration | Zero JS by default |
| `useState` / `useEffect` | `let` + `on:click` / `bind:` |
| `getStaticProps` | `render static` + JSON data |
| `getServerSideProps` | `render server` + `.twm` |
| `pages/_app.js` | `layouts/main.tw` |
| `pages/index.js` | `[home]/index.tw` |
| `public/` folder | `[home]/assets/` |

## Component Conversion

### React Component

```jsx
// components/Hero.jsx
export default function Hero({ title, subtitle, ctaText, ctaLink }) {
  return (
    <section className="hero">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
      <a href={ctaLink} className="btn btn-primary">
        {ctaText}
      </a>
    </section>
  );
}
```

### TW Equivalent

```tw
// components/Hero.tw
let title = ""
let subtitle = ""
let ctaText = "Get Started"
let ctaLink = "/"

section {
    class "hero"
    h1 "{title}"
    if subtitle {
        p "{subtitle}"
    }
    a "{ctaText}" {
        href "{ctaLink}"
        class "btn btn-primary"
    }
}
```

### Usage

```tw
// React
<Hero title="Welcome" subtitle="Build fast" ctaText="Learn More" ctaLink="/docs" />

// TW
Hero {
    title "Welcome"
    subtitle "Build fast"
    ctaText "Learn More"
    ctaLink "/docs"
}
```

## State Management

### React useState

```jsx
const [count, setCount] = useState(0);

<button onClick={() => setCount(count + 1)}>
  Count: {count}
</button>
```

### TW Reactive State

```tw
button "Count: {count}" {
    on:click "count++"
    class "counter-btn"
}
```

### React useEffect

```jsx
useEffect(() => {
  document.title = `Count: ${count}`;
}, [count]);
```

### TW Equivalent

TW compiles to static HTML. For side effects, use inline scripts sparingly:

```tw
script {
    // Only for pages that need it
    document.title = 'Dynamic Title';
}
```

For complex state, prefer `.twm` API routes.

## Routing

### Next.js File-Based Routing

```
pages/
  index.js
  about.js
  blog/
    [slug].js
```

### TW File-Based Routing

```
[home]/
  index.tw
  about.tw
  blog/
    [slug].tw
```

### Next.js Dynamic Routes

```jsx
// pages/blog/[slug].js
export async function getStaticProps({ params }) {
  const post = await fetchPost(params.slug);
  return { props: { post } };
}
```

### TW Dynamic Routes

```tw
// [home]/blog/[slug].tw
page {
    title "{post.title}"
    layout "main"
    render static
}

body {
    article {
        h1 "{post.title}"
        time "{post.date}"
        div { class "content" "{post.body}" }
    }
}
```

With `[home]/blog/[slug].json`:

```json
[
  {"slug": "hello-world", "title": "Hello World", "date": "2024-01-15", "body": "..."},
  {"slug": "getting-started", "title": "Getting Started", "date": "2024-01-20", "body": "..."}
]
```

## Styling

### React (CSS Modules)

```jsx
import styles from './Button.module.css';
<button className={styles.primary}>Click</button>
```

### TW (TSS)

```tw
load "@./style/button.tss"
button "Click" { class "btn-primary" }
```

```css
/* button.tss */
.btn-primary {
    background: #22c55e
    color: white
    padding: 12px 24px
    radius: 8px
}
```

## Data Fetching

### React (useEffect + fetch)

```jsx
useEffect(() => {
  fetch('/api/products')
    .then(r => r.json())
    .then(data => setProducts(data));
}, []);
```

### TW (Static with JSON)

```tw
let products = load_json "products"

each products as product {
    ProductCard { props product }
}
```

### TW (Server-rendered)

```tw
page {
    render server
}

let products = fetch "https://api.example.com/products"
```

## Common Pitfalls

1. **No Virtual DOM**: TW generates static HTML. You cannot diff and patch like React.
2. **No hooks**: `useState`, `useEffect`, `useContext` don't exist. Use `let` and `on:` directives.
3. **No JSX expressions**: `{condition && <Component />}` becomes `if condition { Component {} }`.
4. **No npm packages**: TW doesn't use `node_modules`. Use CDN links or inline scripts.
5. **No HMR**: TW has live reload, not hot module replacement.

## Migration Checklist

- [ ] Audit all React components and map to TW components
- [ ] Convert JSX to TW syntax
- [ ] Replace `useState` with `let` + reactive directives
- [ ] Move CSS Modules to `.tss` files
- [ ] Convert `getStaticProps` / `getServerSideProps` to `render static` / `render server`
- [ ] Move `public/` assets to `[home]/assets/`
- [ ] Replace React Router links with `goto` directives
- [ ] Test all interactive features
- [ ] Verify SEO meta tags
- [ ] Run performance audit (should be faster!)

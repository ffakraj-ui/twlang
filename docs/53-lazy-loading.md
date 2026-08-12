# Lazy Loading

## Image Lazy Loading

```tw
img {
    src "/images/hero.jpg"
    alt "Hero"
    loading "lazy"
    width 1200
    height 600
}
```

## Responsive Images

```tw
img {
    src "/images/hero.jpg"
    srcset "/images/hero-small.jpg 640w, /images/hero-medium.jpg 1024w, /images/hero-large.jpg 1920w"
    sizes "(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
    alt "Hero"
    loading "lazy"
}
```

## Defer Non-Critical CSS

```tw
head {
    load "@./style/critical.tss"
}

body {
    h1 "Welcome"
}

script {
    function loadDeferredCSS() {
        const link = document.createElement('link')
        link.rel = 'stylesheet'
        link.href = '/_tw/static/chunks/non-critical.css'
        document.head.appendChild(link)
    }
    window.addEventListener('load', loadDeferredCSS)
}
```

## Font Loading

```tw
head {
    link {
        rel "preload"
        href "/fonts/inter.woff2"
        as "font"
        type "font/woff2"
        crossorigin "anonymous"
    }
}
```

```css
@font-face {
    font-family 'Inter'
    src url('/fonts/inter.woff2') format('woff2')
    font-display swap
}
```

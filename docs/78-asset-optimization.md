# Asset Optimization

## Image Optimization

TW does not process images. Use pre-compressed formats:

### WebP

```bash
cwebp image.jpg -o image.webp -q 80
```

```tw
img { src "/images/hero.webp", alt "Hero", loading "lazy" }
```

### Picture Element

```tw
picture {
    source { srcset "/images/hero.avif", type "image/avif" }
    source { srcset "/images/hero.webp", type "image/webp" }
    img { src "/images/hero.jpg", alt "Hero" }
}
```

## Font Optimization

### Preload Critical Fonts

```tw
head {
    link { rel "preload", href "/fonts/inter.woff2", as "font", type "font/woff2", crossorigin "anonymous" }
}
```

### Use font-display: swap

```css
@font-face {
    font-family 'Inter'
    src url('/fonts/inter.woff2') format('woff2')
    font-display swap
}
```

## Precompression

`tw build --prod` generates `.gz` and `.br` files:

```
style.css
style.css.gz    (gzip, ~70% smaller)
style.css.br    (brotli, ~75% smaller)
```

## Measuring Performance

```bash
tw build --prod --report
```

Check: total output size, per-page sizes, JS chunk sizes, Gzip/Brotli savings.

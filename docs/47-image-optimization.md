# Image Optimization

TW Framework does not include built-in image optimization. Use pre-compressed images.

## Using Images

```tw
img {
    src "/images/hero.webp"
    alt "Hero image"
    width 1200
    height 600
    loading "lazy"
    decoding "async"
}
```

## Best Practices

### Modern Formats

| Format | Use Case | Size |
|---|---|---|
| WebP | Photos | 25-35% smaller than JPEG |
| AVIF | Modern browsers | 50% smaller than JPEG |
| SVG | Icons, logos | Vector, scalable |
| PNG | Transparency | Larger |

### Lazy Loading

```tw
// Below the fold
img { src "/images/feature.webp", loading "lazy" }

// Above the fold
img { src "/images/hero.webp", loading "eager", fetchpriority "high" }
```

### Responsive Images

```tw
img {
    src "/images/hero.webp"
    srcset "/images/hero-480.webp 480w, /images/hero-800.webp 800w, /images/hero-1200.webp 1200w"
    sizes "(max-width: 600px) 480px, (max-width: 900px) 800px, 1200px"
    width 1200
    height 600
}
```

### Pre-compress Images

```bash
cwebp -q 80 image.jpg -o image.webp

for f in images/*.jpg; do
    cwebp -q 80 "$f" -o "${f%.jpg}.webp"
done
```

## Image CDN

Configure remote patterns in tw.config:

```
images {
  remote_patterns [
    { protocol: "https", hostname: "**" }
  ]
  unoptimized true
}
```

## SVG Icons

```tw
svg {
    width 24
    height 24
    viewBox "0 0 24 24"
    fill "none"
    stroke "currentColor"
    stroke-width 2
    path { d "M12 2L2 7l10 5 10-5-10-5z" }
}
```

## OG Images

```tw
head {
    meta { property "og:image", content "https://example.com/og-image.png" }
    meta { property "og:image:width", content "1200" }
    meta { property "og:image:height", content "630" }
}
```

## Performance Budget

| Image Type | Max Size |
|---|---|
| Hero image | < 200 KB |
| Product image | < 100 KB |
| Thumbnail | < 30 KB |
| Icon (SVG) | < 5 KB |

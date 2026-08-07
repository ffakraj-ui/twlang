# Animations and Transitions

## CSS Transitions

```css
.btn {
    bg #22c55e
    color white
    transition background 0.2s ease, transform 0.1s ease, box-shadow 0.3s ease

    &:hover {
        bg #16a34a
        transform translateY(-2px)
        shadow 0 8px 20px rgba(34,197,94,0.3)
    }

    &:active {
        transform translateY(0)
        shadow 0 2px 8px rgba(34,197,94,0.2)
    }
}
```

## Keyframe Animations

```css
@keyframes fadeIn {
    0% { opacity 0, transform translateY(20px) }
    100% { opacity 1, transform translateY(0) }
}

@keyframes pulse {
    0%, 100% { transform scale(1) }
    50% { transform scale(1.05) }
}

@keyframes spin {
    0% { transform rotate(0deg) }
    100% { transform rotate(360deg) }
}

.element { animation fadeIn 0.4s ease-out }
.badge { animation pulse 2s infinite }
.spinner { animation spin 0.8s linear infinite }
```

## Staggered Animations

```css
.list .item:nth-child(1) { animation fadeIn 0.3s ease-out 0s both }
.list .item:nth-child(2) { animation fadeIn 0.3s ease-out 0.1s both }
.list .item:nth-child(3) { animation fadeIn 0.3s ease-out 0.2s both }
.list .item:nth-child(4) { animation fadeIn 0.3s ease-out 0.3s both }
```

## Hover Effects

```css
.card {
    transition all 0.3s ease
    cursor pointer

    &:hover {
        transform translateY(-4px) scale(1.02)
        shadow 0 12px 30px rgba(0,0,0,0.15)
    }
}

.image-zoom {
    overflow hidden

    img {
        transition transform 0.4s ease
    }

    &:hover img {
        transform scale(1.1)
    }
}
```

## Loading States

```css
.skeleton {
    bg linear-gradient(90deg, #e0e0e0 25%, #f0f0f0 50%, #e0e0e0 75%)
    bg-size 200% 100%
    animation shimmer 1.5s infinite
    radius 4px
}

@keyframes shimmer {
    0% { bg-position 200% 0 }
    100% { bg-position -200% 0 }
}
```

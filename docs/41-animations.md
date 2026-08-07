# Animations and Transitions

## CSS Transitions

```css
.button {
    transition all 0.3s ease
    bg #22c55e
}

.button:hover {
    bg #16a34a
    transform translateY(-2px)
    shadow 0 4px 12px rgba(0,0,0,0.15)
}
```

## Keyframe Animations

```css
@keyframes fadeIn {
    0% { opacity 0 }
    100% { opacity 1 }
}

@keyframes slideUp {
    0% { transform translateY(20px), opacity 0 }
    100% { transform translateY(0), opacity 1 }
}

.hero {
    animation fadeIn 0.5s ease-in
}

.card {
    animation slideUp 0.4s ease-out
}
```

## Multiple Animations

```css
.element {
    animation fadeIn 0.3s ease-in, slideUp 0.4s ease-out 0.1s
}
```

## Animation Properties

| Property | Description |
|---|---|
| `animation-name` | Keyframe name |
| `animation-duration` | Time (e.g. 0.3s) |
| `animation-timing-function` | ease, linear, ease-in, ease-out, ease-in-out |
| `animation-delay` | Delay before start |
| `animation-iteration-count` | 1, infinite, or number |
| `animation-direction` | normal, reverse, alternate |

## Transform

```css
.card {
    transform rotate(5deg) scale(1.05)
}

.card:hover {
    transform rotate(0deg) scale(1.1)
    transition transform 0.3s ease
}
```

## Loading Spinner

```css
@keyframes spin {
    0% { transform rotate(0deg) }
    100% { transform rotate(360deg) }
}

.spinner {
    width 24px
    height 24px
    border 3px solid #e5e7eb
    border-top-color #3b82f6
    border-radius 50%
    animation spin 0.8s linear infinite
}
```

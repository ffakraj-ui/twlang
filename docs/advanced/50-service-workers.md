# Service Workers and PWA

## Basic Service Worker

Create `[home]/static/sw.js`:

```js
const CACHE_NAME = 'tw-site-v1'
const ASSETS = ['/', '/style.css']

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS)))
})

self.addEventListener('fetch', (e) => {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)))
})
```

## Register Service Worker

```tw
on load init "registerSW"

script {
    function registerSW() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
        }
    }
}
```

## Web App Manifest

Create `[home]/static/manifest.json`:

```json
{
    "name": "My TW Site",
    "short_name": "MySite",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#22c55e",
    "icons": [
        { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
        { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
    ]
}
```

## Link Manifest

```tw
head {
    link { rel "manifest", href "/manifest.json" }
    meta { name "theme-color", content "#22c55e" }
    link { rel "apple-touch-icon", href "/icon-192.png" }
}
```

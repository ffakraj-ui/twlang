# Progressive Web App (PWA) Guide

Turn your TW Framework site into an installable Progressive Web App.

## What is a PWA?

A Progressive Web App works offline, can be installed on home screens, and feels like a native app — while remaining a website.

## Requirements

1. **HTTPS**: PWAs require a secure origin.
2. **Web App Manifest**: JSON file describing the app.
3. **Service Worker**: Enables offline caching and background sync.

## Step 1: Web App Manifest

Create `[home]/assets/manifest.json`:

```json
{
  "name": "My TW App",
  "short_name": "TW App",
  "description": "A fast site built with TW Framework",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#22c55e",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/assets/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/assets/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "categories": ["productivity", "utilities"],
  "screenshots": [
    {
      "src": "/assets/screenshots/home.png",
      "sizes": "1280x720",
      "type": "image/png",
      "form_factor": "wide"
    }
  ]
}
```

Link it in your layout:

```tw
head {
    link { rel "manifest" href "/assets/manifest.json" }
    meta { name "theme-color" content "#22c55e" }
    meta { name "apple-mobile-web-app-capable" content "yes" }
    meta { name "apple-mobile-web-app-status-bar-style" content "black-translucent" }
    link { rel "apple-touch-icon" href "/assets/icons/icon-192.png" }
}
```

## Step 2: Service Worker

Create `[home]/assets/sw.js`:

```javascript
const CACHE_NAME = 'tw-app-v1';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/about.html',
  '/assets/style.css',
  '/assets/main.js'
];

// Install — cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch — serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      // Return cached version or fetch from network
      return response || fetch(event.request).then((fetchResponse) => {
        // Cache new requests for static assets
        if (event.request.url.match(/\.(css|js|png|jpg|webp|avif|woff2)$/)) {
          const clone = fetchResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return fetchResponse;
      });
    })
  );
});
```

Register it in your layout:

```tw
script {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/assets/sw.js')
        .then((reg) => console.log('SW registered:', reg.scope))
        .catch((err) => console.log('SW registration failed:', err));
    });
  }
}
```

## Step 3: Offline Page

Create `[home]/offline.tw`:

```tw
page {
    title "Offline"
    layout "main"
    render static
}

body {
    div {
        class "offline-page"
        h1 "You are offline"
        p "Please check your internet connection and try again."
        button "Retry" { on:click "window.location.reload()" }
    }
}
```

Add to service worker:

```javascript
// In sw.js fetch handler
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).catch(() => {
        if (event.request.mode === 'navigate') {
          return caches.match('/offline.html');
        }
      });
    })
  );
});
```

## Step 4: Install Prompt

Show a custom install button:

```tw
button "Install App" {
    id "install-btn"
    class "btn btn-primary"
    style "display: none"
    on:click "installPWA()"
}
```

```javascript
script {
  let deferredPrompt;
  const installBtn = document.getElementById('install-btn');

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBtn.style.display = 'block';
  });

  function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then((choice) => {
      if (choice.outcome === 'accepted') {
        console.log('User installed PWA');
      }
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });
  }
}
```

## Advanced Features

### Background Sync

Queue actions for when connectivity returns:

```javascript
// In your page script
async function submitForm(data) {
  try {
    await fetch('/api/submit', { method: 'POST', body: JSON.stringify(data) });
  } catch (err) {
    // Queue for background sync
    await navigator.serviceWorker.ready.then((sw) => {
      return sw.sync.register('submit-form');
    });
    showNotification('Form saved. Will submit when online.');
  }
}
```

```javascript
// In sw.js
self.addEventListener('sync', (event) => {
  if (event.tag === 'submit-form') {
    event.waitUntil(submitQueuedForms());
  }
});
```

### Push Notifications

```javascript
// Request permission
Notification.requestPermission().then((permission) => {
  if (permission === 'granted') {
    subscribeToPush();
  }
});
```

## Testing Your PWA

1. **Lighthouse**: Run the PWA audit in Chrome DevTools.
2. **Chrome DevTools > Application**: Check manifest, service workers, and cache.
3. **Real devices**: Test install on Android Chrome and iOS Safari.

## PWA Checklist

- [ ] `manifest.json` is valid and linked
- [ ] Icons in multiple sizes (192px, 512px)
- [ ] Service worker registered and functioning
- [ ] Site works offline (cached pages load)
- [ ] Install prompt works on supported browsers
- [ ] HTTPS is enabled in production
- [ ] Theme color matches brand
- [ ] Lighthouse PWA score >= 90

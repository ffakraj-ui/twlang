# Analytics Integration

## Google Analytics

```tw
let gaId = "{GA_TRACKING_ID}"

head {
    script {
        const s = document.createElement('script')
        s.async = true
        s.src = 'https://www.googletagmanager.com/gtag/js?id=' + '{gaId}'
        document.head.appendChild(s)
        window.dataLayer = window.dataLayer || []
        function gtag() { dataLayer.push(arguments) }
        gtag('js', new Date())
        gtag('config', '{gaId}')
    }
}
```

## Plausible Analytics

```tw
head {
    script { src "https://plausible.io/js/script.js", data-domain "mysite.com" }
}
```

## Custom Event Tracking

```tw
button "Download" {
    on:click "trackEvent('download', { id: 'ebook' })"
    class "btn btn-primary"
}

script {
    function trackEvent(name, data) {
        if (typeof gtag !== 'undefined') {
            gtag('event', name, data)
        }
    }
}
```

## Environment Variable for Tracking ID

In `tw.config`:
```
env { public "GA_TRACKING_ID" }
```

In `.env`:
```
GA_TRACKING_ID=G-XXXXXXXXXX
```

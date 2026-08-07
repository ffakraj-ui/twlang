# SaaS Landing Page Template

```tw
page { title "MyApp - Build Better", layout "main", render static }

body {
    section {
        class "hero"
        h1 "Build Better Apps, Faster"
        p "The all-in-one platform for modern web development."
        div {
            class "cta-group"
            a "Start Free" { href "/signup", class "btn btn-primary" }
            a "Watch Demo" { href "#demo", class "btn btn-outline" }
        }
    }

    section {
        class "features"
        h2 "Why Choose MyApp?"
        div {
            class "features-grid"
            div { class "feature", h3 "Fast", p "Lightning fast performance." }
            div { class "feature", h3 "Secure", p "Enterprise-grade security." }
            div { class "feature", h3 "Scalable", p "Scales with your business." }
        }
    }

    section {
        class "pricing"
        h2 "Pricing"
        div {
            class "pricing-grid"
            div { class "plan", h3 "Free", p "$0/mo", a "Start" { href "/signup", class "btn" } }
            div { class "plan popular", h3 "Pro", p "$29/mo", a "Start" { href "/signup", class "btn btn-primary" } }
            div { class "plan", h3 "Enterprise", p "Custom", a "Contact" { href "/contact", class "btn" } }
        }
    }
}
```

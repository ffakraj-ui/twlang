# Structured Data (Schema.org)

## JSON-LD in Head

```tw
head {
    script { type "application/ld+json" }
}
```

## Article Schema

```tw
head {
    script { type "application/ld+json" }
}

body {
    article {
        h1 "Article Title"
        p "Published on January 15, 2024"
    }
}
```

## Breadcrumb Schema

```tw
head {
    script { type "application/ld+json" }
}

body {
    nav {
        class "breadcrumbs"
        a "Home" { href "/" }
        span " > "
        a "Products" { href "/products" }
        span " > "
        span "Widget Pro"
    }
}
```

## FAQ Schema

```tw
head {
    script { type "application/ld+json" }
}

body {
    div {
        class "faq"
        h2 "Frequently Asked Questions"
        div {
            h3 "What is TW Framework?"
            p "A custom language and framework for building websites."
        }
    }
}
```

## Organization Schema

```tw
head {
    script { type "application/ld+json" }
}

body {
    footer { p "Copyright 2024 My Company" }
}
```

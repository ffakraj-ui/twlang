# Data Fetching

## Load JSON Data

```tw
load "@./data/products.json"

body {
    each products as product {
        div {
            class "product-card"
            h3 "{product.name}"
            p "Rs {product.price}"
        }
    }
}
```

## Fetch at Build Time (Static)

```tw
page { render static }

load "@./data/articles.json"

body {
    each articles as article {
        article {
            h2 "{article.title}"
            p "{article.summary}"
            a "Read more" { href "/blog/{article.slug}" }
        }
    }
}
```

## Fetch at Request Time (Server)

```tw
page { render server }

body {
    h1 "Latest Posts"
    each posts as post {
        div { h3 "{post.title}", p "{post.excerpt}" }
    }
}
```

## Revalidation

```tw
page {
    render static
    revalidate 3600
}

load "@./data/news.json"

body {
    each news as item {
        article { h2 "{item.title}", p "{item.content}" }
    }
}
```

## Dynamic Data Based on Route

```tw
page { render server }

body {
    h1 "Post: {params.slug}"
}
```

## JSON File Structure

`[home]/data/products.json`:

```json
[
    { "name": "Widget", "price": 299, "category": "tools" },
    { "name": "Gadget", "price": 599, "category": "electronics" }
]
```

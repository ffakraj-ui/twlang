# E-Commerce Template Guide

Complete e-commerce site using TW Framework.

## Project Structure

```
my-store/
├── [home]/
│   ├── pages/
│   │   ├── index.tw              → Homepage
│   │   ├── products/
│   │   │   ├── index.tw          → /products
│   │   │   └── [slug].tw         → /products/:slug
│   │   ├── cart.tw               → /cart
│   │   └── checkout.tw           → /checkout
│   ├── components/
│   │   ├── ProductCard.tw
│   │   └── CartItem.tw
│   ├── api/
│   │   ├── products/route.twm
│   │   ├── cart/route.twm
│   │   └── checkout/route.twm
│   └── data/
│       └── products.json
```

## Product List Page

```tw
page { title "Products", layout "main", render static }

load "@./data/products.json"

body {
    div {
        class "product-grid"
        each products as product {
            a {
                href "/products/{product.slug}"
                div {
                    class "product-card"
                    img { src "{product.image}", alt "{product.name}", loading "lazy" }
                    h3 "{product.name}"
                    p "${product.price}"
                }
            }
        }
    }
}
```

## Product Detail Page

```tw
page { title "{product.name}", layout "main", render server }

body {
    div {
        class "product-detail"
        img { src "{product.image}", alt "{product.name}" }
        h1 "{product.name}"
        p "Price: ${product.price}"
        p "{product.description}"
        button "Add to Cart" {
            on:click "addToCart()"
            class "btn btn-primary"
        }
    }
}
```

## Cart API

```js
// [home]/api/cart/route.twm
export function GET(request) {
    return { status: 200, json: { items: [], total: 0 } };
}
export function POST(request) {
    const { productId, quantity } = request.body;
    return { status: 200, json: { added: true } };
}
```

## Checkout API

```js
// [home]/api/checkout/route.twm
export function POST(request) {
    const { items, shipping, payment } = request.body;
    const orderId = Date.now();
    return { status: 200, json: { orderId, status: 'confirmed' } };
}
```

## Middleware for Checkout

```tw
rule "protect-checkout" {
    match "/checkout"
    auth { cookie "session", redirect "/login" }
}

rule "api-rate-limit" {
    match "/api/**"
    rate_limit { requests 100, window 60 }
}
```

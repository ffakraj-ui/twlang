# Navigation and Menus

## Simple Navigation

```tw
nav {
    class "main-nav"
    a "Home" { href "/", class "nav-link" }
    a "About" { href "/about", class "nav-link" }
    a "Contact" { href "/contact", class "nav-link" }
}
```

## Navigation Component

`[home]/components/Nav.tw`:

```tw
nav {
    class "navbar"
    div {
        class "nav-brand"
        a "{siteName}" { href "/", class "brand-link" }
    }
    div {
        class "nav-links"
        a "Home" { href "/", class "nav-link" }
        a "About" { href "/about", class "nav-link" }
    }
}
```

## Mobile Hamburger Menu

```tw
let menuOpen = false

nav {
    class "navbar"
    button {
        on:click "menuOpen = !menuOpen"
        class "hamburger"
        text "Menu"
    }
    if menuOpen {
        div {
            class "nav-mobile"
            a "Home" { href "/" }
            a "About" { href "/about" }
        }
    }
}
```

## Breadcrumbs Component

```tw
nav {
    class "breadcrumbs"
    each items as item {
        if item.last {
            span "{item.name}" { class "breadcrumb-current" }
        } else {
            a "{item.name}" { href "{item.url}", class "breadcrumb-link" }
            span " / "
        }
    }
}
```

## Pagination Component

```tw
div {
    class "pagination"
    if currentPage > 1 {
        a "Previous" { href "?page={currentPage - 1}", class "page-link" }
    }
    each pages as page {
        if page == currentPage {
            span "{page}" { class "page-current" }
        } else {
            a "{page}" { href "?page={page}", class "page-link" }
        }
    }
    if currentPage < totalPages {
        a "Next" { href "?page={currentPage + 1}", class "page-link" }
    }
}
```

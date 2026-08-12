# Conditional Rendering

## If/Else

```tw
let isLoggedIn = true

if isLoggedIn {
    h1 "Welcome back!"
} else {
    a "Login" { href "/login" }
}
```

## If Without Else

```tw
if hasNotifications {
    div {
        class "notifications"
        p "You have {notificationCount} new notifications"
    }
}
```

## Nested Conditions

```tw
if isLoggedIn {
    if isAdmin {
        a "Admin Panel" { href "/admin" }
    } else {
        a "Dashboard" { href "/dashboard" }
    }
} else {
    a "Login" { href "/login" }
}
```

## Conditions with Interpolation

```tw
let count = 5

if count > 0 {
    p "You have {count} items"
} else {
    p "No items"
}
```

## Conditions with Comparison

```tw
let role = "admin"

if role == "admin" {
    button "Delete" { on:click "deleteItem()" }
}

if role != "guest" {
    a "Profile" { href "/profile" }
}
```

## Show/Hide with Classes

For CSS-based show/hide:

```tw
let isVisible = true

div {
    class "panel {isVisible ? 'visible' : 'hidden'}"
    p "Content"
}
```

## Conditional Attributes

```tw
let isActive = true

button "Toggle" {
    class "btn {isActive ? 'btn-active' : ''}"
    on:click "isActive = !isActive"
}
```

## Multiple Conditions

TW doesn't have `else if`. Use nested `if`:

```tw
if status == "loading" {
    p "Loading..."
} else {
    if status == "error" {
        p "Error occurred"
    } else {
        if status == "success" {
            p "Success!"
        }
    }
}
```

## Conditional in Loops

```tw
each items as item {
    if item.isVisible {
        div {
            h3 "{item.title}"
            p "{item.description}"
        }
    }
}
```

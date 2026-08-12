# Input Validation

## Server-Side Validation

```js
export function POST(request) {
    const { name, email, password } = request.body

    if (!name || name.trim().length < 2) {
        return { status: 400, json: { error: "Name must be at least 2 characters" } }
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!email || !emailRegex.test(email)) {
        return { status: 400, json: { error: "Invalid email address" } }
    }

    if (!password || password.length < 8) {
        return { status: 400, json: { error: "Password must be at least 8 characters" } }
    }

    return { status: 201, json: { ok: true } }
}
```

## Validation Helper

```js
function validate(data, rules) {
    const errors = {}
    for (const [field, rule] of Object.entries(rules)) {
        const value = data[field]
        if (rule.required && !value) {
            errors[field] = field + " is required"
            continue
        }
        if (value && rule.min && value.length < rule.min) {
            errors[field] = field + " must be at least " + rule.min + " characters"
        }
        if (value && rule.max && value.length > rule.max) {
            errors[field] = field + " must be at most " + rule.max + " characters"
        }
        if (value && rule.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
            errors[field] = "Invalid email format"
        }
    }
    return Object.keys(errors).length > 0 ? errors : null
}
```

## HTML5 Validation

```tw
input { type "email", required true, placeholder "Email" }
input { type "text", required true, minlength 3, maxlength 50, placeholder "Name" }
input { type "password", required true, minlength 8 }
input { type "number", min 18, max 120, placeholder "Age" }
```

## Sanitization

Always sanitize user input:

```js
function sanitize(str) {
    if (typeof str !== 'string') return ''
    return str.replace(/[<>]/g, '').replace(/javascript:/gi, '').trim().slice(0, 1000)
}
```

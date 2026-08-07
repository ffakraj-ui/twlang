# Form Handling and Validation

## Basic Form

```tw
page { title "Contact", render static }

body {
    form {
        on:submit "handleSubmit(event)"
        method "POST"
        action "/api/contact"

        div {
            class "form-group"
            label "Name" { for "name" }
            input { type "text", name "name", id "name", required true, placeholder "Your name" }
        }

        div {
            class "form-group"
            label "Email" { for "email" }
            input { type "email", name "email", id "email", required true }
        }

        div {
            class "form-group"
            label "Message" { for "message" }
            textarea "" { name "message", id "message", rows 5, required true }
        }

        button "Send" { type "submit", class "btn btn-primary" }
    }
}
```

## Client-Side Validation

```tw
script {
    function handleSubmit(event) {
        event.preventDefault();
        const form = event.target;
        const data = new FormData(form);

        const name = data.get('name');
        const email = data.get('email');

        if (!name || name.length < 2) {
            alert('Name must be at least 2 characters');
            return;
        }

        if (!email || !email.includes('@')) {
            alert('Please enter a valid email');
            return;
        }

        fetch('/api/contact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email })
        })
        .then(r => r.json())
        .then(data => alert('Sent!'));
    }
}
```

## Server-Side Validation

```js
// [home]/api/contact/route.twm

export function POST(request) {
    const { name, email, message } = request.body;
    const errors = {};

    if (!name || name.length < 2) errors.name = 'Name too short';
    if (!email || !email.includes('@')) errors.email = 'Invalid email';

    if (Object.keys(errors).length > 0) {
        return { status: 400, json: { errors } };
    }

    return { status: 200, json: { success: true } };
}
```

## File Upload Form

```tw
form {
    method "POST"
    action "/api/upload"
    enctype "multipart/form-data"
    input { type "file", name "file", accept "image/*" }
    button "Upload" { type "submit" }
}
```

## Select Dropdowns

```tw
select "" {
    name "country"
    option "India" { value "IN" }
    option "USA" { value "US" }
}
```

## Checkboxes and Radios

```tw
input { type "checkbox", name "subscribe", checked true }
input { type "radio", name "plan", value "free", checked true }
input { type "radio", name "plan", value "pro" }
```

## CSRF Protection

```tw
form {
    method "POST"
    action "/api/contact"
    input { type "hidden", name "_csrf", value "{csrf_token}" }
}
```

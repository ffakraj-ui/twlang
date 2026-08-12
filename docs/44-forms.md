# Forms and Validation

## Basic Form

```tw
form {
    action "/api/contact"
    method "POST"
    class "contact-form"

    div {
        class "form-group"
        label "Name" { for "name" }
        input { type "text", id "name", name "name", placeholder "Enter name", required true }
    }

    div {
        class "form-group"
        label "Email" { for "email" }
        input { type "email", id "email", name "email", placeholder "you@example.com", required true }
    }

    button "Send" { type "submit", class "btn btn-primary" }
}
```

## Form with Reactive Bindings

```tw
let name = ""
let email = ""

form {
    on:submit "submitForm(event)"
    input { type "text", bind:value "name", placeholder "Name" }
    input { type "email", bind:value "email", placeholder "Email" }
    button "Submit" { type "submit" }
}

div {
    h3 "Preview"
    p "Name: {name}"
    p "Email: {email}"
}
```

## Input Types

text, email, password, number, tel, url, date, time, checkbox, radio, file, hidden, color, range, search

## Select Dropdown

```tw
select {
    id "country"
    name "country"
    option "Select country" { value "" }
    option "India" { value "IN" }
    option "USA" { value "US" }
}
```

## Checkboxes and Radio Buttons

```tw
input { type "checkbox", id "terms", name "terms", required true }
label "I agree to terms" { for "terms" }

input { type "radio", id "male", name "gender", value "male" }
label "Male" { for "male" }
```

## Client-Side Validation

```tw
let emailError = ""

input { type "email", bind:value "email", on:blur "validateEmail()" }

if emailError {
    p "{emailError}" { class "error" }
}

script {
    function validateEmail() {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
        if (!re.test(email)) {
            emailError = "Please enter a valid email"
        } else {
            emailError = ""
        }
    }
}
```

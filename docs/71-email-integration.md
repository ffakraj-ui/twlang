# Email Integration

## Sending Email from API Routes

```js
// [home]/api/contact/route.twm

export async function POST(request) {
    const { name, email, message } = request.body;

    // Using nodemailer (install separately)
    const nodemailer = await import("nodemailer");

    const transporter = nodemailer.createTransport({
        service: "gmail",
        auth: {
            user: process.env.EMAIL_USER,
            pass: process.env.EMAIL_PASS
        }
    });

    await transporter.sendMail({
        from: process.env.EMAIL_USER,
        to: "admin@example.com",
        subject: "New contact from " + name,
        text: "Name: " + name + "\nEmail: " + email + "\nMessage: " + message
    });

    return { status: 200, json: { success: true } };
}
```

## Mailto Links

For simple contact forms without backend:

```tw
form {
    action "mailto:hello@example.com"
    method "POST"
    enctype "text/plain"
    input { type "text", name "name", placeholder "Your name" }
    textarea "" { name "message", placeholder "Your message" }
    button "Send" { type "submit" }
}
```

## Environment Variables

```
# .env
EMAIL_USER=your@gmail.com
EMAIL_PASS=your-app-password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

Don't add these to env { public ... } - they should never reach page HTML.

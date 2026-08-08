# Email Sending

## Via API Route

```js
export async function POST(request) {
    const { to, subject, message } = request.body

    const response = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
            'Authorization': 'Bearer ' + process.env.RESEND_API_KEY,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            from: 'noreply@mysite.com',
            to: to,
            subject: subject,
            html: message
        })
    })

    if (response.ok) {
        return { status: 200, json: { sent: true } }
    }
    return { status: 500, json: { error: 'Failed to send email' } }
}
```

## Contact Form

```tw
let email = ""
let subject = ""
let message = ""
let status = ""

form {
    on:submit "sendEmail(event)"
    input { type "email", bind:value "email", placeholder "Email" }
    input { type "text", bind:value "subject", placeholder "Subject" }
    textarea { bind:value "message", placeholder "Message" }
    button "Send" { type "submit" }
}

if status {
    p "{status}"
}

script {
    async function sendEmail(event) {
        event.preventDefault()
        status = 'Sending...'
        const response = await fetch('/api/email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ to: email, subject, message })
        })
        const result = await response.json()
        status = result.sent ? 'Sent!' : 'Failed'
    }
}
```

## Environment Variables

```
# .env
RESEND_API_KEY=re_xxxxx
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your-app-password
```

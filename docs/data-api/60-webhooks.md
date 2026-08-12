# Webhook Handling

## Basic Webhook Handler

```js
export async function POST(request) {
    const event = request.body
    const signature = request.headers['x-signature']

    if (!verifySignature(event, signature)) {
        return { status: 401, json: { error: "Invalid signature" } }
    }

    switch (event.type) {
        case 'payment.succeeded':
            await handlePaymentSuccess(event.data)
            break
        case 'payment.failed':
            await handlePaymentFailure(event.data)
            break
        default:
            console.log('Unhandled event:', event.type)
    }

    return { status: 200, json: { received: true } }
}
```

## Webhook Verification

```js
import crypto from 'crypto'

function verifySignature(payload, signature, secret) {
    if (!signature || !secret) return false
    const expected = crypto.createHmac('sha256', secret).update(JSON.stringify(payload)).digest('hex')
    return signature === expected
}
```

## GitHub Webhook

```js
export async function POST(request) {
    const event = request.headers['x-github-event']
    const payload = request.body

    switch (event) {
        case 'push':
            console.log('Push to', payload.repository.name)
            break
        case 'pull_request':
            console.log('PR', payload.action, payload.number)
            break
    }

    return { status: 200, json: { ok: true } }
}
```

## Response Requirements

Webhooks expect a quick 200 OK. Process heavy work asynchronously:

```js
export async function POST(request) {
    const event = request.body
    setTimeout(() => processEvent(event), 0)
    return { status: 200, json: { received: true } }
}
```

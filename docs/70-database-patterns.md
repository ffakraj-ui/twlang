# Database Integration

## Connecting to a Database

```js
let db = null

function getDb() {
    if (!db) {
        const { MongoClient } = require('mongodb')
        const client = new MongoClient(process.env.DATABASE_URL)
        db = client.db('myapp')
    }
    return db
}

export async function GET(request) {
    const database = getDb()
    const users = await database.collection('users').find({}).toArray()
    return { status: 200, json: { users } }
}
```

## External Packages

Configure in `tw.config`:

```
server {
  external_packages [
    "mongodb",
    "pg",
    "mysql2",
    "redis"
  ]
}
```

## Bundler Fallbacks

```
bundler {
  fallback {
    fs false
    net false
    tls false
    http false
    https false
    crypto false
  }
}
```

## CRUD Pattern

### Create
```js
export async function POST(request) {
    const result = await db.collection('users').insertOne(request.body)
    return { status: 201, json: { id: result.insertedId } }
}
```

### Read
```js
export async function GET(request) {
    const users = await db.collection('users').find({}).toArray()
    return { status: 200, json: { users } }
}
```

### Update
```js
export async function PUT(request) {
    await db.collection('users').updateOne({ _id: request.params.id }, { $set: request.body })
    return { status: 200, json: { ok: true } }
}
```

### Delete
```js
export async function DELETE(request) {
    await db.collection('users').deleteOne({ _id: request.params.id })
    return { status: 200, json: { ok: true } }
}
```

Never add DATABASE_URL to `env { public "..." }`.

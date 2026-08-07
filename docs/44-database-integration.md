# Database Integration

TW Framework doesn't include a built-in ORM, but `.twm` modules can connect to any database.

## SQLite

```js
// [home]/api/users/route.twm
import Database from 'better-sqlite3';
const db = new Database('data/app.db');

export function GET(request) {
    const users = db.prepare('SELECT * FROM users').all();
    return { status: 200, json: { users } };
}

export function POST(request) {
    const { name, email } = request.body;
    const result = db.prepare(
        'INSERT INTO users (name, email) VALUES (?, ?)'
    ).run(name, email);
    return { status: 201, json: { id: result.lastInsertRowid } };
}
```

## PostgreSQL

```js
import { Pool } from 'pg';
const pool = new Pool({
    connectionString: process.env.DATABASE_URL
});

export async function GET(request) {
    const page = parseInt(request.query.page) || 1;
    const limit = 20;
    const offset = (page - 1) * limit;
    const result = await pool.query(
        'SELECT * FROM products ORDER BY id LIMIT $1 OFFSET $2',
        [limit, offset]
    );
    return { status: 200, json: { products: result.rows, page } };
}
```

## MongoDB

```js
import { MongoClient } from 'mongodb';
const client = new MongoClient(process.env.MONGODB_URI);
const db = client.db('myapp');

export async function GET(request) {
    const articles = await db.collection('articles').find({}).limit(20).toArray();
    return { status: 200, json: { articles } };
}
```

## Connection Pooling

Create a shared database module:

```js
// [home]/lib/db.twm
import Database from 'better-sqlite3';
const db = new Database('data/app.db');

export function query(sql, params = []) {
    return db.prepare(sql).all(...params);
}

export function execute(sql, params = []) {
    return db.prepare(sql).run(...params);
}
```

## Database in tw.config

```
server {
  external_packages ["better-sqlite3", "pg", "mongodb"]
}

bundler {
  client_externals ["better-sqlite3", "pg", "mongodb"]
  fallback { fs false, net false }
}
```

## Environment Variables

```
# .env
DATABASE_URL=postgres://user:pass@localhost:5432/myapp
MONGODB_URI=mongodb://localhost:27017/myapp
```

Don't add these to `env { public ... }` - they should never reach page HTML.

## Migration Example

```js
export function POST(request) {
    const db = new Database('data/app.db');
    db.exec(`
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    `);
    return { status: 200, json: { migrated: true } };
}
```

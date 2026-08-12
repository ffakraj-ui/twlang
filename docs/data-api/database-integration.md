# Database Integration

Connect TW Framework to databases for dynamic content and APIs.

## Supported Databases

TW Framework works with any Python-compatible database:

| Database | Library | Best For |
|----------|---------|----------|
| SQLite | built-in `sqlite3` | Small sites, prototyping |
| PostgreSQL | `psycopg2` or `asyncpg` | Production, complex queries |
| MySQL | `PyMySQL` | Legacy systems |
| MongoDB | `pymongo` | Document stores |
| Redis | `redis-py` | Caching, sessions |

## SQLite Setup

SQLite requires no external server — perfect for small projects.

### Connection

```python
# [home]/db/connection.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/site.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

### Schema

```python
# [home]/db/schema.py
from db.connection import get_db

def init_schema():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            author TEXT,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft'
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug);
        CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
    ''')
    conn.commit()
    conn.close()
```

### API Route

```twm
# [home]/api/posts/route.twm
from db.connection import get_db

function get(request):
    conn = get_db()
    cursor = conn.execute(
        "SELECT id, slug, title, author, published_at FROM posts WHERE status = ? ORDER BY published_at DESC",
        ("published",)
    )
    posts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return json_response(posts)

function post(request):
    data = request.json()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO posts (slug, title, content, author, status) VALUES (?, ?, ?, ?, ?)",
        (data["slug"], data["title"], data.get("content", ""), data.get("author", ""), "draft")
    )
    conn.commit()
    post_id = cursor.lastrowid
    conn.close()
    return json_response({"id": post_id}, status=201)
```

## PostgreSQL Setup

### Connection Pool

```python
# [home]/db/pool.py
import psycopg2.pool
import os

pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "tw_app"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "")
)

def get_connection():
    return pool.getconn()

def release_connection(conn):
    pool.putconn(conn)
```

### Context Manager

```python
# [home]/db/queries.py
from contextlib import contextmanager
from db.pool import get_connection, release_connection

@contextmanager
def db_transaction():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)

def get_post_by_slug(slug):
    with db_transaction() as conn:
        cursor = conn.execute(
            "SELECT * FROM posts WHERE slug = %s",
            (slug,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
```

## MongoDB Setup

```python
# [home]/db/mongo.py
from pymongo import MongoClient
import os

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
db = client[os.environ.get("MONGO_DB", "tw_app")]

def get_collection(name):
    return db[name]
```

```twm
# [home]/api/products/route.twm
from db.mongo import get_collection

function get(request):
    products = get_collection("products")
    results = list(products.find({}, {"_id": 0}).limit(50))
    return json_response(results)

function post(request):
    data = request.json()
    products = get_collection("products")
    result = products.insert_one(data)
    return json_response({"id": str(result.inserted_id)}, status=201)
```

## Redis for Caching

```python
# [home]/db/cache.py
import redis
import json
import os

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True
)

def cache_get(key):
    value = r.get(key)
    return json.loads(value) if value else None

def cache_set(key, value, ttl=300):
    r.setex(key, ttl, json.dumps(value))

def cache_delete(key):
    r.delete(key)
```

```twm
function get_popular_posts(request):
    cached = cache_get("posts:popular")
    if cached:
        return json_response(cached)

    conn = get_db()
    cursor = conn.execute(
        "SELECT * FROM posts ORDER BY views DESC LIMIT 10"
    )
    posts = [dict(row) for row in cursor.fetchall()]
    conn.close()

    cache_set("posts:popular", posts, ttl=600)
    return json_response(posts)
```

## Database Migrations

Create a simple migration system:

```python
# [home]/db/migrate.py
import os
import sqlite3

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

def get_applied_migrations(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor = conn.execute("SELECT filename FROM _migrations")
    return {row[0] for row in cursor.fetchall()}

def run_migrations():
    conn = sqlite3.connect(DB_PATH)
    applied = get_applied_migrations(conn)

    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql'))

    for filename in files:
        if filename in applied:
            continue

        with open(os.path.join(MIGRATIONS_DIR, filename)) as f:
            conn.executescript(f.read())

        conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (filename,))
        conn.commit()
        print(f"Applied: {filename}")

    conn.close()
```

## Best Practices

1. **Always close connections**: Use context managers.
2. **Use connection pools**: For PostgreSQL/MySQL in production.
3. **Parameterize queries**: Never use f-strings for SQL.
4. **Index frequently queried columns**.
5. **Cache expensive queries** with Redis.
6. **Run migrations before deployment**.

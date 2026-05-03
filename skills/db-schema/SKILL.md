---
name: db-schema
description: Design, review, and improve PostgreSQL database schemas including tables, columns, data types, indexes, constraints, foreign keys, relationships, migrations, and query optimisation. Use this skill whenever the user wants to model data, design a database, write a migration, optimise queries with indexes, normalise a schema, add pgvector support, or asks "how should I structure this in the database?" Trigger on mentions of tables, schemas, migrations, ERDs, relationships, PostgreSQL, pgvector, or database design questions.
---

# Database Schema Design

Design clear, correct, and performant PostgreSQL schemas. Model the domain accurately, enforce integrity at the database level, and support the application's query patterns.

---

## Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Tables | `snake_case`, plural | `user_profiles`, `order_items` |
| Columns | `snake_case` | `created_at`, `user_id` |
| Primary key | `id` | `id BIGSERIAL PRIMARY KEY` |
| Foreign keys | `<table_singular>_id` | `user_id`, `order_id` |
| Indexes | `idx_<table>_<columns>` | `idx_posts_user_id` |
| Unique constraints | `uq_<table>_<columns>` | `uq_users_email` |
| Check constraints | `ck_<table>_<rule>` | `ck_orders_positive_total` |

---

## Data types — choose the most specific type

| Data | Type | Notes |
|---|---|---|
| Auto-increment ID (small table) | `SERIAL` | 4-byte int, max ~2 billion |
| Auto-increment ID (large table) | `BIGSERIAL` | 8-byte int, virtually unlimited |
| Distributed/external ID | `UUID` | `DEFAULT gen_random_uuid()` |
| Short text | `VARCHAR(n)` | Use when you need a max length enforced |
| Unlimited text | `TEXT` | No performance difference from VARCHAR in PG |
| Whole number | `INTEGER` | 4 bytes |
| Large integer | `BIGINT` | 8 bytes |
| Money / precise decimal | `NUMERIC(10, 2)` | Never use `FLOAT` for money |
| Timestamp with tz | `TIMESTAMPTZ` | **Always** use this over `TIMESTAMP` |
| Date only | `DATE` | |
| True/false | `BOOLEAN` | |
| Flexible data | `JSONB` | Binary, indexable — prefer over `JSON` |
| Vector embeddings | `vector(1536)` | Via pgvector extension |
| Enum | `TEXT` + `CHECK` | Easier to extend than PG ENUM |
| IP address | `INET` | Built-in PG type |

---

## Primary keys

```sql
-- BIGSERIAL for most tables
id BIGSERIAL PRIMARY KEY

-- UUID for distributed systems or external-facing IDs
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

**When to use UUID:**
- IDs are exposed to clients (harder to enumerate)
- Rows created across multiple services without a central sequence
- Importing from external systems

**UUID downside:** Larger (16 bytes vs 8), random UUIDs fragment indexes — use `gen_random_uuid()` or UUIDv7 for better insert performance.

---

## Full table examples

### Users table
```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'member'
                    CHECK (role IN ('member', 'admin', 'moderator')),
    password_hash TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ DEFAULT NULL,         -- soft delete
    CONSTRAINT uq_users_email UNIQUE (email)
);

-- Index for common lookups
CREATE INDEX idx_users_email       ON users(email);
CREATE INDEX idx_users_active      ON users(id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created     ON users(created_at DESC);
```

### Posts with foreign key
```sql
CREATE TABLE posts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'published', 'archived')),
    published_at TIMESTAMPTZ DEFAULT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Always index foreign keys (PG does NOT do this automatically)
CREATE INDEX idx_posts_user_id    ON posts(user_id);
CREATE INDEX idx_posts_status     ON posts(status);
-- Partial index for the most common query (active published posts)
CREATE INDEX idx_posts_published  ON posts(published_at DESC)
    WHERE status = 'published';
```

### Many-to-many junction table
```sql
CREATE TABLE post_tags (
    post_id  BIGINT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tag_id   BIGINT NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, tag_id)
);

-- Also index the reverse direction for "posts with this tag" queries
CREATE INDEX idx_post_tags_tag_id ON post_tags(tag_id);
```

### Agent memory table (your project)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE llm_memory (
    id           BIGSERIAL PRIMARY KEY,
    user_id      TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content      TEXT NOT NULL,
    embedding    vector(768),           -- nomic-embed-text outputs 768 dims
    tool_call_id TEXT DEFAULT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_memory_user_id    ON llm_memory(user_id);
CREATE INDEX idx_llm_memory_created    ON llm_memory(user_id, created_at DESC);
-- IVFFlat index for approximate nearest-neighbour vector search
CREATE INDEX idx_llm_memory_embedding  ON llm_memory
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);                -- lists ≈ sqrt(row_count)
```

---

## Indexes — when and why

```sql
-- Single column (equality, FK, sorting)
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- Composite (covers multi-column WHERE, order matters: most selective first)
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
-- This covers: WHERE user_id = ? AND status = ?
-- Also covers: WHERE user_id = ?
-- Does NOT cover: WHERE status = ? alone

-- Partial (filter rows that are always in the WHERE clause)
CREATE INDEX idx_sessions_active ON sessions(user_id, expires_at)
    WHERE revoked = false;

-- Expression (index on a computed value)
CREATE INDEX idx_users_email_lower ON users(LOWER(email));
-- Needed for: WHERE LOWER(email) = LOWER($1)

-- Full-text search
CREATE INDEX idx_posts_fts ON posts
    USING GIN(to_tsvector('english', title || ' ' || body));
-- Query: WHERE to_tsvector('english', title || ' ' || body) @@ plainto_tsquery('english', $1)

-- JSONB fields
CREATE INDEX idx_profiles_data ON user_profiles USING GIN(data);
-- Query: WHERE data @> '{"role": "admin"}'

-- Vector similarity (pgvector)
CREATE INDEX idx_memory_vec ON llm_memory
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
-- Query: ORDER BY embedding <=> $1 LIMIT 5
```

**Always index:**
- Every foreign key column
- Columns in `WHERE`, `ORDER BY`, `JOIN ON`
- Columns in `UNIQUE` constraints

**Do NOT index:**
- Columns with very few distinct values (boolean, status with 2 values) — a full scan is faster
- Tables with < 1000 rows — overhead not worth it
- Write-heavy tables where reads are rare

---

## Relationships and ON DELETE

```sql
-- ON DELETE CASCADE: delete children when parent deleted
-- Use for: posts → comments, users → sessions
user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE

-- ON DELETE RESTRICT: block parent deletion if children exist
-- Use for: orders → products (can't delete a product in an order)
product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE RESTRICT

-- ON DELETE SET NULL: orphan the child record
-- Use for: optional relationships, audit trails
author_id BIGINT REFERENCES users(id) ON DELETE SET NULL
```

---

## Migrations

```sql
-- up migration
ALTER TABLE users ADD COLUMN avatar_url TEXT;
CREATE INDEX idx_users_avatar ON users(avatar_url)
    WHERE avatar_url IS NOT NULL;

-- down migration (always write the reverse)
DROP INDEX idx_users_avatar;
ALTER TABLE users DROP COLUMN avatar_url;
```

**Rules:**
- Never modify an applied migration — add a new one
- Make migrations reversible (up + down)
- For large tables: use `NOT VALID` constraint to add without full table scan, then validate separately
- Add columns with defaults as `NOT NULL DEFAULT x`, not via two steps (avoids full rewrite on Postgres 11+)

```sql
-- Safe: adding NOT NULL column with default on large table
ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT false;
-- Postgres 11+: no table rewrite, uses default value metadata
```

---

## Common issues and fixes

### Missing index on foreign key
```sql
-- Symptom: slow JOINs or slow ON DELETE CASCADE
-- Diagnosis:
EXPLAIN ANALYZE SELECT * FROM posts WHERE user_id = 42;
-- If you see "Seq Scan" on a large table, add an index

CREATE INDEX idx_posts_user_id ON posts(user_id);
```

### N+1 query problem
```python
# BAD — runs 1 query for users, then 1 per user for posts
users = db.query("SELECT * FROM users")
for user in users:
    posts = db.query("SELECT * FROM posts WHERE user_id = %s", user.id)

# GOOD — single JOIN query
rows = db.query("""
    SELECT u.id, u.name, p.id AS post_id, p.title
    FROM users u
    LEFT JOIN posts p ON p.user_id = u.id
    WHERE u.id = ANY(%s)
""", [user_ids])
```

### Using FLOAT for money
```sql
-- BAD: floating point imprecision
price FLOAT

-- GOOD: exact decimal
price NUMERIC(10, 2)   -- up to 99,999,999.99
```

### Not using TIMESTAMPTZ
```sql
-- BAD: stores without timezone, ambiguous
created_at TIMESTAMP

-- GOOD: stores as UTC, displays in any timezone
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

### Large JSON blob instead of columns
```sql
-- BAD: hard to query, index, or constrain
data JSONB   -- stores everything in one blob

-- GOOD: real columns for fields you filter/sort on
name TEXT NOT NULL,
email TEXT NOT NULL,
preferences JSONB   -- JSONB only for truly dynamic/optional data
```

### Checking query performance
```sql
-- EXPLAIN ANALYZE shows actual execution plan with timing
EXPLAIN ANALYZE
SELECT * FROM llm_memory
WHERE user_id = 'user_1'
ORDER BY created_at DESC
LIMIT 10;

-- Look for:
-- "Seq Scan" on large tables = missing index
-- "Rows Removed by Filter" = index not selective enough
-- High "actual time" vs "estimated time" = stale statistics (run ANALYZE)
```

---

## Output format

When designing a schema, deliver:

1. **Entity summary** — plain English: what the entities are and how they relate
2. **CREATE TABLE statements** — complete, runnable SQL with all constraints and defaults
3. **Index statements** — each with a comment explaining why it exists
4. **Design decisions** — notes on non-obvious choices (UUID vs BIGSERIAL, soft delete, JSONB fields)
5. **Common queries** — 2–3 example queries the schema is designed to serve efficiently
6. **Migration** — up/down pair if modifying an existing schema

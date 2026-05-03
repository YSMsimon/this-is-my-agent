---
name: api-designer
description: Design REST APIs including endpoints, URL structures, HTTP methods, request/response bodies, status codes, authentication, versioning, pagination, and error formats. Use this skill whenever the user wants to design an API, plan endpoints, structure a backend, decide on REST conventions, write an API spec, design request/response shapes, or asks "how should I structure this API?" Trigger on phrases like "design an API", "what endpoints do I need", "REST API for", "API structure", "request/response format", "status codes", or "API versioning".
---

# API Designer

Design REST APIs that are consistent, predictable, and easy to consume. Good API design is a contract — once clients depend on it, changing it is expensive. Get the structure right upfront.

---

## URL structure

URLs identify **resources** (nouns). The HTTP method expresses the action.

```
# Correct — nouns, hierarchical
GET    /users                    list all users
GET    /users/{id}               get one user
POST   /users                    create a user
PATCH  /users/{id}               update a user partially
PUT    /users/{id}               replace a user entirely
DELETE /users/{id}               delete a user

GET    /users/{id}/posts         list posts by this user
POST   /users/{id}/posts         create a post for this user
GET    /users/{id}/posts/{pid}   get one post by this user

# Wrong — verbs in URL
POST   /createUser
GET    /getUser?id=123
POST   /deleteUser
POST   /users/update
```

**Rules:**
- Plural nouns for collections: `/users`, not `/user`
- Lowercase, hyphen-separated: `/user-profiles`, not `/userProfiles`
- Nested max 2 levels deep: `/users/{id}/posts` ✓, `/users/{id}/posts/{pid}/comments/{cid}` ✗
- For deeply nested resources, flatten with query params: `GET /comments?post_id=42`

---

## HTTP methods

| Method | Use | Body | Idempotent |
|---|---|---|---|
| `GET` | Fetch resource(s) | No | Yes |
| `POST` | Create new resource | Yes | No |
| `PUT` | Replace resource entirely | Yes | Yes |
| `PATCH` | Update fields partially | Yes | No |
| `DELETE` | Delete resource | No | Yes |

Use `PATCH` over `PUT` for most updates. `PUT` requires sending the full object — two clients updating different fields simultaneously will overwrite each other.

---

## Status codes

### Success
| Code | When to use |
|---|---|
| `200 OK` | GET, PATCH, PUT succeeded |
| `201 Created` | POST succeeded; include `Location: /users/abc` header |
| `204 No Content` | DELETE succeeded (no body) |

### Client errors (their fault)
| Code | When to use |
|---|---|
| `400 Bad Request` | Malformed JSON, missing required field |
| `401 Unauthorized` | Not authenticated — missing or invalid token |
| `403 Forbidden` | Authenticated but not allowed (wrong user, wrong role) |
| `404 Not Found` | Resource ID doesn't exist |
| `409 Conflict` | Duplicate (email already taken), optimistic lock failure |
| `422 Unprocessable Entity` | Valid JSON but business rule violation |
| `429 Too Many Requests` | Rate limited; add `Retry-After` header |

### Server errors (your fault)
| Code | When to use |
|---|---|
| `500 Internal Server Error` | Unhandled exception |
| `503 Service Unavailable` | DB down, maintenance; add `Retry-After` header |

**Common mistakes:**
- Using `400` for everything — use `401`, `403`, `404`, `409` where appropriate
- Using `200` for failed operations ("status: error" in body with 200) — use the right status code
- Using `500` for client input errors

---

## Request & response examples

### Create resource (POST /users)

**Request:**
```http
POST /v1/users
Content-Type: application/json
Authorization: Bearer <token>

{
  "email": "alice@example.com",
  "name": "Alice Chen",
  "role": "member"
}
```

**Response:**
```http
HTTP/1.1 201 Created
Location: /v1/users/usr_abc123
Content-Type: application/json

{
  "id": "usr_abc123",
  "email": "alice@example.com",
  "name": "Alice Chen",
  "role": "member",
  "created_at": "2025-05-02T10:00:00Z",
  "updated_at": "2025-05-02T10:00:00Z"
}
```

Always return the created resource — the client shouldn't need a second GET call.

### List resources (GET /users)

```http
HTTP/1.1 200 OK

{
  "data": [
    {"id": "usr_abc123", "email": "alice@example.com", "name": "Alice"},
    {"id": "usr_def456", "email": "bob@example.com",   "name": "Bob"}
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 84,
    "next": "/v1/users?page=2&per_page=20",
    "prev": null
  }
}
```

Always wrap in `{ "data": [...] }` — lets you add pagination/metadata without breaking existing clients.

### Partial update (PATCH /users/{id})

```http
PATCH /v1/users/usr_abc123
Content-Type: application/json

{
  "name": "Alice Smith"
}
```

Only include fields being changed. Return the full updated resource with `200`.

### Delete (DELETE /users/{id})

```http
DELETE /v1/users/usr_abc123
Authorization: Bearer <token>
```

```http
HTTP/1.1 204 No Content
```

No body. If the resource was already deleted, still return `204` (idempotent).

---

## Error response format

Define one consistent error shape for the entire API. Clients write error handling once.

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "must be a valid email address",
        "value": "not-an-email"
      },
      {
        "field": "name",
        "message": "must be at least 2 characters"
      }
    ]
  }
}
```

```http
HTTP/1.1 409 Conflict

{
  "error": {
    "code": "EMAIL_ALREADY_EXISTS",
    "message": "An account with this email already exists"
  }
}
```

```http
HTTP/1.1 401 Unauthorized

{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "The provided token is expired or invalid"
  }
}
```

`code` is machine-readable (client can switch on it). `message` is human-readable. `details` is optional for field-level errors.

---

## Filtering, sorting, pagination

```bash
# Filtering
GET /v1/posts?status=published
GET /v1/posts?user_id=42&status=published

# Sorting
GET /v1/posts?sort=created_at&order=desc
GET /v1/posts?sort=title&order=asc

# Offset pagination (simple, but skips rows on inserts)
GET /v1/posts?page=2&per_page=20

# Cursor pagination (better for feeds — no skipping/repeating)
GET /v1/posts?after=post_cursor_abc&limit=20
# Response includes: "next_cursor": "post_cursor_xyz"
```

Use cursor pagination for any feed where new items are inserted while users paginate.

---

## Versioning

Version from day one. Changing a public API without versioning breaks clients.

```bash
# URL path versioning (recommended — simple, cacheable, visible)
/v1/users
/v2/users

# Header versioning (cleaner URLs but harder to test in browser)
Accept: application/vnd.myapi.v2+json
```

**Deprecation process:**
1. Add `Deprecation: true` and `Sunset: 2026-01-01` response headers to v1 routes
2. Communicate deadline in docs and via email
3. Monitor v1 traffic — only remove when it's near zero

---

## Authentication

```bash
# Bearer token (JWT) — for user-facing APIs
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API key — for server-to-server
X-API-Key: sk_live_abc123...
```

- Return `401` for missing/expired/invalid token
- Return `403` for valid token but insufficient permissions
- Never return which specific check failed ("invalid token" is fine; "token expired" leaks info to attackers)

### JWT example (FastAPI)
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
import jwt

security = HTTPBearer()

def get_current_user(token = Depends(security)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/users/me")
def get_me(user_id: str = Depends(get_current_user)):
    return db.get_user(user_id)
```

---

## FastAPI implementation examples

### Full CRUD router
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/v1/users", tags=["users"])

class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    role: str = "member"

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    created_at: datetime

@router.post("", response_model=UserResponse, status_code=201)
def create_user(body: CreateUserRequest, db = Depends(get_db)):
    if db.user_exists(body.email):
        raise HTTPException(status_code=409, detail={
            "error": {"code": "EMAIL_ALREADY_EXISTS", "message": "Email already in use"}
        })
    user = db.create_user(body.email, body.name, body.role)
    return user

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db = Depends(get_db)):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "USER_NOT_FOUND", "message": f"User {user_id} not found"}
        })
    return user

@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: str, body: UpdateUserRequest, db = Depends(get_db),
                current_user = Depends(get_current_user)):
    if current_user != user_id and not is_admin(current_user):
        raise HTTPException(status_code=403, detail={
            "error": {"code": "FORBIDDEN", "message": "Cannot update another user's profile"}
        })
    updates = body.dict(exclude_none=True)   # only set fields
    user = db.update_user(user_id, updates)
    return user

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, db = Depends(get_db)):
    db.delete_user(user_id)   # idempotent — no error if already gone
```

---

## Common mistakes

### Putting verbs in URLs
```bash
# Wrong
POST /api/sendEmail
POST /api/users/123/activate
GET  /api/getActiveUsers

# Right
POST /v1/emails                     # "send" is POST semantics
POST /v1/users/123/activations      # activation as a resource
GET  /v1/users?status=active
```

### Returning 200 for errors
```python
# Wrong — client can't distinguish success from failure by status code
return {"status": "error", "message": "user not found"}, 200

# Right
raise HTTPException(status_code=404, detail={"error": {...}})
```

### No pagination on list endpoints
```python
# Wrong — returns all rows, kills the server at scale
@app.get("/posts")
def list_posts(db = Depends(get_db)):
    return db.get_all_posts()

# Right
@app.get("/posts")
def list_posts(page: int = 1, per_page: int = 20, db = Depends(get_db)):
    per_page = min(per_page, 100)   # cap max page size
    return db.get_posts(offset=(page-1)*per_page, limit=per_page)
```

### Exposing internal IDs
```python
# Wrong — leaks row count, enables enumeration
{"id": 1042}

# Better — use UUIDs or prefixed IDs
{"id": "usr_k3j2nf8w"}
```

---

## Output format

When designing an API, deliver:

1. **Resource model** — the entities and their relationships (plain English)
2. **Endpoint table** — method, path, description, auth required
3. **Request/response examples** — for create, list, get-by-id, update, delete
4. **Error format** — the standard error shape for the whole API
5. **Design decisions** — notes on non-obvious choices

### Endpoint table
| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/v1/users` | List users (paginated) | Admin |
| `POST` | `/v1/users` | Create user | Admin |
| `GET` | `/v1/users/{id}` | Get user by ID | Self or Admin |
| `PATCH` | `/v1/users/{id}` | Update user fields | Self or Admin |
| `DELETE` | `/v1/users/{id}` | Delete user | Admin |
| `GET` | `/v1/users/{id}/posts` | List posts by user | Public |

---
name: dockerfile
description: Write, explain, debug, and optimise Dockerfiles and docker-compose.yml files for any language or stack. Use this skill whenever the user wants to containerise an application, write a Dockerfile, set up docker-compose, configure environment variables in containers, set up multi-stage builds, reduce image size, fix Docker build errors, or debug container networking issues. Trigger on words like "Dockerfile", "docker-compose", "containerise", "container", "docker build", "image size", "port", or "volume".
---

# Dockerfile & Docker Compose

Write correct, minimal, and production-ready container configurations. Goals: small images, fast builds via layer caching, no unnecessary privileges, and predictable behaviour between dev and prod.

---

## Layer caching — the most important concept

Docker rebuilds every layer below the first changed layer. Order instructions from **least to most frequently changed**:

```dockerfile
# 1. Base image — almost never changes
FROM python:3.12-slim

# 2. System deps — changes rarely
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Dependency manifest — changes when you add/remove packages
WORKDIR /app
COPY requirements.txt .

# 4. Install deps — expensive, should be cached most of the time
RUN pip install --no-cache-dir -r requirements.txt

# 5. Source code — changes most often, always last
COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Common mistake:** `COPY . .` before installing deps. Every source file change triggers a full pip install.

---

## Language templates

### Python (FastAPI / Flask)
```dockerfile
FROM python:3.12-slim

# Create non-root user
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Install deps first (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source with correct ownership
COPY --chown=app:app . .

USER app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Node.js / TypeScript
```dockerfile
FROM node:20-alpine

RUN addgroup -S app && adduser -S app -G app

WORKDIR /app

# Install deps (use ci for reproducible installs)
COPY package*.json .
RUN npm ci --only=production

COPY --chown=app:app . .

USER app

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

### Go — multi-stage (produces ~10MB final image)
```dockerfile
# Build stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o server .

# Final stage — distroless or scratch
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/server /server
EXPOSE 8080
CMD ["/server"]
```

### React (build + nginx serve)
```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

`nginx.conf` for React Router:
```nginx
server {
    listen 80;
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;  # handles client-side routing
    }
}
```

---

## .dockerignore

Always create this — without it, Docker sends your entire working directory as build context, including `node_modules`, `.git`, and `.env`:

```
.git
.env
.env.*
__pycache__
*.pyc
*.pyo
*.pyd
.Python
node_modules
.DS_Store
*.log
dist
build
.venv
venv
.pytest_cache
*.egg-info
```

**Common mistake:** Forgetting `.dockerignore`. Build context balloons to gigabytes, copying secrets into the image.

---

## Security

### Never run as root
```dockerfile
# Python
RUN addgroup --system app && adduser --system --ingroup app app
USER app

# Alpine
RUN addgroup -S app && adduser -S app -G app
USER app
```

### Never bake secrets into the image
```dockerfile
# BAD — secret is in the image layer history forever
RUN export DATABASE_URL=postgres://... && ./migrate.sh

# BAD — ARG values are visible in docker history
ARG DATABASE_URL
RUN ./migrate.sh

# GOOD — pass secrets at runtime
ENV DATABASE_URL=""    # document the var, leave empty
# docker run -e DATABASE_URL=... myimage
# or use --env-file .env
```

### Pin base image versions
```dockerfile
# BAD — "latest" changes unpredictably
FROM python:latest

# GOOD — exact version, reproducible builds
FROM python:3.12.3-slim-bookworm
```

### Minimise image surface
```dockerfile
# Remove apt cache in the same RUN layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# --no-install-recommends prevents pulling in hundreds of suggested packages
```

---

## docker-compose.yml

### Web app + PostgreSQL (production-like)
```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://myuser:mypassword@db:5432/mydb
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs   # persist logs

  db:
    image: ankane/pgvector:latest
    environment:
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: mypassword
      POSTGRES_DB: mydb
    ports:
      - "5433:5432"        # expose on 5433 to avoid conflicts with local postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myuser -d mydb"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
```

### Dev override (hot reload, mount source)
```yaml
# docker-compose.dev.yml — run with: docker compose -f docker-compose.yml -f docker-compose.dev.yml up
services:
  app:
    volumes:
      - .:/app               # mount source for hot reload
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DEBUG: "true"
```

### Networking — how containers talk to each other
```yaml
# Services in the same compose file can reach each other by service name
# app → db is just: postgresql://db:5432/mydb (NOT localhost)
# localhost inside a container = that container only
```

**Common mistake:** Using `localhost` in `DATABASE_URL` inside docker-compose. Use the service name (`db`, `redis`, etc.) instead.

---

## Common issues and fixes

### "Port already in use"
```bash
# Find what's using the port
lsof -i :5432
# Kill it, or change the host port in docker-compose:
ports:
  - "5434:5432"   # use 5434 on host instead
```

### "Connection refused" to database
```bash
# 1. Is the container running?
docker compose ps

# 2. Is the healthcheck passing?
docker compose logs db

# 3. Are you using the right host?
# Inside docker-compose: use service name "db"
# From your host machine: use "localhost" with the mapped port
DATABASE_URL=postgresql://myuser:mypassword@db:5432/mydb      # inside compose
DATABASE_URL=postgresql://myuser:mypassword@localhost:5433/mydb  # from host
```

### "Module not found" after adding a dependency
```bash
# Image was not rebuilt after requirements.txt changed
docker compose up -d --build    # force rebuild
docker compose build --no-cache # nuclear option — full rebuild
```

### Image is too large
```bash
# Check layer sizes
docker history myimage

# Common culprits:
# 1. apt cache not cleaned: add && rm -rf /var/lib/apt/lists/*
# 2. Dev dependencies included: use --only=production (npm) or separate requirements-dev.txt
# 3. Source control included: check .dockerignore
# 4. Build tools not removed after compile step: use multi-stage build
```

### "Permission denied" on files
```dockerfile
# File was copied as root but process runs as app user
COPY --chown=app:app . .   # set ownership at copy time

# Or fix after copying
RUN chown -R app:app /app
USER app
```

### Container exits immediately
```bash
# Check the logs
docker compose logs app

# Common causes:
# 1. CMD is wrong — process isn't running in foreground
# 2. Missing env var — app crashes on startup
# 3. Database not ready — add depends_on with healthcheck
```

### Changes to .env not picked up
```bash
# docker-compose caches env at container start
docker compose down && docker compose up -d
# OR just restart the affected service
docker compose restart app
```

---

## Useful commands

```bash
# Build & run
docker compose up -d                  # start detached
docker compose up -d --build          # rebuild then start
docker compose down                   # stop and remove containers
docker compose down -v                # also remove volumes (⚠ deletes DB data)
docker compose restart app            # restart single service

# Logs
docker compose logs -f                # stream all logs
docker compose logs -f app            # stream one service
docker compose logs --tail=50 app     # last 50 lines

# Debugging
docker compose ps                     # status of all services
docker exec -it <container> /bin/sh   # shell into running container
docker exec -it <container> /bin/bash # if bash is available
docker inspect <container>            # full container metadata

# Images
docker build -t myapp .               # build with tag
docker build --no-cache -t myapp .    # full rebuild
docker image ls                       # list images
docker image rm myapp                 # remove image
docker system prune -af               # remove all unused (⚠ nuclear)

# Postgres inside container
docker exec -it postgres_vector_db psql -U myuser -d agent_memory
```

---

## Image size checklist

- [ ] `slim` or `alpine` base image
- [ ] Multi-stage build if there's a compile step
- [ ] `--no-cache-dir` (pip), `--only=production` (npm)
- [ ] `rm -rf /var/lib/apt/lists/*` after apt-get
- [ ] `.dockerignore` excludes `node_modules`, `.git`, `.env`, build output
- [ ] No dev tools in final image
- [ ] Non-root user set with `USER`
- [ ] Secrets passed at runtime, not baked in

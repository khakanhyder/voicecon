# 🐳 Voicecon Docker Development Guide

Complete guide for running Voicecon using Docker and Docker Compose.

## Quick Start

```bash
# Clone and navigate
cd voicecon

# Start all services
cd infrastructure/docker
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

Visit:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📋 Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 4GB RAM available
- 10GB free disk space

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│             Docker Network                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Frontend │  │ Backend  │  │  Celery  │  │
│  │ Next.js  │──│ FastAPI  │──│  Worker  │  │
│  │  :3000   │  │  :8000   │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                      │              │        │
│              ┌───────┴──────────────┘        │
│              │                               │
│  ┌───────────▼──────┐    ┌──────────────┐   │
│  │   PostgreSQL     │    │    Redis     │   │
│  │   with pgvector  │    │    Cache     │   │
│  │     :5432        │    │    :6379     │   │
│  └──────────────────┘    └──────────────┘   │
└─────────────────────────────────────────────┘
```

## 📦 Services

### 1. PostgreSQL (Database)
- **Image**: `ankane/pgvector:latest`
- **Port**: 5432
- **Extensions**: pgvector for embeddings
- **Data**: Persistent volume `postgres_data`

### 2. Redis (Cache & Queue)
- **Image**: `redis:7-alpine`
- **Port**: 6379
- **Persistence**: AOF (Append-Only File)
- **Data**: Persistent volume `redis_data`

### 3. Backend (FastAPI)
- **Port**: 8000
- **Hot Reload**: Enabled in dev mode
- **Dependencies**: Installed in container
- **Volumes**: Source code mounted for development

### 4. Celery Worker
- **Purpose**: Background tasks
- **Queues**: Default, workflows, calls
- **Concurrency**: Auto-scaled

### 5. Celery Beat
- **Purpose**: Scheduled tasks
- **Schedule**: Analytics, cleanup, sync

### 6. Frontend (Next.js)
- **Port**: 3000
- **Hot Reload**: Enabled
- **API Proxy**: Connects to backend

## 🚀 Commands

### Starting Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d postgres
docker-compose up -d backend

# Start with logs
docker-compose up

# Start in development mode (with overrides)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Stopping Services

```bash
# Stop all services
docker-compose stop

# Stop specific service
docker-compose stop backend

# Stop and remove containers
docker-compose down

# Stop, remove, and delete volumes
docker-compose down -v
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Last 100 lines
docker-compose logs --tail=100 backend

# Follow logs from specific time
docker-compose logs --since 30m -f
```

### Service Management

```bash
# Check status
docker-compose ps

# Restart service
docker-compose restart backend

# Rebuild specific service
docker-compose up -d --build backend

# Rebuild all services
docker-compose build --no-cache

# Scale workers
docker-compose up -d --scale celery_worker=3
```

### Entering Containers

```bash
# Backend shell
docker-compose exec backend /bin/bash

# Python shell
docker-compose exec backend python

# PostgreSQL shell
docker-compose exec postgres psql -U voicecon_user -d voicecon

# Redis CLI
docker-compose exec redis redis-cli
```

## 🛠️ Development Workflow

### 1. Initial Setup

```bash
# Start infrastructure
cd infrastructure/docker
docker-compose up -d postgres redis

# Wait for PostgreSQL to be ready
sleep 5

# Run migrations
docker-compose exec backend alembic upgrade head

# Seed database
docker-compose exec backend python scripts/seed_data.py

# Start application services
docker-compose up -d backend frontend celery_worker
```

### 2. Making Changes

#### Backend Changes
```bash
# Code changes are auto-reloaded
# Just edit files in backend/app/

# If you change requirements.txt
docker-compose build backend
docker-compose up -d backend

# If you change database models
docker-compose exec backend alembic revision --autogenerate -m "Your message"
docker-compose exec backend alembic upgrade head
```

#### Frontend Changes
```bash
# Code changes are auto-reloaded
# Just edit files in frontend/src/

# If you change package.json
docker-compose build frontend
docker-compose up -d frontend
```

### 3. Database Operations

```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "Add new field"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback migration
docker-compose exec backend alembic downgrade -1

# View migration history
docker-compose exec backend alembic history

# Seed data
docker-compose exec backend python scripts/seed_data.py

# Clear and reseed
docker-compose exec backend python scripts/seed_data.py clear
docker-compose exec backend python scripts/seed_data.py
```

### 4. Debugging

```bash
# View real-time logs
docker-compose logs -f backend

# Check container resource usage
docker stats

# Inspect container
docker-compose exec backend env

# Check network connectivity
docker-compose exec backend ping postgres
docker-compose exec backend curl http://frontend:3000

# Test database connection
docker-compose exec backend python -c "from app.database import sync_engine; sync_engine.connect()"
```

## 🔧 Configuration

### Environment Variables

**Backend (.env)**
```env
DATABASE_URL=postgresql://voicecon_user:voicecon_password_dev@postgres:5432/voicecon
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
ENVIRONMENT=development
DEBUG=True
```

**Frontend (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Docker Compose Overrides

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'

services:
  backend:
    environment:
      - LOG_LEVEL=DEBUG
    ports:
      - "8001:8000"  # Different port

  frontend:
    environment:
      - NODE_ENV=development
    command: npm run dev -- --turbo
```

## 📊 Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Database
docker-compose exec postgres pg_isready -U voicecon_user

# Redis
docker-compose exec redis redis-cli ping
```

### Resource Usage

```bash
# All containers
docker stats

# Specific container
docker stats voicecon_backend

# Disk usage
docker system df
```

### Logs Analysis

```bash
# Error logs only
docker-compose logs | grep ERROR

# Count log entries
docker-compose logs backend | wc -l

# Export logs
docker-compose logs > voicecon_logs.txt
```

## 🧹 Cleanup

### Remove Everything

```bash
# Stop and remove containers
docker-compose down

# Also remove volumes (deletes data!)
docker-compose down -v

# Also remove images
docker-compose down --rmi all

# Complete cleanup
docker-compose down -v --rmi all --remove-orphans
```

### Prune Unused Resources

```bash
# Remove unused containers
docker container prune

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove everything unused
docker system prune -a --volumes
```

## 🚨 Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"
```

### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Check container status
docker-compose ps

# Remove and recreate
docker-compose rm backend
docker-compose up -d backend
```

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres

# Wait for it to be ready
docker-compose exec postgres pg_isready -U voicecon_user
```

### Out of Disk Space

```bash
# Check disk usage
docker system df

# Clean up
docker system prune -a --volumes

# Remove old images
docker image prune -a
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Limit resources in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## 🔐 Production Considerations

### Security

```yaml
# Use secrets instead of environment variables
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  backend:
    secrets:
      - db_password
```

### Performance

```yaml
# Use restart policy
services:
  backend:
    restart: unless-stopped

  # Optimize build
  build:
    context: .
    cache_from:
      - myapp:latest
```

### Scaling

```bash
# Scale workers
docker-compose up -d --scale celery_worker=5

# Use Docker Swarm or Kubernetes for production
```

## 📚 Best Practices

1. **Use .dockerignore**
   - Exclude node_modules, venv, .git
   - Reduces image size
   - Faster builds

2. **Multi-stage builds**
   - Separate build and runtime stages
   - Smaller production images
   - Better caching

3. **Health checks**
   - Add to all services
   - Ensures containers are actually working
   - Auto-restart on failure

4. **Volume mounts**
   - Use for development hot-reload
   - Named volumes for data persistence
   - Avoid for production secrets

5. **Environment specific configs**
   - docker-compose.yml - base config
   - docker-compose.dev.yml - development overrides
   - docker-compose.prod.yml - production settings

## 🎯 Common Workflows

### Fresh Start

```bash
# Complete reset
docker-compose down -v
docker-compose up -d postgres redis
sleep 5
docker-compose exec backend alembic upgrade head
docker-compose exec backend python scripts/seed_data.py
docker-compose up -d
```

### Daily Development

```bash
# Morning
docker-compose up -d

# Work on code (auto-reloads)
# ...

# Evening
docker-compose stop
```

### Before Committing

```bash
# Run tests
docker-compose exec backend pytest

# Check logs for errors
docker-compose logs | grep ERROR

# Lint code
docker-compose exec backend black app/
docker-compose exec frontend npm run lint
```

## 📖 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
- [Next.js with Docker](https://nextjs.org/docs/deployment#docker-image)

---

Happy Dockering! 🐳

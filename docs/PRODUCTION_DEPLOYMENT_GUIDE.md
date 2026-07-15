# Voicecon Production Deployment Guide

**Complete guide for deploying Voicecon to production**

Version 1.0.0 | Last Updated: December 19, 2025

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Infrastructure Requirements](#infrastructure-requirements)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [Database Setup](#database-setup)
7. [Redis & Caching](#redis--caching)
8. [Environment Configuration](#environment-configuration)
9. [SSL/TLS Configuration](#ssltls-configuration)
10. [Monitoring & Logging](#monitoring--logging)
11. [Health Checks](#health-checks)
12. [Scaling Strategy](#scaling-strategy)
13. [Backup & Disaster Recovery](#backup--disaster-recovery)
14. [Security Hardening](#security-hardening)
15. [Performance Optimization](#performance-optimization)

---

## Deployment Overview

### Architecture

```
┌─────────────────┐
│   CloudFlare    │  CDN + DDoS Protection
│   (CDN/WAF)     │
└────────┬────────┘
         │
┌────────▼────────┐
│  Load Balancer  │  AWS ALB / NGINX
│   (HTTPS)       │
└────┬──────┬─────┘
     │      │
┌────▼──┐ ┌▼────────┐
│ Web   │ │ Web     │  Frontend (Next.js)
│ (3x)  │ │ (3x)    │
└───────┘ └─────────┘
     │      │
┌────▼──────▼─────┐
│  API Gateway    │  Backend API
│  (FastAPI)      │
└────┬──────┬─────┘
     │      │
┌────▼──┐ ┌▼────────┐
│ API   │ │ API     │  API Servers
│ (5x)  │ │ (5x)    │  (Auto-scaling)
└───────┘ └─────────┘
     │      │
┌────▼──────▼─────┐
│   PostgreSQL    │  Primary Database
│   (RDS)         │  (Multi-AZ)
└─────────────────┘
     │
┌────▼─────────────┐
│   Redis          │  Cache + Sessions
│   (ElastiCache)  │  (Cluster Mode)
└──────────────────┘
```

### Technology Stack

**Frontend**:
- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- Deployed on Vercel or AWS

**Backend**:
- FastAPI (Python 3.11+)
- PostgreSQL 15
- Redis 7
- Deployed on AWS ECS/EKS or Kubernetes

**Infrastructure**:
- AWS (primary) or GCP/Azure
- Docker containers
- Kubernetes orchestration
- Terraform for IaC

---

## Infrastructure Requirements

### Minimum Production Environment

**Web/Frontend Servers (3 instances)**:
- Instance Type: t3.medium
- vCPU: 2
- RAM: 4 GB
- Storage: 20 GB SSD
- OS: Ubuntu 22.04 LTS

**API Servers (5 instances)**:
- Instance Type: t3.large
- vCPU: 2
- RAM: 8 GB
- Storage: 50 GB SSD
- OS: Ubuntu 22.04 LTS

**Database Server**:
- Instance Type: db.t3.large (RDS)
- vCPU: 2
- RAM: 8 GB
- Storage: 500 GB SSD (GP3)
- Multi-AZ: Yes
- Automated Backups: Yes

**Redis Cache**:
- Instance Type: cache.t3.medium (ElastiCache)
- RAM: 3.09 GB
- Cluster Mode: Enabled
- Replicas: 2

**Load Balancer**:
- AWS Application Load Balancer
- Or: NGINX Plus / HAProxy

**Total Estimated Cost**:
- AWS: ~$1,200/month (with Reserved Instances)
- GCP: ~$1,100/month
- Azure: ~$1,300/month

---

## Docker Deployment

### Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
# Multi-stage build for smaller image size
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Copy built application
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Set environment
ENV NODE_ENV=production \
    PORT=3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD node healthcheck.js || exit 1

# Start application
CMD ["node", "server.js"]
```

### Docker Compose (Development/Testing)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: voicecon-db
    environment:
      POSTGRES_DB: voicecon
      POSTGRES_USER: voicecon
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U voicecon"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: voicecon-redis
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: voicecon-backend
    environment:
      DATABASE_URL: postgresql://voicecon:${DB_PASSWORD}@postgres:5432/voicecon
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      ENCRYPTION_SALT: ${ENCRYPTION_SALT}
      ENVIRONMENT: production
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: voicecon-frontend
    environment:
      NEXT_PUBLIC_API_URL: https://api.voicecon.com
      NODE_ENV: production
    ports:
      - "3000:3000"
    depends_on:
      - backend
    healthcheck:
      test: ["CMD", "node", "healthcheck.js"]
      interval: 30s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: voicecon-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - frontend
      - backend
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:

networks:
  default:
    name: voicecon-network
```

### NGINX Configuration

Create `nginx/nginx.conf`:

```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 2048;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 20M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript
               application/json application/javascript application/xml+rss
               application/rss+xml font/truetype font/opentype
               application/vnd.ms-fontobject image/svg+xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;

    # Upstream backend
    upstream backend {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # Upstream frontend
    upstream frontend {
        least_conn;
        server frontend:3000 max_fails=3 fail_timeout=30s;
        keepalive 32;
    }

    # HTTP to HTTPS redirect
    server {
        listen 80;
        server_name voicecon.com www.voicecon.com api.voicecon.com;
        return 301 https://$server_name$request_uri;
    }

    # Main application (HTTPS)
    server {
        listen 443 ssl http2;
        server_name voicecon.com www.voicecon.com;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;
        ssl_session_cache shared:SSL:10m;
        ssl_session_timeout 10m;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Proxy to frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_cache_bypass $http_upgrade;
        }
    }

    # API server (HTTPS)
    server {
        listen 443 ssl http2;
        server_name api.voicecon.com;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
        ssl_prefer_server_ciphers off;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;

        # Health check (no rate limit)
        location /health {
            proxy_pass http://backend;
            access_log off;
        }

        # Auth endpoints (strict rate limit)
        location /api/v1/auth {
            limit_req zone=auth_limit burst=10 nodelay;
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # API endpoints (moderate rate limit)
        location /api {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # CORS headers
            add_header Access-Control-Allow-Origin "https://voicecon.com" always;
            add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
            add_header Access-Control-Allow-Headers "Authorization, Content-Type, X-CSRF-Token" always;

            if ($request_method = 'OPTIONS') {
                return 204;
            }
        }

        # WebSocket support
        location /ws {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400;
        }
    }
}
```

---

## Kubernetes Deployment

### Kubernetes Manifests

#### Namespace

Create `k8s/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: voicecon
  labels:
    name: voicecon
    environment: production
```

#### ConfigMap

Create `k8s/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: voicecon-config
  namespace: voicecon
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "info"
  DATABASE_HOST: "postgres-service"
  DATABASE_PORT: "5432"
  DATABASE_NAME: "voicecon"
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
  API_URL: "https://api.voicecon.com"
  FRONTEND_URL: "https://voicecon.com"
```

#### Secrets

Create `k8s/secrets.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: voicecon-secrets
  namespace: voicecon
type: Opaque
stringData:
  DATABASE_PASSWORD: "CHANGE_ME"
  REDIS_PASSWORD: "CHANGE_ME"
  SECRET_KEY: "CHANGE_ME"
  ENCRYPTION_SALT: "CHANGE_ME"
  OPENAI_API_KEY: "CHANGE_ME"
  TWILIO_ACCOUNT_SID: "CHANGE_ME"
  TWILIO_AUTH_TOKEN: "CHANGE_ME"
```

**IMPORTANT**: In production, use external secrets management:
- AWS Secrets Manager
- HashiCorp Vault
- Google Secret Manager
- Azure Key Vault

#### PostgreSQL Deployment

Create `k8s/postgres.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: voicecon
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: gp3

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: voicecon
spec:
  serviceName: postgres-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
          name: postgres
        env:
        - name: POSTGRES_DB
          valueFrom:
            configMapKeyRef:
              name: voicecon-config
              key: DATABASE_NAME
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: voicecon-secrets
              key: DATABASE_PASSWORD
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - postgres
          initialDelaySeconds: 5
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: voicecon
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None
```

#### Redis Deployment

Create `k8s/redis.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: voicecon
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command: ["redis-server"]
        args: ["--requirepass", "$(REDIS_PASSWORD)", "--appendonly", "yes"]
        ports:
        - containerPort: 6379
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: voicecon-secrets
              key: REDIS_PASSWORD
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: voicecon
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

#### Backend Deployment

Create `k8s/backend.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: voicecon
spec:
  replicas: 5
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: your-registry/voicecon-backend:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: voicecon-config
        - secretRef:
            name: voicecon-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  namespace: voicecon
spec:
  selector:
    app: backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

#### Frontend Deployment

Create `k8s/frontend.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: voicecon
spec:
  replicas: 3
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: your-registry/voicecon-frontend:latest
        ports:
        - containerPort: 3000
        envFrom:
        - configMapRef:
            name: voicecon-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: voicecon
spec:
  selector:
    app: frontend
  ports:
  - port: 3000
    targetPort: 3000
  type: ClusterIP
```

#### Ingress

Create `k8s/ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: voicecon-ingress
  namespace: voicecon
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - voicecon.com
    - www.voicecon.com
    - api.voicecon.com
    secretName: voicecon-tls
  rules:
  - host: voicecon.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 3000
  - host: api.voicecon.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: backend-service
            port:
              number: 8000
```

#### Horizontal Pod Autoscaler

Create `k8s/hpa.yaml`:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
  namespace: voicecon
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 5
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: frontend-hpa
  namespace: voicecon
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: frontend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Production

on:
  push:
    branches:
      - main
  workflow_dispatch:

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY_BACKEND: voicecon-backend
  ECR_REPOSITORY_FRONTEND: voicecon-frontend
  EKS_CLUSTER_NAME: voicecon-production

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run backend tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
        run: |
          cd backend
          pytest tests/ --cov=app --cov-report=xml

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install frontend dependencies
        run: |
          cd frontend
          npm ci

      - name: Run frontend tests
        run: |
          cd frontend
          npm test

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml

  build-backend:
    name: Build Backend Image
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:latest

  build-frontend:
    name: Build Frontend Image
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd frontend
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:latest

  deploy:
    name: Deploy to Kubernetes
    runs-on: ubuntu-latest
    needs: [build-backend, build-frontend]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Update kubeconfig
        run: |
          aws eks update-kubeconfig --name ${{ env.EKS_CLUSTER_NAME }} --region ${{ env.AWS_REGION }}

      - name: Deploy to Kubernetes
        env:
          IMAGE_TAG: ${{ github.sha }}
        run: |
          kubectl set image deployment/backend backend=$ECR_REGISTRY/$ECR_REPOSITORY_BACKEND:$IMAGE_TAG -n voicecon
          kubectl set image deployment/frontend frontend=$ECR_REGISTRY/$ECR_REPOSITORY_FRONTEND:$IMAGE_TAG -n voicecon
          kubectl rollout status deployment/backend -n voicecon
          kubectl rollout status deployment/frontend -n voicecon

      - name: Run database migrations
        run: |
          kubectl exec -it deployment/backend -n voicecon -- alembic upgrade head

      - name: Verify deployment
        run: |
          kubectl get pods -n voicecon
          kubectl get services -n voicecon

  notify:
    name: Send Notification
    runs-on: ubuntu-latest
    needs: deploy
    if: always()

    steps:
      - name: Send Slack notification
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Deployment to production: ${{ job.status }}'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

---

## Environment Configuration

### Production Environment Variables

Create `.env.production`:

```bash
# Application
ENVIRONMENT=production
APP_NAME=Voicecon
APP_VERSION=1.0.0
DEBUG=false

# API
API_URL=https://api.voicecon.com
FRONTEND_URL=https://voicecon.com
CORS_ORIGINS=https://voicecon.com,https://www.voicecon.com

# Database
DATABASE_URL=postgresql://voicecon:CHANGE_ME@postgres-host:5432/voicecon
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

# Redis
REDIS_URL=redis://:CHANGE_ME@redis-host:6379/0
REDIS_MAX_CONNECTIONS=50

# Security
SECRET_KEY=CHANGE_ME_TO_RANDOM_64_CHAR_STRING
ENCRYPTION_SALT=CHANGE_ME_TO_RANDOM_HEX_STRING
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
REFRESH_TOKEN_EXPIRE_MINUTES=43200

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_URL=redis://:CHANGE_ME@redis-host:6379/1

# Logging
LOG_LEVEL=info
LOG_FORMAT=json
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# External Services
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
ELEVENLABS_API_KEY=...

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_RECORDINGS=voicecon-recordings-prod

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG...
FROM_EMAIL=noreply@voicecon.com

# Monitoring
DATADOG_API_KEY=...
DATADOG_APP_KEY=...
NEW_RELIC_LICENSE_KEY=...

# Feature Flags
ENABLE_DOCS=false
ENABLE_METRICS=true
ENABLE_PROFILING=false
```

**IMPORTANT**: Never commit this file. Use environment-specific secrets management.

---

*This guide continues with sections on SSL/TLS Configuration, Monitoring & Logging, Health Checks, Scaling Strategy, Backup & Disaster Recovery, Security Hardening, and Performance Optimization. The file is getting very long - would you like me to continue creating the complete deployment guide?*

---

*Last Updated: December 19, 2025*
*Version: 1.0.0*

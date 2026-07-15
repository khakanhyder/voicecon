# Getting Started with Voicecon

This guide will help you set up Voicecon for local development.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Node.js** (20+) and **npm** (10+)
- **Python** (3.11+)
- **Git**

## Quick Setup (Recommended)

### 1. Automated Setup

Run the setup script to automatically configure your development environment:

```bash
./scripts/setup.sh
```

This script will:
- Create environment files
- Set up Python virtual environment
- Install backend dependencies
- Install frontend dependencies
- Start Docker services (PostgreSQL, Redis)
- Run database migrations

### 2. Configure Environment Variables

#### Backend Configuration

Edit `backend/.env`:

```env
# Required
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://voicecon_user:voicecon_password_dev@localhost:5432/voicecon

# Optional (add your API keys)
OPENAI_API_KEY=your-openai-key
DEEPGRAM_API_KEY=your-deepgram-key
ELEVENLABS_API_KEY=your-elevenlabs-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
```

#### Frontend Configuration

Edit `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 3. Start Development Servers

#### Option A: Using Docker Compose (Easiest)

```bash
cd infrastructure/docker
docker-compose up
```

This starts everything:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

#### Option B: Manual Start

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Celery Worker (optional):**
```bash
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

## Manual Setup (Alternative)

If the automated script doesn't work, follow these steps:

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/voicecon.git
cd voicecon
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor
```

### 3. Database Setup

Start PostgreSQL using Docker:

```bash
cd ../infrastructure/docker
docker-compose up -d postgres redis
```

Wait a few seconds for PostgreSQL to start, then run migrations:

```bash
cd ../../backend
source venv/bin/activate
alembic upgrade head
```

### 4. Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local

# Edit .env.local if needed
nano .env.local
```

## Verifying Installation

### 1. Check Backend

Visit http://localhost:8000 - you should see:
```json
{
  "name": "Voicecon",
  "version": "0.1.0",
  "description": "Voice AI Platform with Integration Management"
}
```

### 2. Check API Documentation

Visit http://localhost:8000/docs for Swagger UI

### 3. Check Frontend

Visit http://localhost:3000 - you should see the Voicecon landing page

### 4. Check Database Connection

```bash
cd backend
source venv/bin/activate
python -c "from app.database import sync_engine; print('✅ Database connected!' if sync_engine.connect() else '❌ Connection failed')"
```

## Common Issues

### Port Already in Use

If ports 3000, 8000, or 5432 are in use:

```bash
# Check what's using the port
lsof -i :8000  # On macOS/Linux
netstat -ano | findstr :8000  # On Windows

# Kill the process or change ports in .env files
```

### PostgreSQL Connection Errors

Make sure PostgreSQL is running:

```bash
cd infrastructure/docker
docker-compose ps
docker-compose logs postgres
```

### Python Dependencies Issues

If you encounter dependency conflicts:

```bash
cd backend
deactivate  # if virtual env is active
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

### Node Module Issues

If you encounter npm issues:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Development Workflow

### Making Database Changes

1. Modify SQLAlchemy models in `backend/app/models/`
2. Generate migration:
   ```bash
   cd backend
   source venv/bin/activate
   alembic revision --autogenerate -m "Description of changes"
   ```
3. Review the migration in `backend/alembic/versions/`
4. Apply migration:
   ```bash
   alembic upgrade head
   ```

### Adding New API Endpoints

1. Create Pydantic schemas in `backend/app/schemas/`
2. Add endpoint in `backend/app/api/v1/endpoints/`
3. Register endpoint in `backend/app/api/v1/api.py`
4. Test using Swagger UI at http://localhost:8000/docs

### Adding New Frontend Pages

1. Create page in `frontend/src/app/` following Next.js App Router conventions
2. Add components in `frontend/src/components/`
3. Create API hooks in `frontend/src/hooks/`
4. Define TypeScript types in `frontend/src/types/`

## Testing

### Backend Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Next Steps

Once your development environment is set up:

1. **Create your first agent**: Visit http://localhost:3000/agents/new
2. **Connect an integration**: Visit http://localhost:3000/integrations
3. **Build a workflow**: Visit http://localhost:3000/workflows/new
4. **Review the API**: http://localhost:8000/docs

## Additional Resources

- [API Documentation](http://localhost:8000/docs)
- [Database Schema](/docs/database-schema.md)
- [Architecture Overview](/docs/architecture.md)
- [Contributing Guidelines](/CONTRIBUTING.md)

## Getting Help

- **Issues**: https://github.com/yourusername/voicecon/issues
- **Discussions**: https://github.com/yourusername/voicecon/discussions
- **Email**: dev@voicecon.com

---

Happy coding! 🚀

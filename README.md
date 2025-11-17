# Voicecon

**The only platform where voice AI meets unlimited integrations**

Voicecon is a comprehensive SaaS platform that combines:
- 🎙️ **Voice AI Agent capabilities** - Create, deploy, and manage AI voice agents
- 🔗 **Integration Ecosystem** - Connect voice agents with 500+ external apps
- ⚡ **No-Code Automation** - Visual workflow builder for non-technical users

## 🏗️ Architecture

### Backend
- **Framework**: FastAPI 0.110+ (Python 3.11+)
- **Database**: PostgreSQL 15+ with pgvector
- **Cache**: Redis 7+
- **Task Queue**: Celery
- **Authentication**: JWT, OAuth2

### Frontend
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5+
- **Styling**: TailwindCSS 3+ with Shadcn/ui
- **State Management**: Zustand + React Query

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Orchestration**: Kubernetes (production)
- **CI/CD**: GitHub Actions

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 20+ and npm
- Python 3.11+
- PostgreSQL 15+ (or use Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/khakan/voicecon.git
cd voicecon
```

### 2. Set Up Backend

```bash
cd backend

# Copy environment variables
cp .env.example .env

# Edit .env with your configuration
# At minimum, set SECRET_KEY and database credentials

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 3. Set Up Frontend

```bash
cd frontend

# Copy environment variables
cp .env.local.example .env.local

# Install dependencies
npm install

# Start the development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### 4. Using Docker Compose (Recommended)

```bash
# From the project root
cd infrastructure/docker

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

This will start:
- PostgreSQL with pgvector (port 5432)
- Redis (port 6379)
- Backend API (port 8000)
- Frontend (port 3000)
- Celery Worker
- Celery Beat

## 📁 Project Structure

```
voicecon/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   ├── core/              # Core utilities
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   └── workers/           # Celery tasks
│   ├── alembic/               # Database migrations
│   └── tests/                 # Backend tests
│
├── frontend/                   # Next.js frontend
│   └── src/
│       ├── app/               # Next.js App Router pages
│       ├── components/        # React components
│       ├── hooks/             # Custom React hooks
│       ├── lib/               # Utilities
│       └── types/             # TypeScript types
│
├── infrastructure/            # Infrastructure config
│   ├── docker/               # Docker Compose files
│   └── kubernetes/           # K8s manifests
│
└── docs/                      # Documentation
```

## 🔧 Configuration

### Backend Environment Variables

See `backend/.env.example` for all available configuration options.

Key variables:
- `SECRET_KEY`: JWT secret key (required)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key for LLM
- `DEEPGRAM_API_KEY`: Deepgram API key for STT
- `ELEVENLABS_API_KEY`: ElevenLabs API key for TTS
- `TWILIO_ACCOUNT_SID`: Twilio account SID for telephony

### Frontend Environment Variables

See `frontend/.env.local.example` for all available configuration options.

Key variables:
- `NEXT_PUBLIC_API_URL`: Backend API URL
- `NEXT_PUBLIC_WS_URL`: WebSocket URL

## 🧪 Development

### Running Tests

#### Backend
```bash
cd backend
pytest tests/
```

#### Frontend
```bash
cd frontend
npm test
```

### Code Formatting

#### Backend
```bash
cd backend
black app/
isort app/
```

#### Frontend
```bash
cd frontend
npm run lint
npm run format
```

### Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1
```

## 📚 API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🎯 Key Features

### Voice AI Agents
- Multiple LLM providers (OpenAI, Anthropic, Google)
- Multiple TTS providers (ElevenLabs, PlayHT, Azure)
- Multiple STT providers (Deepgram, AssemblyAI, Whisper)
- Customizable conversation flows
- Function calling capabilities
- Knowledge base integration with RAG

### Integrations
- 500+ pre-built connectors
- CRM (Salesforce, HubSpot, Zoho)
- Marketing (Mailchimp, SendGrid, ActiveCampaign)
- Calendar (Google Calendar, Outlook, Calendly)
- Communication (Slack, Teams, SMS)
- E-commerce (Shopify, Stripe, WooCommerce)

### Workflow Automation
- Visual workflow builder using React Flow
- Trigger-action based automation
- Data transformation and mapping
- Conditional logic and branching
- Error handling and retries

### Analytics & Reporting
- Real-time call analytics
- Sentiment analysis
- Cost tracking
- Integration performance metrics
- Custom dashboards

## 🔐 Security

- JWT-based authentication
- OAuth2 for third-party integrations
- API key authentication for programmatic access
- Encrypted storage for sensitive data (API keys, tokens)
- Role-based access control (RBAC)
- Rate limiting
- CORS protection

## 🚢 Deployment

### Docker Production Build

```bash
# Build backend
cd backend
docker build -t voicecon-backend:latest .

# Build frontend
cd frontend
docker build -t voicecon-frontend:latest .
```

### Kubernetes

```bash
# Apply Kubernetes manifests
kubectl apply -f infrastructure/kubernetes/
```

## 📝 License

[Your License Here]

## 🤝 Contributing

[Contribution guidelines]

## 📞 Support

For support, email support@voicecon.com or join our Slack community.

## 🗺️ Roadmap

### Phase 1 - MVP (Month 1-2)
- [x] Project setup and infrastructure
- [ ] User authentication and organization management
- [ ] Basic agent creation and configuration
- [ ] Simple telephony integration
- [ ] Core integrations (5-10 popular services)

### Phase 2 - Core Features (Month 3)
- [ ] Visual workflow builder
- [ ] Knowledge base with RAG
- [ ] Advanced analytics dashboard
- [ ] 50+ integration connectors
- [ ] Template marketplace

### Phase 3 - Scale (Month 4)
- [ ] Multi-agent orchestration (Squads)
- [ ] Advanced call features
- [ ] 200+ integration connectors
- [ ] Billing and subscriptions
- [ ] White-label options

## 🌟 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)
- [Shadcn/ui](https://ui.shadcn.com/)
- [React Flow](https://reactflow.dev/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Tailwind CSS](https://tailwindcss.com/)

---

Made with ❤️ by the Voicecon team

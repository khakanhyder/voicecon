#!/bin/bash

# Voicecon Setup Script
# This script sets up the development environment for Voicecon

set -e

echo "🚀 Setting up Voicecon development environment..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${BLUE}✅ Docker and Docker Compose found${NC}"

# Navigate to project root
cd "$(dirname "$0")/.."

# Backend setup
echo -e "${BLUE}📦 Setting up backend...${NC}"
cd backend

if [ ! -f ".env" ]; then
    echo -e "${BLUE}📝 Creating .env file from example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Created .env file. Please update it with your configuration.${NC}"
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo -e "${BLUE}🐍 Creating Python virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment and install dependencies
echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
echo -e "${GREEN}✅ Python dependencies installed${NC}"

cd ..

# Frontend setup
echo -e "${BLUE}📦 Setting up frontend...${NC}"
cd frontend

if [ ! -f ".env.local" ]; then
    echo -e "${BLUE}📝 Creating .env.local file from example...${NC}"
    cp .env.local.example .env.local
    echo -e "${GREEN}✅ Created .env.local file${NC}"
else
    echo -e "${GREEN}✅ .env.local file already exists${NC}"
fi

# Install Node dependencies
if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}📦 Installing Node.js dependencies...${NC}"
    npm install
    echo -e "${GREEN}✅ Node.js dependencies installed${NC}"
else
    echo -e "${GREEN}✅ node_modules already exists${NC}"
fi

cd ..

# Start Docker services
echo -e "${BLUE}🐳 Starting Docker services...${NC}"
cd infrastructure/docker
docker-compose up -d postgres redis

echo -e "${BLUE}⏳ Waiting for PostgreSQL to be ready...${NC}"
sleep 5

cd ../../backend
source venv/bin/activate

# Run database migrations
echo -e "${BLUE}🗄️  Running database migrations...${NC}"
alembic upgrade head
echo -e "${GREEN}✅ Database migrations complete${NC}"

cd ..

echo -e "${GREEN}"
echo "============================================"
echo "✨ Voicecon setup complete! ✨"
echo "============================================"
echo -e "${NC}"
echo ""
echo -e "${BLUE}📝 Next steps:${NC}"
echo ""
echo "1. Update backend/.env with your API keys and configuration"
echo "2. Update frontend/.env.local if needed"
echo ""
echo -e "${BLUE}🚀 To start development:${NC}"
echo ""
echo "Backend:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload"
echo ""
echo "Frontend:"
echo "  cd frontend"
echo "  npm run dev"
echo ""
echo "Or use Docker Compose:"
echo "  cd infrastructure/docker"
echo "  docker-compose up"
echo ""
echo -e "${GREEN}Happy coding! 🎉${NC}"

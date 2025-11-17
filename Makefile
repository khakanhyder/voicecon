# Voicecon Makefile
# Convenience commands for development

.PHONY: help setup start stop restart logs clean migrate seed test lint format

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Voicecon Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

setup: ## Initial project setup
	@echo "$(BLUE)🚀 Setting up Voicecon...$(NC)"
	@./scripts/setup.sh

start: ## Start all services with Docker Compose
	@echo "$(BLUE)🐳 Starting services...$(NC)"
	@cd infrastructure/docker && docker-compose up -d
	@echo "$(GREEN)✅ Services started!$(NC)"
	@echo "Frontend: http://localhost:3000"
	@echo "Backend:  http://localhost:8000"
	@echo "API Docs: http://localhost:8000/docs"

stop: ## Stop all services
	@echo "$(BLUE)🛑 Stopping services...$(NC)"
	@cd infrastructure/docker && docker-compose stop
	@echo "$(GREEN)✅ Services stopped$(NC)"

restart: stop start ## Restart all services

logs: ## View logs from all services
	@cd infrastructure/docker && docker-compose logs -f

logs-backend: ## View backend logs
	@cd infrastructure/docker && docker-compose logs -f backend

logs-frontend: ## View frontend logs
	@cd infrastructure/docker && docker-compose logs -f frontend

ps: ## Show running containers
	@cd infrastructure/docker && docker-compose ps

migrate: ## Run database migrations
	@echo "$(BLUE)🗄️  Running migrations...$(NC)"
	@./scripts/migrate.sh upgrade

migrate-create: ## Create a new migration (make migrate-create msg="Your message")
	@echo "$(BLUE)📝 Creating migration...$(NC)"
	@./scripts/migrate.sh create "$(msg)"

migrate-rollback: ## Rollback last migration
	@echo "$(BLUE)⬇️  Rolling back migration...$(NC)"
	@./scripts/migrate.sh downgrade 1

seed: ## Seed database with sample data
	@echo "$(BLUE)🌱 Seeding database...$(NC)"
	@./scripts/seed.sh

clean: ## Clean up Docker resources
	@echo "$(BLUE)🧹 Cleaning up...$(NC)"
	@cd infrastructure/docker && docker-compose down
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: ## Clean up everything including volumes
	@echo "$(RED)⚠️  This will delete all data!$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ $$confirm = y ] || exit 1
	@cd infrastructure/docker && docker-compose down -v
	@echo "$(GREEN)✅ Complete cleanup done$(NC)"

rebuild: ## Rebuild all containers
	@echo "$(BLUE)🔨 Rebuilding containers...$(NC)"
	@cd infrastructure/docker && docker-compose build --no-cache
	@echo "$(GREEN)✅ Rebuild complete$(NC)"

test-backend: ## Run backend tests
	@echo "$(BLUE)🧪 Running backend tests...$(NC)"
	@cd backend && source venv/bin/activate && pytest tests/ -v

test-frontend: ## Run frontend tests
	@echo "$(BLUE)🧪 Running frontend tests...$(NC)"
	@cd frontend && npm test

lint-backend: ## Lint backend code
	@echo "$(BLUE)🔍 Linting backend...$(NC)"
	@cd backend && source venv/bin/activate && flake8 app/

lint-frontend: ## Lint frontend code
	@echo "$(BLUE)🔍 Linting frontend...$(NC)"
	@cd frontend && npm run lint

format-backend: ## Format backend code
	@echo "$(BLUE)✨ Formatting backend...$(NC)"
	@cd backend && source venv/bin/activate && black app/ && isort app/

format-frontend: ## Format frontend code
	@echo "$(BLUE)✨ Formatting frontend...$(NC)"
	@cd frontend && npm run format

shell-backend: ## Open backend container shell
	@cd infrastructure/docker && docker-compose exec backend /bin/bash

shell-db: ## Open PostgreSQL shell
	@cd infrastructure/docker && docker-compose exec postgres psql -U voicecon_user -d voicecon

shell-redis: ## Open Redis CLI
	@cd infrastructure/docker && docker-compose exec redis redis-cli

dev-backend: ## Run backend locally (without Docker)
	@echo "$(BLUE)🚀 Starting backend...$(NC)"
	@cd backend && source venv/bin/activate && uvicorn app.main:app --reload

dev-frontend: ## Run frontend locally (without Docker)
	@echo "$(BLUE)🚀 Starting frontend...$(NC)"
	@cd frontend && npm run dev

install-backend: ## Install backend dependencies
	@echo "$(BLUE)📦 Installing backend dependencies...$(NC)"
	@cd backend && source venv/bin/activate && pip install -r requirements.txt

install-frontend: ## Install frontend dependencies
	@echo "$(BLUE)📦 Installing frontend dependencies...$(NC)"
	@cd frontend && npm install

update-deps: install-backend install-frontend ## Update all dependencies

status: ## Show project status
	@echo "$(BLUE)📊 Voicecon Status$(NC)"
	@echo ""
	@echo "$(GREEN)Docker Services:$(NC)"
	@cd infrastructure/docker && docker-compose ps
	@echo ""
	@echo "$(GREEN)Disk Usage:$(NC)"
	@docker system df
	@echo ""
	@echo "$(GREEN)Database Status:$(NC)"
	@cd infrastructure/docker && docker-compose exec postgres pg_isready -U voicecon_user || echo "PostgreSQL not running"

health: ## Check health of all services
	@echo "$(BLUE)🏥 Health Check$(NC)"
	@echo ""
	@echo -n "Backend:  "
	@curl -s http://localhost:8000/health > /dev/null && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Down$(NC)"
	@echo -n "Frontend: "
	@curl -s http://localhost:3000 > /dev/null && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Down$(NC)"
	@echo -n "Database: "
	@cd infrastructure/docker && docker-compose exec postgres pg_isready -U voicecon_user > /dev/null 2>&1 && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Down$(NC)"
	@echo -n "Redis:    "
	@cd infrastructure/docker && docker-compose exec redis redis-cli ping > /dev/null 2>&1 && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Down$(NC)"

reset: clean migrate seed ## Reset database (clean, migrate, seed)
	@echo "$(GREEN)✅ Database reset complete!$(NC)"

backup-db: ## Backup database
	@echo "$(BLUE)💾 Backing up database...$(NC)"
	@mkdir -p backups
	@cd infrastructure/docker && docker-compose exec -T postgres pg_dump -U voicecon_user voicecon > ../../backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ Backup created in backups/$(NC)"

restore-db: ## Restore database from backup (make restore-db file=backup.sql)
	@echo "$(BLUE)📥 Restoring database...$(NC)"
	@cd infrastructure/docker && docker-compose exec -T postgres psql -U voicecon_user voicecon < ../../backups/$(file)
	@echo "$(GREEN)✅ Database restored$(NC)"

docs: ## Open API documentation
	@echo "$(BLUE)📖 Opening API docs...$(NC)"
	@open http://localhost:8000/docs || xdg-open http://localhost:8000/docs || echo "Visit http://localhost:8000/docs"

prod-build: ## Build production Docker images
	@echo "$(BLUE)🏗️  Building production images...$(NC)"
	@cd backend && docker build -t voicecon-backend:latest .
	@cd frontend && docker build -t voicecon-frontend:latest .
	@echo "$(GREEN)✅ Production images built$(NC)"

.DEFAULT_GOAL := help

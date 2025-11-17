#!/bin/bash

# Database Migration Script for Voicecon
# Handles database migrations using Alembic

set -e

echo "🗄️  Voicecon Database Migration Script"
echo "========================================"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Navigate to backend directory
cd "$(dirname "$0")/../backend"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Run ./scripts/setup.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if database is accessible
echo -e "${BLUE}🔍 Checking database connection...${NC}"
python -c "from app.database import sync_engine; sync_engine.connect()" 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to database${NC}"
    echo "Make sure PostgreSQL is running:"
    echo "  docker-compose -f infrastructure/docker/docker-compose.yml up -d postgres"
    exit 1
fi

# Parse command line arguments
COMMAND=${1:-"upgrade"}
MESSAGE=${2:-"Auto-generated migration"}

case $COMMAND in
    "create"|"revision")
        echo -e "${BLUE}📝 Creating new migration: $MESSAGE${NC}"
        alembic revision --autogenerate -m "$MESSAGE"
        echo -e "${GREEN}✅ Migration file created in alembic/versions/${NC}"
        echo "Review the migration file before applying it."
        ;;

    "upgrade"|"up")
        echo -e "${BLUE}⬆️  Applying migrations...${NC}"
        alembic upgrade head
        echo -e "${GREEN}✅ Database migrated to latest version${NC}"
        ;;

    "downgrade"|"down")
        STEPS=${2:-"1"}
        echo -e "${YELLOW}⬇️  Rolling back $STEPS migration(s)...${NC}"
        alembic downgrade -$STEPS
        echo -e "${GREEN}✅ Rolled back $STEPS migration(s)${NC}"
        ;;

    "current")
        echo -e "${BLUE}📍 Current migration version:${NC}"
        alembic current
        ;;

    "history")
        echo -e "${BLUE}📜 Migration history:${NC}"
        alembic history
        ;;

    "reset")
        echo -e "${YELLOW}⚠️  WARNING: This will reset the entire database!${NC}"
        read -p "Are you sure? (type 'yes' to confirm): " -r
        if [[ $REPLY == "yes" ]]; then
            echo -e "${BLUE}🔄 Resetting database...${NC}"
            alembic downgrade base
            alembic upgrade head
            echo -e "${GREEN}✅ Database reset complete${NC}"
        else
            echo "Cancelled."
        fi
        ;;

    "initial")
        echo -e "${BLUE}🏗️  Creating initial migration from schema...${NC}"

        # Create initial migration
        alembic revision --autogenerate -m "Initial database schema"

        echo -e "${GREEN}✅ Initial migration created${NC}"
        echo "Review the migration and then run: ./scripts/migrate.sh upgrade"
        ;;

    "help"|"--help"|"-h")
        echo ""
        echo "Usage: ./scripts/migrate.sh [command] [options]"
        echo ""
        echo "Commands:"
        echo "  upgrade, up           Apply all pending migrations (default)"
        echo "  downgrade, down [n]   Rollback n migrations (default: 1)"
        echo "  create, revision MSG  Create a new migration with message"
        echo "  current               Show current migration version"
        echo "  history               Show migration history"
        echo "  reset                 Reset database (downgrade all, then upgrade)"
        echo "  initial               Create initial migration from models"
        echo "  help                  Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./scripts/migrate.sh upgrade"
        echo "  ./scripts/migrate.sh create 'Add user preferences table'"
        echo "  ./scripts/migrate.sh downgrade 2"
        echo "  ./scripts/migrate.sh reset"
        echo ""
        ;;

    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo "Run './scripts/migrate.sh help' for usage information"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done! 🎉${NC}"

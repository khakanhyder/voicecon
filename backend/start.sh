#!/bin/sh
alembic upgrade head
# Seed integration connectors + subscription plans (idempotent: skips existing
# rows). Without this the integration_connectors table is empty and every
# integration shows "Requires Server Config". Non-fatal if it fails.
python -m scripts.seed_data || echo "seed_data failed (continuing startup)"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

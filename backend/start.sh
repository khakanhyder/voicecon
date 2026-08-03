#!/bin/sh
# Migrations must succeed before serving. A container that boots on a stale
# schema returns 500s from every endpoint touching a missing table while the
# deploy still looks green — exit instead, so the platform marks the deploy
# failed and keeps the previous version running.
if ! alembic upgrade head; then
    echo "FATAL: 'alembic upgrade head' failed — refusing to start on a stale schema." >&2
    echo "       Check for multiple heads with 'alembic heads'." >&2
    exit 1
fi
# Seed integration connectors + subscription plans (idempotent: skips existing
# rows). Without this the integration_connectors table is empty and every
# integration shows "Requires Server Config". Non-fatal if it fails.
python -m scripts.seed_data || echo "seed_data failed (continuing startup)"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

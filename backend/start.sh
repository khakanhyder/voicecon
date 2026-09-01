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
# --proxy-headers with a permissive --forwarded-allow-ips: the app runs behind
# the platform's TLS-terminating proxy (Traefik on Dokploy, Railway's edge), and
# uvicorn only honours X-Forwarded-Proto from IPs it trusts — which defaults to
# 127.0.0.1, never the proxy's address on the container network. Without this,
# request.base_url reports http:// on an https deployment and every absolute URL
# the app writes down (avatars, chat embed snippets) is mixed content the browser
# refuses to load. The container is only reachable through that proxy, so
# trusting the hop in front of it is safe; narrow it with FORWARDED_ALLOW_IPS if
# the network says otherwise.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"

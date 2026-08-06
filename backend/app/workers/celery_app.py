"""Celery application configuration."""
from celery import Celery
from celery.schedules import crontab
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "voicecon",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Subscription reconciliation also runs in-process inside the API (see
    # app.services.billing.scheduler), so a deployment without a Celery beat
    # still expires trials and sends notices. These entries are for setups that
    # would rather own the schedule here; the tasks are idempotent, so both
    # running is harmless.
    beat_schedule={
        "billing-reconcile-subscriptions": {
            "task": "billing.reconcile_subscriptions",
            "schedule": crontab(minute="*/15"),
        },
        "billing-reset-period-counters": {
            "task": "billing.reset_period_counters",
            "schedule": crontab(hour=0, minute=5),
        },
    },
)

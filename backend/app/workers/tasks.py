"""Background tasks."""
import asyncio
import logging

from app.workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task
def health_check():
    """Simple health check task."""
    return {"status": "ok"}


def _run(coro):
    """Run an async coroutine from a synchronous Celery task."""
    return asyncio.run(coro)


@app.task(name="billing.reconcile_subscriptions")
def reconcile_subscriptions_task():
    """Expire lapsed trials and subscriptions, and fire their side effects.

    The same reconciliation also runs in-process inside the API
    (``app.services.billing.scheduler``), because it must happen wherever the
    app runs and not only where a Celery worker happens to be deployed. Every
    transition is idempotent, so having both scheduled is safe — deployments
    that prefer a worker can simply not start the in-process one.
    """
    from app.database import get_db_session
    from app.services.billing.reconciler import reconcile_subscriptions

    async def run():
        async with get_db_session() as db:
            report = await reconcile_subscriptions(db)
            return str(report)

    result = _run(run())
    logger.info(f"billing.reconcile_subscriptions: {result}")
    return {"status": "ok", "report": result}


@app.task(name="billing.reset_period_counters")
def reset_period_counters_task():
    """Roll usage counters for subscriptions Stripe never invoices."""
    from app.database import get_db_session
    from app.services.billing.reconciler import reset_expired_period_counters

    async def run():
        async with get_db_session() as db:
            return await reset_expired_period_counters(db)

    rolled = _run(run())
    return {"status": "ok", "rolled": rolled}

"""
In-process scheduler that drives subscription reconciliation.

Runs inside the API process, like the analytics and workflow schedulers, rather
than depending on a Celery worker being deployed — the reconciler is not
optional plumbing, it is what sends expiry emails and reclaims resources, so it
has to run wherever the app runs. A Celery task wrapping the same function is
registered in ``app.workers.tasks`` for deployments that prefer to move it out.

Safe to run in several processes at once: every transition is idempotent, so the
worst case of two workers sweeping simultaneously is a wasted query.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from app.database import get_db_session

logger = logging.getLogger(__name__)

#: How often to sweep. Access control does not depend on this interval — the
#: entitlement resolver derives expiry per request — so this only governs how
#: quickly the *side effects* (emails, audit rows, resource release) follow.
RECONCILE_INTERVAL_SECONDS = 15 * 60

#: Counter rolls are cheap and only matter daily.
COUNTER_RESET_INTERVAL_SECONDS = 60 * 60

#: Wait before the first sweep so startup isn't competing with request traffic.
STARTUP_DELAY_SECONDS = 30


class BillingScheduler:
    """Periodic subscription reconciliation."""

    def __init__(self) -> None:
        self.is_running = False
        self.tasks: List[asyncio.Task] = []

    async def start(self) -> None:
        if self.is_running:
            logger.warning("Billing scheduler is already running")
            return

        self.is_running = True
        self.tasks = [
            asyncio.create_task(self._run_reconcile_job()),
            asyncio.create_task(self._run_counter_reset_job()),
        ]
        logger.info("Billing scheduler started")

    async def stop(self) -> None:
        if not self.is_running:
            return

        self.is_running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        logger.info("Billing scheduler stopped")

    async def _run_reconcile_job(self) -> None:
        from app.services.billing.reconciler import reconcile_subscriptions

        await asyncio.sleep(STARTUP_DELAY_SECONDS)
        while self.is_running:
            try:
                async with get_db_session() as db:
                    await reconcile_subscriptions(db)
            except asyncio.CancelledError:
                logger.info("Subscription reconcile job cancelled")
                break
            except Exception as exc:
                logger.error(f"Subscription reconcile failed: {exc}", exc_info=True)
            try:
                await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    async def _run_counter_reset_job(self) -> None:
        from app.services.billing.reconciler import reset_expired_period_counters

        await asyncio.sleep(STARTUP_DELAY_SECONDS * 2)
        while self.is_running:
            try:
                async with get_db_session() as db:
                    await reset_expired_period_counters(db)
            except asyncio.CancelledError:
                logger.info("Usage counter reset job cancelled")
                break
            except Exception as exc:
                logger.error(f"Usage counter reset failed: {exc}", exc_info=True)
            try:
                await asyncio.sleep(COUNTER_RESET_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break


_scheduler: Optional[BillingScheduler] = None


def get_billing_scheduler() -> BillingScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BillingScheduler()
    return _scheduler


async def start_billing_scheduler() -> None:
    await get_billing_scheduler().start()


async def stop_billing_scheduler() -> None:
    await get_billing_scheduler().stop()

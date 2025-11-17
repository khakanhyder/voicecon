"""
Analytics Scheduler Service

This module handles scheduled analytics aggregation jobs.
Jobs run on a schedule to pre-aggregate data for performance.
"""
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.user import Organization
from app.services.analytics.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class AnalyticsScheduler:
    """
    Manages scheduled analytics aggregation jobs.

    Runs periodic tasks to aggregate data:
    - Hourly: Real-time metrics update
    - Daily: Call metrics, agent metrics, integration metrics, daily summary
    - Weekly: Cleanup old cache entries
    """

    def __init__(self):
        self.is_running = False
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        """Start all scheduled jobs."""
        if self.is_running:
            logger.warning("Analytics scheduler is already running")
            return

        self.is_running = True
        logger.info("Starting analytics scheduler...")

        # Start periodic tasks
        self.tasks = [
            asyncio.create_task(self._run_realtime_metrics_job()),
            asyncio.create_task(self._run_daily_aggregation_job()),
            asyncio.create_task(self._run_cache_cleanup_job()),
        ]

        logger.info("Analytics scheduler started successfully")

    async def stop(self):
        """Stop all scheduled jobs."""
        if not self.is_running:
            return

        logger.info("Stopping analytics scheduler...")
        self.is_running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        logger.info("Analytics scheduler stopped")

    async def _run_realtime_metrics_job(self):
        """
        Update real-time metrics every minute.

        This job runs continuously, updating real-time metrics
        for all organizations every 60 seconds.
        """
        logger.info("Real-time metrics job started")

        while self.is_running:
            try:
                await self._update_all_realtime_metrics()

                # Wait 1 minute before next run
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                logger.info("Real-time metrics job cancelled")
                break
            except Exception as e:
                logger.error(f"Error in real-time metrics job: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(60)

    async def _run_daily_aggregation_job(self):
        """
        Run daily aggregation at 1 AM.

        Aggregates yesterday's data:
        - Call metrics
        - Agent metrics
        - Integration metrics
        - Daily summary
        """
        logger.info("Daily aggregation job started")

        while self.is_running:
            try:
                now = datetime.now()

                # Calculate next run time (1 AM)
                next_run = now.replace(hour=1, minute=0, second=0, microsecond=0)
                if now.hour >= 1:
                    # If past 1 AM, schedule for tomorrow
                    next_run += timedelta(days=1)

                # Wait until next run time
                wait_seconds = (next_run - now).total_seconds()
                logger.info(f"Next daily aggregation in {wait_seconds / 3600:.2f} hours")
                await asyncio.sleep(wait_seconds)

                # Run aggregation
                await self._run_daily_aggregation()

            except asyncio.CancelledError:
                logger.info("Daily aggregation job cancelled")
                break
            except Exception as e:
                logger.error(f"Error in daily aggregation job: {e}", exc_info=True)
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)

    async def _run_cache_cleanup_job(self):
        """
        Clean up expired cache entries every 6 hours.

        Removes cache entries that have passed their expiration time.
        """
        logger.info("Cache cleanup job started")

        while self.is_running:
            try:
                await self._cleanup_expired_cache()

                # Wait 6 hours before next run
                await asyncio.sleep(6 * 3600)

            except asyncio.CancelledError:
                logger.info("Cache cleanup job cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup job: {e}", exc_info=True)
                # Wait 1 hour before retrying
                await asyncio.sleep(3600)

    async def _update_all_realtime_metrics(self):
        """Update real-time metrics for all organizations."""
        logger.debug("Updating real-time metrics for all organizations")

        async with get_db_session() as db:
            # Get all active organizations
            result = await db.execute(
                select(Organization).where(Organization.is_active == True)
            )
            organizations = result.scalars().all()

            analytics_service = AnalyticsService(db)

            # Update metrics for each organization
            for org in organizations:
                try:
                    await analytics_service.update_realtime_metrics(org.id)
                    logger.debug(f"Updated real-time metrics for organization {org.id}")
                except Exception as e:
                    logger.error(
                        f"Failed to update real-time metrics for organization {org.id}: {e}",
                        exc_info=True
                    )

            await db.commit()

        logger.info(f"Updated real-time metrics for {len(organizations)} organizations")

    async def _run_daily_aggregation(self):
        """Run daily aggregation for all organizations."""
        logger.info("Running daily aggregation for all organizations")

        yesterday = date.today() - timedelta(days=1)

        async with get_db_session() as db:
            # Get all active organizations
            result = await db.execute(
                select(Organization).where(Organization.is_active == True)
            )
            organizations = result.scalars().all()

            analytics_service = AnalyticsService(db)

            for org in organizations:
                try:
                    # Aggregate call metrics
                    await analytics_service.aggregate_call_metrics(
                        organization_id=org.id,
                        start_date=yesterday,
                        end_date=yesterday,
                        granularity="daily"
                    )

                    # Aggregate agent metrics
                    await analytics_service.aggregate_agent_metrics(
                        organization_id=org.id,
                        start_date=yesterday,
                        end_date=yesterday
                    )

                    # Aggregate integration metrics
                    await analytics_service.aggregate_integration_metrics(
                        organization_id=org.id,
                        start_date=yesterday,
                        end_date=yesterday
                    )

                    # Generate daily summary
                    await analytics_service.generate_daily_summary(
                        organization_id=org.id,
                        summary_date=yesterday
                    )

                    logger.info(f"Completed daily aggregation for organization {org.id}")

                except Exception as e:
                    logger.error(
                        f"Failed daily aggregation for organization {org.id}: {e}",
                        exc_info=True
                    )

            await db.commit()

        logger.info(f"Completed daily aggregation for {len(organizations)} organizations")

    async def _cleanup_expired_cache(self):
        """Remove expired cache entries."""
        logger.debug("Cleaning up expired cache entries")

        async with get_db_session() as db:
            analytics_service = AnalyticsService(db)
            deleted_count = await analytics_service.cleanup_expired_cache()
            await db.commit()

        logger.info(f"Cleaned up {deleted_count} expired cache entries")


# Global scheduler instance
_scheduler: AnalyticsScheduler = None


async def get_scheduler() -> AnalyticsScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AnalyticsScheduler()
    return _scheduler


async def start_scheduler():
    """Start the analytics scheduler."""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler():
    """Stop the analytics scheduler."""
    scheduler = await get_scheduler()
    await scheduler.stop()

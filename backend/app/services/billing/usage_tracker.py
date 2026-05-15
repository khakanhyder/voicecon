"""
Usage tracking utility for automatic billing.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription, UsageRecord
from app.models.call import Call

logger = logging.getLogger(__name__)


class UsageTracker:
    """Service for tracking and recording usage for billing."""

    @staticmethod
    async def record_call_usage(
        db: AsyncSession,
        call_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[UsageRecord]:
        """
        Record usage for a completed call.

        Args:
            db: Database session
            call_id: Call UUID
            organization_id: Organization UUID

        Returns:
            Created usage record or None
        """
        try:
            # Get active subscription
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.organization_id == organization_id,
                        Subscription.status.in_(["active", "trialing"]),
                    )
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.debug(
                    f"No active subscription for organization {organization_id}, skipping usage tracking"
                )
                return None

            # Get call details
            result = await db.execute(select(Call).where(Call.id == call_id))
            call = result.scalar_one_or_none()

            if not call or not call.duration:
                logger.warning(f"Call {call_id} not found or has no duration")
                return None

            # Calculate minutes (round up)
            minutes = (call.duration + 59) // 60  # Round up to nearest minute

            # Get plan for pricing
            from app.models.subscription import SubscriptionPlan

            result = await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.id == subscription.plan_id
                )
            )
            plan = result.scalar_one_or_none()

            if not plan:
                logger.error(f"Plan not found for subscription {subscription.id}")
                return None

            # Create usage records for both minutes and calls
            # Only charge for overage (beyond included limits)
            minutes_overage = max(
                0, subscription.current_period_minutes + minutes - plan.included_minutes
            )
            calls_overage = max(
                0, subscription.current_period_calls + 1 - plan.included_calls
            )

            # Record minutes usage
            if minutes > 0:
                minutes_record = UsageRecord(
                    subscription_id=subscription.id,
                    organization_id=organization_id,
                    usage_type="minutes",
                    quantity=minutes,
                    unit_price=plan.overage_rate_per_minute
                    if minutes_overage > 0
                    else 0,
                    total_amount=plan.overage_rate_per_minute * minutes_overage
                    if minutes_overage > 0
                    else 0,
                    resource_type="call",
                    resource_id=call_id,
                    period_start=subscription.current_period_start,
                    period_end=subscription.current_period_end,
                    metadata={
                        "call_duration_seconds": call.duration,
                        "from_number": call.from_number,
                        "to_number": call.to_number,
                    },
                )
                db.add(minutes_record)

            # Record call usage
            call_record = UsageRecord(
                subscription_id=subscription.id,
                organization_id=organization_id,
                usage_type="calls",
                quantity=1,
                unit_price=plan.overage_rate_per_call if calls_overage > 0 else 0,
                total_amount=plan.overage_rate_per_call if calls_overage > 0 else 0,
                resource_type="call",
                resource_id=call_id,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
                metadata={
                    "call_duration_seconds": call.duration,
                    "from_number": call.from_number,
                    "to_number": call.to_number,
                },
            )
            db.add(call_record)

            # Update subscription counters
            subscription.current_period_minutes += minutes
            subscription.current_period_calls += 1

            await db.commit()

            logger.info(
                f"Recorded usage for call {call_id}: {minutes} minutes, 1 call"
            )
            return call_record

        except Exception as e:
            logger.error(f"Error recording call usage: {e}")
            await db.rollback()
            return None

    @staticmethod
    async def record_sms_usage(
        db: AsyncSession,
        organization_id: uuid.UUID,
        sms_count: int = 1,
        resource_id: Optional[uuid.UUID] = None,
    ) -> Optional[UsageRecord]:
        """
        Record usage for SMS messages.

        Args:
            db: Database session
            organization_id: Organization UUID
            sms_count: Number of SMS messages
            resource_id: Optional resource UUID

        Returns:
            Created usage record or None
        """
        try:
            # Get active subscription
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.organization_id == organization_id,
                        Subscription.status.in_(["active", "trialing"]),
                    )
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.debug(
                    f"No active subscription for organization {organization_id}"
                )
                return None

            # Get plan for pricing
            from app.models.subscription import SubscriptionPlan

            result = await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.id == subscription.plan_id
                )
            )
            plan = result.scalar_one_or_none()

            if not plan:
                logger.error(f"Plan not found for subscription {subscription.id}")
                return None

            # SMS typically charged at $0.0075 per message
            sms_rate = 0.0075

            # Create usage record
            usage_record = UsageRecord(
                subscription_id=subscription.id,
                organization_id=organization_id,
                usage_type="sms",
                quantity=sms_count,
                unit_price=sms_rate,
                total_amount=sms_rate * sms_count,
                resource_type="sms",
                resource_id=resource_id,
                period_start=subscription.current_period_start,
                period_end=subscription.current_period_end,
            )
            db.add(usage_record)
            await db.commit()

            logger.info(f"Recorded SMS usage: {sms_count} messages")
            return usage_record

        except Exception as e:
            logger.error(f"Error recording SMS usage: {e}")
            await db.rollback()
            return None

    @staticmethod
    async def check_usage_limit(
        db: AsyncSession, organization_id: uuid.UUID, usage_type: str
    ) -> dict:
        """
        Check if organization has reached usage limits.

        Args:
            db: Database session
            organization_id: Organization UUID
            usage_type: Type of usage (minutes, calls, etc.)

        Returns:
            Dictionary with limit status
        """
        try:
            # Get active subscription
            result = await db.execute(
                select(Subscription).where(
                    and_(
                        Subscription.organization_id == organization_id,
                        Subscription.status.in_(["active", "trialing"]),
                    )
                )
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                return {
                    "has_subscription": False,
                    "within_limit": False,
                    "message": "No active subscription",
                }

            # Get plan
            from app.models.subscription import SubscriptionPlan

            result = await db.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.id == subscription.plan_id
                )
            )
            plan = result.scalar_one_or_none()

            if not plan:
                return {
                    "has_subscription": False,
                    "within_limit": False,
                    "message": "Plan not found",
                }

            # Check limits (we allow overage for metered billing)
            if usage_type == "minutes":
                used = subscription.current_period_minutes
                limit = plan.included_minutes
                within_limit = True  # Allow overage
                overage = max(0, used - limit)
            elif usage_type == "calls":
                used = subscription.current_period_calls
                limit = plan.included_calls
                within_limit = True  # Allow overage
                overage = max(0, used - limit)
            else:
                return {
                    "has_subscription": True,
                    "within_limit": True,
                    "message": f"Unknown usage type: {usage_type}",
                }

            return {
                "has_subscription": True,
                "within_limit": within_limit,
                "used": used,
                "limit": limit,
                "overage": overage,
                "message": f"Usage: {used}/{limit} (overage: {overage})",
            }

        except Exception as e:
            logger.error(f"Error checking usage limit: {e}")
            return {
                "has_subscription": False,
                "within_limit": False,
                "message": f"Error: {str(e)}",
            }

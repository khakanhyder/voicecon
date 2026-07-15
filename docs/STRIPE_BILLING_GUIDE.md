# Stripe Billing Integration Guide

Complete guide for the Stripe billing and subscription system in Voicecon.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Database Models](#database-models)
5. [Stripe Service](#stripe-service)
6. [Usage Tracking](#usage-tracking)
7. [API Endpoints](#api-endpoints)
8. [Webhooks](#webhooks)
9. [Frontend Integration](#frontend-integration)
10. [Testing](#testing)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

## Overview

The Voicecon billing system provides comprehensive subscription management, usage tracking, and metered billing through Stripe integration.

### Key Features

- **Subscription Plans**: Multiple pricing tiers with different limits
- **Metered Billing**: Pay-per-use for overages beyond plan limits
- **Automatic Usage Tracking**: Track call minutes and calls automatically
- **Invoice Management**: Automatic invoice generation and payment processing
- **Payment Failure Handling**: Automatic retry and notification system
- **Webhook Integration**: Real-time updates from Stripe
- **Usage Limits**: Soft limits with overage billing

## Quick Start

### 1. Environment Setup

Add Stripe credentials to your `.env`:

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. Run Database Migration

```bash
cd backend
alembic upgrade head
```

### 3. Create Subscription Plans

```python
from app.services.billing import StripeService

stripe_service = StripeService(
    api_key="sk_test_...",
    webhook_secret="whsec_..."
)

# Create a plan
plan = await stripe_service.create_subscription_plan(
    db=db,
    name="Professional",
    description="For growing businesses",
    price_monthly=Decimal("99.00"),
    included_minutes=5000,
    included_calls=500,
    max_agents=5,
    max_phone_numbers=5,
    max_knowledge_bases=10,
)
```

### 4. Subscribe a Customer

```python
# Create Stripe customer
customer_id = await stripe_service.create_customer(
    email="user@example.com",
    name="John Doe",
    organization_id=org_id,
)

# Create subscription
subscription = await stripe_service.create_subscription(
    db=db,
    organization_id=org_id,
    plan_id=plan.id,
    stripe_customer_id=customer_id,
    trial_days=14,
)
```

## Architecture

### System Components

```
┌─────────────────┐
│  Frontend UI    │
│  (React/Next)   │
└────────┬────────┘
         │
         ├─────────────────────────────┐
         │                             │
┌────────▼────────┐          ┌─────────▼────────┐
│   Billing API   │          │   Usage Tracker  │
│   (FastAPI)     │          │   (Auto-track)   │
└────────┬────────┘          └─────────┬────────┘
         │                             │
         ├─────────────────────────────┤
         │                             │
┌────────▼────────┐          ┌─────────▼────────┐
│ Stripe Service  │◄────────►│   Database       │
│                 │          │   (PostgreSQL)   │
└────────┬────────┘          └──────────────────┘
         │
         │ Webhooks
         │
┌────────▼────────┐
│     Stripe      │
│   (Payment)     │
└─────────────────┘
```

### Data Flow

1. **Subscription Creation**: Frontend → API → Stripe Service → Stripe → Database
2. **Usage Recording**: Call End → Usage Tracker → Database
3. **Usage Reporting**: Cron Job → Stripe Service → Stripe API
4. **Invoice Creation**: Stripe → Webhook → Database
5. **Payment Failure**: Stripe → Webhook → Notification

## Database Models

### SubscriptionPlan

Defines available subscription tiers.

```python
{
    "id": "uuid",
    "name": "Professional",
    "price_monthly": 99.00,
    "included_minutes": 5000,
    "included_calls": 500,
    "max_agents": 5,
    "overage_rate_per_minute": 0.012,
    "overage_rate_per_call": 0.04,
    "features": {
        "advanced_analytics": true,
        "priority_support": true
    }
}
```

### Subscription

Active customer subscriptions.

```python
{
    "id": "uuid",
    "organization_id": "uuid",
    "plan_id": "uuid",
    "stripe_subscription_id": "sub_...",
    "status": "active",  # active, past_due, canceled, trialing
    "current_period_minutes": 3245,
    "current_period_calls": 289,
    "current_period_start": "2024-01-01T00:00:00Z",
    "current_period_end": "2024-02-01T00:00:00Z"
}
```

### UsageRecord

Tracks metered usage for billing.

```python
{
    "id": "uuid",
    "subscription_id": "uuid",
    "usage_type": "minutes",  # minutes, calls, sms
    "quantity": 100,
    "unit_price": 0.012,
    "total_amount": 1.20,
    "resource_type": "call",
    "resource_id": "uuid",
    "reported_to_stripe": false
}
```

### Invoice

Stripe invoices synced to database.

```python
{
    "id": "uuid",
    "stripe_invoice_id": "in_...",
    "invoice_number": "INV-2024-001",
    "status": "paid",
    "total": 99.00,
    "invoice_pdf": "https://...",
    "paid_at": "2024-01-05T00:00:00Z"
}
```

### PaymentFailure

Failed payment attempts for tracking and resolution.

```python
{
    "id": "uuid",
    "invoice_id": "uuid",
    "failure_code": "card_declined",
    "failure_message": "Your card was declined",
    "resolved": false,
    "customer_notified": true
}
```

## Stripe Service

### Key Methods

#### Subscription Management

```python
# Create subscription
subscription = await stripe_service.create_subscription(
    db=db,
    organization_id=org_id,
    plan_id=plan_id,
    stripe_customer_id=customer_id,
    trial_days=14
)

# Cancel subscription
await stripe_service.cancel_subscription(
    db=db,
    subscription_id=sub_id,
    immediate=False  # Cancel at period end
)

# Update plan
await stripe_service.update_subscription_plan(
    db=db,
    subscription_id=sub_id,
    new_plan_id=new_plan_id,
    prorate=True
)
```

#### Usage Tracking

```python
# Record usage
usage = await stripe_service.record_usage(
    db=db,
    subscription_id=sub_id,
    usage_type="minutes",
    quantity=100,
    resource_type="call",
    resource_id=call_id
)

# Report to Stripe
count = await stripe_service.report_usage_to_stripe(
    db=db,
    subscription_id=sub_id
)

# Check limits
limits = await stripe_service.check_usage_limits(
    db=db,
    organization_id=org_id
)
```

#### Invoice Management

```python
# Sync invoice from Stripe
invoice = await stripe_service.sync_invoice(
    db=db,
    stripe_invoice_id="in_..."
)

# Handle payment failure
await stripe_service.handle_payment_failure(
    db=db,
    invoice_id=invoice_id,
    failure_code="card_declined",
    failure_message="Your card was declined"
)
```

## Usage Tracking

### Automatic Call Tracking

Usage is automatically tracked when calls complete:

```python
# In CallSession.cleanup() (call_manager.py)
if self.state == CallState.COMPLETED and self.organization_id:
    await UsageTracker.record_call_usage(
        db=self.db,
        call_id=self.call_id,
        organization_id=self.organization_id,
    )
```

### How It Works

1. **Call Ends**: CallSession cleanup is triggered
2. **Calculate Usage**: Minutes = ceil(duration / 60)
3. **Check Limits**: Compare with plan included limits
4. **Record Usage**: Create UsageRecord entries
5. **Update Counters**: Increment subscription counters
6. **Calculate Overage**: Bill only for usage beyond limits

### Usage Example

```
Plan: 5000 minutes included
Used: 5123 minutes
Overage: 123 minutes
Charge: 123 × $0.012 = $1.48
```

### Manual Usage Recording

```python
# Record SMS usage
await UsageTracker.record_sms_usage(
    db=db,
    organization_id=org_id,
    sms_count=5
)

# Check if within limits
status = await UsageTracker.check_usage_limit(
    db=db,
    organization_id=org_id,
    usage_type="minutes"
)
# Returns: {has_subscription: true, within_limit: true, overage: 123}
```

## API Endpoints

### GET /api/v1/billing/plans

List all available subscription plans.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Professional",
    "price_monthly": 99.00,
    "included_minutes": 5000,
    "included_calls": 500,
    "max_agents": 5,
    "features": {...}
  }
]
```

### GET /api/v1/billing/subscription

Get current subscription.

**Response:**
```json
{
  "id": "uuid",
  "plan_name": "Professional",
  "status": "active",
  "current_period_start": "2024-01-01T00:00:00Z",
  "current_period_end": "2024-02-01T00:00:00Z",
  "current_period_minutes": 3245,
  "current_period_calls": 289
}
```

### POST /api/v1/billing/subscription

Create new subscription.

**Request:**
```json
{
  "plan_id": "uuid",
  "payment_method_id": "pm_...",
  "trial_days": 14
}
```

### PUT /api/v1/billing/subscription

Update subscription plan.

**Request:**
```json
{
  "plan_id": "uuid",
  "prorate": true
}
```

### DELETE /api/v1/billing/subscription

Cancel subscription.

**Query Params:**
- `immediate`: boolean (default: false)

### GET /api/v1/billing/usage

Get current period usage.

**Response:**
```json
{
  "minutes_used": 3245,
  "minutes_included": 5000,
  "minutes_overage": 0,
  "calls_used": 289,
  "calls_included": 500,
  "calls_overage": 0,
  "estimated_overage_cost": 0.00
}
```

### GET /api/v1/billing/usage/limits

Check usage limits.

**Response:**
```json
{
  "has_active_subscription": true,
  "within_limits": true,
  "minutes_limit_reached": false,
  "calls_limit_reached": false
}
```

### GET /api/v1/billing/invoices

List invoices.

**Query Params:**
- `limit`: integer (default: 10)

**Response:**
```json
[
  {
    "id": "uuid",
    "invoice_number": "INV-2024-001",
    "status": "paid",
    "total": 99.00,
    "paid_at": "2024-01-05T00:00:00Z",
    "invoice_pdf": "https://..."
  }
]
```

### POST /api/v1/billing/webhooks/stripe

Handle Stripe webhooks.

**Headers:**
- `stripe-signature`: Webhook signature

## Webhooks

### Setup Webhook Endpoint

1. Configure in Stripe Dashboard: `https://yourdomain.com/api/v1/billing/webhooks/stripe`
2. Select events to listen for
3. Copy webhook secret to `.env`

### Supported Events

- `invoice.paid`: Invoice successfully paid
- `invoice.payment_failed`: Payment failed
- `customer.subscription.updated`: Subscription changed
- `customer.subscription.deleted`: Subscription canceled

### Event Handlers

```python
async def handle_webhook_event(self, db: AsyncSession, event: Dict[str, Any]):
    event_type = event["type"]

    if event_type == "invoice.paid":
        await self.sync_invoice(db, event["data"]["object"]["id"])

    elif event_type == "invoice.payment_failed":
        invoice = await self.sync_invoice(db, event["data"]["object"]["id"])
        await self.handle_payment_failure(db, invoice.id, ...)

    # ... more handlers
```

## Frontend Integration

### Billing Page

Located at: `frontend/src/app/(dashboard)/settings/billing/page.tsx`

**Features:**
- Current plan display
- Usage meters with progress bars
- Plan comparison and upgrade/downgrade
- Invoice history with download links
- Payment method management

**Key Components:**

```typescript
// Current subscription
const subscription = await fetch('/api/v1/billing/subscription');

// Current usage
const usage = await fetch('/api/v1/billing/usage');

// Available plans
const plans = await fetch('/api/v1/billing/plans');

// Create subscription
await fetch('/api/v1/billing/subscription', {
  method: 'POST',
  body: JSON.stringify({
    plan_id: selectedPlan.id,
    payment_method_id: paymentMethod.id,
    trial_days: 14
  })
});
```

## Testing

### Test Stripe Integration

Use Stripe test mode credentials:

```bash
STRIPE_SECRET_KEY=sk_test_...
```

### Test Cards

```
Success: 4242 4242 4242 4242
Decline: 4000 0000 0000 0002
Insufficient funds: 4000 0000 0000 9995
```

### Test Webhooks Locally

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe

# Trigger test events
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
```

### Unit Tests

```python
# Test usage tracking
async def test_record_call_usage():
    usage = await UsageTracker.record_call_usage(
        db=db,
        call_id=call_id,
        organization_id=org_id,
    )
    assert usage is not None
    assert usage.usage_type == "minutes"

# Test subscription creation
async def test_create_subscription():
    subscription = await stripe_service.create_subscription(
        db=db,
        organization_id=org_id,
        plan_id=plan_id,
        stripe_customer_id=customer_id,
    )
    assert subscription.status == "active"
```

## Best Practices

### 1. Usage Tracking

- **Always track usage**: Don't skip usage recording
- **Handle errors gracefully**: Log failures but don't block calls
- **Background processing**: Use async for non-critical operations
- **Idempotency**: Handle duplicate usage records

### 2. Webhook Handling

- **Verify signatures**: Always verify Stripe webhook signatures
- **Idempotent processing**: Handle duplicate webhook deliveries
- **Async processing**: Process webhooks quickly, defer heavy work
- **Error handling**: Return 200 even if processing fails initially

### 3. Payment Failures

- **Notify customers**: Send email when payment fails
- **Retry logic**: Let Stripe handle automatic retries
- **Grace periods**: Don't immediately disable service
- **Clear communication**: Explain why payment failed

### 4. Security

- **Secure API keys**: Never commit Stripe keys to git
- **Use environment variables**: Store credentials in `.env`
- **Webhook secrets**: Verify all webhook requests
- **User permissions**: Restrict billing access to admins

### 5. Performance

- **Cache plan data**: Plans rarely change
- **Batch usage reporting**: Report to Stripe in batches
- **Index queries**: Ensure proper database indexes
- **Async operations**: Don't block user requests

## Troubleshooting

### Usage Not Recording

**Problem**: Calls complete but usage not recorded

**Solutions**:
1. Check if organization has active subscription
2. Verify organization_id is set in CallSession
3. Check logs for UsageTracker errors
4. Ensure call has duration set

### Webhook Failures

**Problem**: Webhooks returning 400/500 errors

**Solutions**:
1. Verify webhook secret is correct
2. Check signature verification
3. Ensure database is accessible
4. Review webhook event logs in Stripe Dashboard

### Invoice Not Syncing

**Problem**: Invoices created in Stripe but not in database

**Solutions**:
1. Check webhook configuration
2. Manually trigger sync: `sync_invoice(invoice_id)`
3. Verify subscription exists in database
4. Check for database errors

### Overage Not Charging

**Problem**: Usage exceeds limits but no charges

**Solutions**:
1. Ensure usage is reported to Stripe: `report_usage_to_stripe()`
2. Check if subscription has metered billing configured
3. Verify overage rates are set in plan
4. Review Stripe subscription item configuration

## Support

For issues or questions:

1. Check logs: `backend/logs/app.log`
2. Review Stripe Dashboard: Events and Logs
3. Consult Stripe API docs: https://stripe.com/docs/api
4. Contact support: support@voicecon.ai

---

**Last Updated**: January 2024
**Version**: 1.0.0

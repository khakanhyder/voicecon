# Analytics Scheduler Guide

## Overview

The Analytics Scheduler is a background service that runs periodic jobs to aggregate and maintain analytics data in the Voicecon platform. It ensures that metrics are pre-aggregated for optimal query performance and that real-time data stays current.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Analytics Scheduler                        │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │ │
│  │  │ Real-time    │  │   Daily      │  │   Cache     │  │ │
│  │  │ Metrics Job  │  │ Aggregation  │  │  Cleanup    │  │ │
│  │  │ (1 minute)   │  │   (1 AM)     │  │  (6 hours)  │  │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  │ │
│  │         │                 │                  │         │ │
│  └─────────┼─────────────────┼──────────────────┼─────────┘ │
│            │                 │                  │           │
└────────────┼─────────────────┼──────────────────┼───────────┘
             ↓                 ↓                  ↓
   ┌─────────────────────────────────────────────────────┐
   │              Analytics Service                       │
   │  ┌────────────┐ ┌────────────┐ ┌─────────────────┐ │
   │  │ Update     │ │ Aggregate  │ │  Cleanup        │ │
   │  │ Realtime   │ │ Metrics    │ │  Expired Cache  │ │
   │  └────────────┘ └────────────┘ └─────────────────┘ │
   └────────────────────────┬────────────────────────────┘
                            ↓
                    ┌──────────────┐
                    │   Database   │
                    └──────────────┘
```

## Scheduled Jobs

### 1. Real-time Metrics Job

**Frequency:** Every 1 minute
**Purpose:** Keep real-time metrics current

**What it does:**
- Updates `realtime_metrics` table for all active organizations
- Counts active calls (currently in progress)
- Counts calls in last hour and last 5 minutes
- Calculates current error rate
- Determines system health status (healthy, degraded, down)
- Updates active agents and integrations count

**Implementation:**
```python
async def _run_realtime_metrics_job(self):
    while self.is_running:
        await self._update_all_realtime_metrics()
        await asyncio.sleep(60)  # Wait 1 minute
```

**Database Impact:**
- Updates one row per organization every minute
- Very low overhead (SELECT + UPDATE)
- No historical data accumulation

### 2. Daily Aggregation Job

**Frequency:** Daily at 1:00 AM
**Purpose:** Aggregate previous day's data

**What it does:**
1. Aggregates call metrics for yesterday
2. Aggregates agent metrics for yesterday
3. Aggregates integration metrics for yesterday
4. Generates daily summary with trends

**Implementation:**
```python
async def _run_daily_aggregation_job(self):
    while self.is_running:
        # Calculate next 1 AM
        next_run = now.replace(hour=1, minute=0, second=0, microsecond=0)
        if now.hour >= 1:
            next_run += timedelta(days=1)

        # Wait until 1 AM
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # Run aggregation
        await self._run_daily_aggregation()
```

**Data Aggregated:**
- **Call Metrics:** Total calls, duration, success rate, costs
- **Agent Metrics:** Performance, sentiment, function calls, token usage
- **Integration Metrics:** Executions, API calls, health scores
- **Daily Summary:** Organization-wide overview with trends

**Database Impact:**
- Processes all raw data from previous day
- Creates aggregated rows for quick access
- Runs during low-traffic hours (1 AM)

### 3. Cache Cleanup Job

**Frequency:** Every 6 hours
**Purpose:** Remove expired cache entries

**What it does:**
- Deletes rows from `metrics_cache` where `expires_at < now()`
- Prevents cache table from growing indefinitely
- Keeps cache efficient

**Implementation:**
```python
async def _run_cache_cleanup_job(self):
    while self.is_running:
        await self._cleanup_expired_cache()
        await asyncio.sleep(6 * 3600)  # Wait 6 hours
```

**Database Impact:**
- DELETE query with WHERE clause
- Removes only expired entries
- Very fast operation

## Lifecycle Management

### Startup

The scheduler starts automatically when the FastAPI application starts:

```python
# In app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await start_scheduler()
    logger.info("Analytics scheduler started")

    yield

    # Shutdown
    await stop_scheduler()
    logger.info("Analytics scheduler stopped")
```

**Startup Process:**
1. Creates global `AnalyticsScheduler` instance
2. Spawns three asyncio tasks (one for each job)
3. Each task runs in an infinite loop
4. Jobs handle their own timing and retry logic

### Shutdown

Clean shutdown ensures no data loss:

```python
async def stop(self):
    self.is_running = False

    # Cancel all tasks
    for task in self.tasks:
        task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(*self.tasks, return_exceptions=True)
```

**Shutdown Process:**
1. Sets `is_running = False` to signal all jobs to stop
2. Cancels all running asyncio tasks
3. Waits for tasks to finish current operation
4. Ensures no jobs are left running

## Error Handling

### Job-Level Error Handling

Each job catches and logs its own errors:

```python
try:
    await self._update_all_realtime_metrics()
except asyncio.CancelledError:
    logger.info("Real-time metrics job cancelled")
    break
except Exception as e:
    logger.error(f"Error in real-time metrics job: {e}", exc_info=True)
    await asyncio.sleep(60)  # Wait before retry
```

**Features:**
- Jobs don't crash the entire scheduler on error
- Errors are logged with full stack trace
- Jobs automatically retry after delay
- Cancellation is handled gracefully

### Organization-Level Error Handling

When processing multiple organizations, errors in one don't affect others:

```python
for org in organizations:
    try:
        await analytics_service.aggregate_call_metrics(
            organization_id=org.id,
            # ... parameters
        )
    except Exception as e:
        logger.error(
            f"Failed daily aggregation for organization {org.id}: {e}",
            exc_info=True
        )
        # Continue with next organization
```

**Benefits:**
- One organization's data issues don't block others
- Each organization's aggregation is independent
- Detailed error logs per organization

## Configuration

### Job Timing

Job timing can be customized by modifying the scheduler:

```python
# Real-time metrics interval (default: 60 seconds)
await asyncio.sleep(60)

# Daily aggregation time (default: 1 AM)
next_run = now.replace(hour=1, minute=0, second=0, microsecond=0)

# Cache cleanup interval (default: 6 hours)
await asyncio.sleep(6 * 3600)
```

**Recommendations:**
- **Real-time metrics:** 30-120 seconds (balance freshness vs. load)
- **Daily aggregation:** 1-4 AM (low traffic hours)
- **Cache cleanup:** 4-12 hours (depends on cache usage)

### Database Connection

The scheduler uses async database sessions:

```python
async with get_db_session() as db:
    analytics_service = AnalyticsService(db)
    # ... perform operations
    await db.commit()
```

**Features:**
- Connection pooling managed by SQLAlchemy
- Each job gets its own session
- Automatic session cleanup
- Commits only on success

## Monitoring

### Logging

The scheduler provides comprehensive logging:

```python
logger.info("Analytics scheduler started")
logger.info(f"Updated real-time metrics for {len(organizations)} organizations")
logger.info(f"Completed daily aggregation for organization {org.id}")
logger.error(f"Failed to update real-time metrics: {e}", exc_info=True)
```

**Log Levels:**
- **INFO:** Normal operation, job completion
- **DEBUG:** Detailed per-organization operations
- **ERROR:** Failures, retries, issues
- **WARNING:** Configuration issues, missing data

### Metrics to Monitor

Track these metrics in production:

1. **Job Execution Time**
   - Real-time update should be < 10 seconds
   - Daily aggregation depends on data volume
   - Cache cleanup should be < 5 seconds

2. **Error Rate**
   - Should be 0% under normal conditions
   - Spikes indicate data or connection issues

3. **Organizations Processed**
   - Should match active organization count
   - Gaps indicate processing failures

4. **Database Load**
   - Monitor query times during aggregation
   - Watch connection pool usage
   - Check for slow queries

## Performance Optimization

### Database Queries

All jobs use optimized queries:

```python
# Single query to get all active organizations
result = await db.execute(
    select(Organization).where(Organization.is_active == True)
)
organizations = result.scalars().all()
```

**Optimizations:**
- Use indexes on frequently queried fields
- Batch operations when possible
- Minimize round-trips to database

### Concurrent Processing

Process organizations in parallel when appropriate:

```python
# For CPU-bound aggregations, use asyncio.gather
await asyncio.gather(*[
    analytics_service.aggregate_call_metrics(org.id, ...)
    for org in organizations
])
```

**Considerations:**
- Balance parallelism with database load
- Limit concurrent connections to database
- Consider using background workers for very large datasets

### Memory Management

Jobs don't load all data into memory:

```python
# Process date ranges incrementally
while current_date <= end_date:
    metric = await self._aggregate_call_metrics_for_day(...)
    if metric:
        metrics.append(metric)
    current_date += timedelta(days=1)
```

**Best Practices:**
- Stream results when possible
- Clear temporary data after processing
- Use database aggregation functions

## Troubleshooting

### Scheduler Won't Start

**Symptoms:**
- No scheduler log messages on startup
- Jobs don't run

**Possible Causes:**
1. Import error in scheduler module
2. Database connection failure
3. Missing dependencies

**Solution:**
```bash
# Check logs for import errors
tail -f app.log | grep scheduler

# Test database connection
python -m app.database

# Verify dependencies
pip install -r requirements.txt
```

### Jobs Not Running

**Symptoms:**
- Scheduler starts but no job execution
- Missing log messages for job runs

**Possible Causes:**
1. `is_running` flag not set
2. Infinite sleep due to timing bug
3. Uncaught exception in job

**Solution:**
```python
# Add debug logging
logger.info(f"Job running: {self.is_running}")
logger.info(f"Next run in {wait_seconds} seconds")
```

### High Database Load

**Symptoms:**
- Slow queries during aggregation
- Database connection pool exhaustion
- Timeouts

**Possible Causes:**
1. Missing database indexes
2. Too many concurrent operations
3. Large data volume

**Solution:**
```sql
-- Add missing indexes
CREATE INDEX idx_calls_org_created ON calls(organization_id, created_at);

-- Check slow queries
SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

### Memory Leaks

**Symptoms:**
- Increasing memory usage over time
- Out of memory errors

**Possible Causes:**
1. Database sessions not closed
2. Large result sets kept in memory
3. Circular references

**Solution:**
```python
# Ensure sessions are closed
async with get_db_session() as db:
    # Use session
    pass  # Automatically closed

# Clear large lists
metrics.clear()

# Use generators for large datasets
def iter_results():
    for item in large_list:
        yield item
        del item
```

## Best Practices

### 1. Idempotent Jobs

Jobs should be safe to run multiple times:

```python
# Use UPSERT instead of INSERT
stmt = insert(CallMetrics).values(...)
stmt = stmt.on_conflict_do_update(
    index_elements=['organization_id', 'metric_date'],
    set_=dict(total_calls=stmt.excluded.total_calls)
)
```

### 2. Graceful Degradation

Handle missing or incomplete data gracefully:

```python
# Skip organizations with no data
if not result.scalar():
    logger.debug(f"No data for organization {org.id}, skipping")
    continue
```

### 3. Atomic Operations

Use transactions for related operations:

```python
async with db.begin():
    # All operations succeed or fail together
    await analytics_service.aggregate_call_metrics(...)
    await analytics_service.aggregate_agent_metrics(...)
    await analytics_service.generate_daily_summary(...)
```

### 4. Monitoring and Alerting

Set up alerts for critical failures:

```python
# Send alert on repeated failures
failure_count = 0
if failure_count > 3:
    await send_alert(f"Analytics job failing: {org.id}")
```

## Production Deployment

### Environment Variables

Configure scheduler behavior via environment:

```bash
# .env file
ANALYTICS_REALTIME_INTERVAL=60  # seconds
ANALYTICS_AGGREGATION_HOUR=1    # 1 AM
ANALYTICS_CACHE_CLEANUP_HOURS=6
```

### Health Checks

Add scheduler health to API health check:

```python
@app.get("/health")
async def health_check():
    scheduler = await get_scheduler()
    return {
        "status": "healthy",
        "scheduler_running": scheduler.is_running,
        "jobs_count": len(scheduler.tasks),
    }
```

### Scaling Considerations

For multi-instance deployments:

1. **Use Leader Election:**
   - Only one instance runs scheduler
   - Others remain in standby
   - Automatic failover on leader failure

2. **Use External Scheduler:**
   - Kubernetes CronJobs
   - AWS EventBridge
   - Apache Airflow

3. **Distributed Task Queue:**
   - Celery
   - RQ (Redis Queue)
   - AWS SQS

## Examples

### Manual Trigger

Trigger aggregation manually via API:

```python
@router.post("/analytics/aggregate")
async def trigger_aggregation(
    date: date,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger aggregation for a specific date."""
    analytics_service = AnalyticsService(db)

    await analytics_service.aggregate_call_metrics(
        organization_id=current_user.organization_id,
        start_date=date,
        end_date=date,
    )

    return {"status": "success", "date": date}
```

### Testing Jobs

Test jobs in isolation:

```python
import pytest
from app.services.analytics.scheduler import AnalyticsScheduler

@pytest.mark.asyncio
async def test_realtime_metrics_job():
    scheduler = AnalyticsScheduler()

    # Run job once
    await scheduler._update_all_realtime_metrics()

    # Verify results
    # ... assertions
```

### Custom Job

Add custom analytics job:

```python
async def _run_weekly_report_job(self):
    """Generate weekly reports every Monday at 6 AM."""
    while self.is_running:
        now = datetime.now()

        # Calculate next Monday 6 AM
        days_until_monday = (7 - now.weekday()) % 7
        next_run = (now + timedelta(days=days_until_monday)).replace(
            hour=6, minute=0, second=0, microsecond=0
        )

        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        # Generate weekly report
        await self._generate_weekly_reports()
```

## Summary

The Analytics Scheduler provides:

✅ **Automated Data Aggregation** - Daily metrics pre-aggregation
✅ **Real-time Metrics** - Up-to-date system status
✅ **Performance Optimization** - Fast queries via pre-aggregated data
✅ **Resource Management** - Automatic cache cleanup
✅ **Error Resilience** - Per-organization error handling
✅ **Production Ready** - Comprehensive logging and monitoring

For more information on the analytics system, see [ANALYTICS_SYSTEM_GUIDE.md](ANALYTICS_SYSTEM_GUIDE.md).

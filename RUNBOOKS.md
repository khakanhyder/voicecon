# Voicecon Operational Runbooks

**Standard operating procedures for common incidents and tasks**

Version 1.0.0 | Last Updated: December 19, 2025

---

## Table of Contents

### Incident Response
1. [High Error Rate](#runbook-1-high-error-rate)
2. [Database Connection Issues](#runbook-2-database-connection-issues)
3. [Redis Connection Failed](#runbook-3-redis-connection-failed)
4. [High API Latency](#runbook-4-high-api-latency)
5. [Service Degradation](#runbook-5-service-degradation)
6. [Call Quality Issues](#runbook-6-call-quality-issues)

### Operational Tasks
7. [Deploy New Version](#runbook-7-deploy-new-version)
8. [Database Migration](#runbook-8-database-migration)
9. [Scale Services](#runbook-9-scale-services)
10. [Backup and Restore](#runbook-10-backup-and-restore)
11. [Security Incident Response](#runbook-11-security-incident-response)

### Maintenance
12. [Rotate Secrets](#runbook-12-rotate-secrets)
13. [Update Dependencies](#runbook-13-update-dependencies)
14. [Clean Up Old Data](#runbook-14-clean-up-old-data)

---

## Runbook 1: High Error Rate

### Symptoms
- Error rate > 1% in monitoring dashboard
- Multiple 500 errors in logs
- User reports of failures
- Sentry alert: "Error rate spike"

### Severity
**Critical** - Immediate response required

### Detection
- **DataDog Alert**: `voicecon.errors.rate > 1%`
- **Sentry Alert**: Error rate threshold exceeded
- **PagerDuty**: Incident created automatically

### Investigation Steps

#### Step 1: Identify Scope (2 minutes)

1. Check error dashboard:
```bash
# Access DataDog dashboard
https://app.datadoghq.com/dashboard/voicecon-errors

# Or check Grafana
https://grafana.voicecon.com/d/errors
```

2. Determine affected endpoints:
```bash
# View recent errors
kubectl logs -l app=backend --tail=100 -n voicecon | grep ERROR

# Check error distribution
curl -H "Authorization: Bearer $DATADOG_API_KEY" \
  "https://api.datadoghq.com/api/v1/query?query=sum:voicecon.errors{*}by{endpoint}"
```

3. Check if errors are widespread or localized:
   - All endpoints → Infrastructure issue
   - Specific endpoint → Application bug
   - Specific integration → External service issue

#### Step 2: Check Dependencies (3 minutes)

1. Verify database health:
```bash
# Check database connection
curl https://api.voicecon.com/health/detailed | jq '.checks.database'

# Check database load
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
SELECT
  state,
  count(*)
FROM pg_stat_activity
GROUP BY state;
"
```

2. Verify Redis:
```bash
# Check Redis status
kubectl exec -it redis-0 -n voicecon -- redis-cli INFO | grep -E "(connected_clients|used_memory_human|uptime_in_seconds)"
```

3. Check external services:
```bash
# Check LLM service
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models

# Check Twilio status
curl https://status.twilio.com/api/v2/status.json
```

#### Step 3: Review Recent Changes (2 minutes)

1. Check recent deployments:
```bash
# View recent deployments
kubectl rollout history deployment/backend -n voicecon

# View recent commits
git log --oneline -10
```

2. Check if errors correlate with deployment time

#### Step 4: Analyze Error Patterns (3 minutes)

1. Group errors by type:
```bash
# View error distribution in Sentry
# Go to: https://sentry.io/organizations/voicecon/issues/

# Or check logs
kubectl logs -l app=backend -n voicecon --tail=500 | \
  grep ERROR | \
  awk '{print $5}' | \
  sort | uniq -c | sort -rn
```

2. Identify most common error:
   - Database timeouts
   - External API failures
   - Application exceptions
   - Memory errors

### Resolution

#### If Database Issue:

```bash
# Scale up database
# For RDS:
aws rds modify-db-instance \
  --db-instance-identifier voicecon-prod \
  --db-instance-class db.t3.xlarge \
  --apply-immediately

# For self-hosted:
kubectl scale statefulset postgres --replicas=2 -n voicecon
```

#### If External Service Issue:

```bash
# Enable circuit breaker
kubectl set env deployment/backend -n voicecon \
  CIRCUIT_BREAKER_ENABLED=true

# Or rollback problematic integration
kubectl exec -it deployment/backend -n voicecon -- \
  python -c "from app.services.integrations import disable_integration; \
             disable_integration('salesforce')"
```

#### If Application Bug:

```bash
# Rollback to previous version
kubectl rollout undo deployment/backend -n voicecon

# Verify rollback
kubectl rollout status deployment/backend -n voicecon
```

#### If Infrastructure Issue:

```bash
# Scale up pods
kubectl scale deployment backend --replicas=10 -n voicecon

# Or restart all pods
kubectl rollout restart deployment/backend -n voicecon
```

### Verification

1. Check error rate returned to normal:
```bash
# Wait 5 minutes, then check
curl https://api.voicecon.com/health/detailed | jq '.checks'
```

2. Verify in monitoring:
   - Error rate < 0.1%
   - Response times normal
   - No alerts firing

### Post-Incident

1. **Document in incident log**:
   - Root cause
   - Timeline
   - Resolution steps
   - Lessons learned

2. **Create follow-up tasks**:
   - Fix underlying bug
   - Improve monitoring
   - Update runbook

3. **Notify stakeholders**:
```bash
# Send status update to Slack
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "✅ Incident resolved: High error rate",
    "attachments": [{
      "color": "good",
      "fields": [
        {"title": "Duration", "value": "15 minutes"},
        {"title": "Root Cause", "value": "Database connection pool exhausted"},
        {"title": "Resolution", "value": "Increased pool size and restarted services"}
      ]
    }]
  }'
```

---

## Runbook 2: Database Connection Issues

### Symptoms
- "Cannot connect to database" errors
- Timeouts on database queries
- Health check failures
- Application unable to start

### Severity
**Critical** - Service completely down

### Investigation Steps

#### Step 1: Check Database Status

```bash
# Check if database pod is running
kubectl get pods -l app=postgres -n voicecon

# Check database logs
kubectl logs -l app=postgres --tail=100 -n voicecon

# For RDS:
aws rds describe-db-instances \
  --db-instance-identifier voicecon-prod \
  --query 'DBInstances[0].DBInstanceStatus'
```

#### Step 2: Test Connectivity

```bash
# From backend pod
kubectl exec -it deployment/backend -n voicecon -- \
  psql $DATABASE_URL -c "SELECT 1"

# Check connection pool
kubectl exec -it deployment/backend -n voicecon -- \
  python -c "
from app.core.database import engine
pool = engine.pool
print(f'Size: {pool.size()}')
print(f'Checked out: {pool.checkedout()}')
print(f'Overflow: {pool.overflow()}')
"
```

#### Step 3: Check Database Load

```bash
# Check active connections
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
SELECT
  count(*) as total_connections,
  count(*) FILTER (WHERE state = 'active') as active,
  count(*) FILTER (WHERE state = 'idle') as idle,
  count(*) FILTER (WHERE wait_event IS NOT NULL) as waiting
FROM pg_stat_activity;
"

# Check long-running queries
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - pg_stat_activity.query_start > interval '1 minute'
ORDER BY duration DESC;
"
```

### Resolution

#### If Database is Down:

```bash
# Restart database pod
kubectl delete pod postgres-0 -n voicecon

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/postgres-0 -n voicecon --timeout=300s

# For RDS:
aws rds reboot-db-instance \
  --db-instance-identifier voicecon-prod
```

#### If Connection Pool Exhausted:

```bash
# Increase pool size
kubectl set env deployment/backend -n voicecon \
  DATABASE_POOL_SIZE=50 \
  DATABASE_MAX_OVERFLOW=20

# Restart backend to apply changes
kubectl rollout restart deployment/backend -n voicecon
```

#### If Too Many Connections:

```bash
# Kill idle connections
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
  AND state_change < current_timestamp - INTERVAL '5 minutes';
"

# Increase max_connections (requires restart)
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
ALTER SYSTEM SET max_connections = 200;
"

kubectl delete pod postgres-0 -n voicecon
```

#### If Disk Full:

```bash
# Check disk usage
kubectl exec -it postgres-0 -n voicecon -- df -h

# Expand PVC (if supported by storage class)
kubectl patch pvc postgres-pvc -n voicecon \
  -p '{"spec":{"resources":{"requests":{"storage":"200Gi"}}}}'

# Or clean up old data
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
VACUUM FULL;
"
```

### Verification

```bash
# Test connection
curl https://api.voicecon.com/health/ready | jq '.checks.database'

# Verify application is healthy
kubectl get pods -l app=backend -n voicecon
```

---

## Runbook 3: Redis Connection Failed

### Symptoms
- "Cannot connect to Redis" errors
- Session/cache failures
- Rate limiting not working
- Application degraded performance

### Severity
**High** - Service degraded but functional

### Investigation Steps

```bash
# Check Redis pod status
kubectl get pods -l app=redis -n voicecon

# Check Redis logs
kubectl logs -l app=redis --tail=100 -n voicecon

# Test connectivity
kubectl exec -it deployment/backend -n voicecon -- \
  redis-cli -u $REDIS_URL ping
```

### Resolution

#### If Redis is Down:

```bash
# Restart Redis
kubectl delete pod redis-0 -n voicecon

# Verify it's running
kubectl wait --for=condition=ready pod/redis-0 -n voicecon --timeout=60s
```

#### If Out of Memory:

```bash
# Check memory usage
kubectl exec -it redis-0 -n voicecon -- \
  redis-cli INFO memory

# Clear cache (if safe)
kubectl exec -it redis-0 -n voicecon -- \
  redis-cli FLUSHDB

# Or scale up Redis
kubectl set env deployment/redis -n voicecon \
  REDIS_MAX_MEMORY=2gb
```

#### If Connection Limit Reached:

```bash
# Check connections
kubectl exec -it redis-0 -n voicecon -- \
  redis-cli INFO clients

# Increase max clients
kubectl exec -it redis-0 -n voicecon -- \
  redis-cli CONFIG SET maxclients 10000
```

---

## Runbook 7: Deploy New Version

### Prerequisites
- All tests passing
- Code reviewed and approved
- Database migrations prepared (if needed)
- Rollback plan ready

### Pre-Deployment Checklist

```bash
# 1. Verify current version is healthy
kubectl get pods -n voicecon
curl https://api.voicecon.com/health/detailed

# 2. Check recent metrics
# - Error rate < 0.1%
# - Response time < 500ms p95
# - No active incidents

# 3. Announce deployment
curl -X POST $SLACK_WEBHOOK_URL \
  -d '{"text":"🚀 Starting deployment of v1.2.0"}'
```

### Deployment Steps

#### Step 1: Deploy Backend

```bash
# Tag new version
export NEW_VERSION="1.2.0"
git tag -a v$NEW_VERSION -m "Release v$NEW_VERSION"
git push origin v$NEW_VERSION

# Build and push image (done by CI/CD)
# Or manually:
cd backend
docker build -t $ECR_REGISTRY/voicecon-backend:$NEW_VERSION .
docker push $ECR_REGISTRY/voicecon-backend:$NEW_VERSION

# Update deployment
kubectl set image deployment/backend \
  backend=$ECR_REGISTRY/voicecon-backend:$NEW_VERSION \
  -n voicecon

# Watch rollout
kubectl rollout status deployment/backend -n voicecon
```

#### Step 2: Run Database Migrations (if needed)

```bash
# Run migrations
kubectl exec -it deployment/backend -n voicecon -- \
  alembic upgrade head

# Verify migration
kubectl exec -it deployment/backend -n voicecon -- \
  alembic current
```

#### Step 3: Deploy Frontend

```bash
# Build and deploy
cd frontend
npm run build

# Deploy to Vercel
vercel --prod

# Or to Kubernetes
kubectl set image deployment/frontend \
  frontend=$ECR_REGISTRY/voicecon-frontend:$NEW_VERSION \
  -n voicecon
```

#### Step 4: Verify Deployment

```bash
# Check pod status
kubectl get pods -n voicecon

# Check health endpoints
curl https://api.voicecon.com/health/detailed | jq

# Smoke test critical endpoints
curl -X POST https://api.voicecon.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}'

# Check metrics
# - Error rate still low
# - Response times normal
# - No new errors in Sentry
```

### Rollback Procedure

If issues detected:

```bash
# Rollback backend
kubectl rollout undo deployment/backend -n voicecon

# Verify rollback
kubectl rollout status deployment/backend -n voicecon

# Rollback database (if migration was run)
kubectl exec -it deployment/backend -n voicecon -- \
  alembic downgrade -1

# Notify team
curl -X POST $SLACK_WEBHOOK_URL \
  -d '{"text":"⚠️ Deployment rolled back due to errors"}'
```

### Post-Deployment

```bash
# Monitor for 30 minutes
# Watch dashboards, error rates, user reports

# Mark deployment complete
curl -X POST $SLACK_WEBHOOK_URL \
  -d '{"text":"✅ Deployment v1.2.0 complete and stable"}'

# Update changelog
echo "## v1.2.0 - $(date +%Y-%m-%d)" >> CHANGELOG.md
echo "- New features..." >> CHANGELOG.md
```

---

## Runbook 10: Backup and Restore

### Database Backup

#### Manual Backup

```bash
# Create backup
kubectl exec -it postgres-0 -n voicecon -- \
  pg_dump -U voicecon voicecon > backup-$(date +%Y%m%d-%H%M%S).sql

# Compress backup
gzip backup-*.sql

# Upload to S3
aws s3 cp backup-*.sql.gz s3://voicecon-backups/database/
```

#### Automated Backup (CronJob)

Create `k8s/cronjob-backup.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: database-backup
  namespace: voicecon
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: voicecon-secrets
                  key: DATABASE_PASSWORD
            command:
            - /bin/sh
            - -c
            - |
              BACKUP_FILE="/tmp/backup-$(date +%Y%m%d-%H%M%S).sql"
              pg_dump -h postgres-service -U voicecon voicecon > $BACKUP_FILE
              gzip $BACKUP_FILE
              aws s3 cp ${BACKUP_FILE}.gz s3://voicecon-backups/database/
          restartPolicy: OnFailure
```

### Database Restore

```bash
# Download backup
aws s3 cp s3://voicecon-backups/database/backup-20250115-020000.sql.gz .

# Decompress
gunzip backup-20250115-020000.sql.gz

# Stop application
kubectl scale deployment backend --replicas=0 -n voicecon

# Drop and recreate database
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
DROP DATABASE voicecon;
CREATE DATABASE voicecon;
"

# Restore backup
kubectl exec -i postgres-0 -n voicecon -- \
  psql -U voicecon voicecon < backup-20250115-020000.sql

# Start application
kubectl scale deployment backend --replicas=5 -n voicecon

# Verify
curl https://api.voicecon.com/health/detailed
```

---

## Runbook 11: Security Incident Response

### Severity Levels

- **P1 Critical**: Data breach, system compromise
- **P2 High**: Unauthorized access attempt, vulnerability exploited
- **P3 Medium**: Suspicious activity, potential vulnerability
- **P4 Low**: Security warning, minor issue

### Incident Response Procedure

#### Step 1: Contain (Immediate)

```bash
# If active attack detected:

# 1. Block malicious IP
kubectl exec -it deployment/nginx -n voicecon -- \
  nginx -s reload -c /etc/nginx/block-ip.conf

# 2. Disable compromised accounts
kubectl exec -it deployment/backend -n voicecon -- \
  python -c "from app.services.auth import disable_user; disable_user('user@example.com')"

# 3. Rotate credentials
kubectl create secret generic voicecon-secrets-new \
  --from-literal=SECRET_KEY=$(openssl rand -hex 32) \
  -n voicecon

# 4. Enable enhanced logging
kubectl set env deployment/backend -n voicecon \
  LOG_LEVEL=debug \
  SECURITY_AUDIT_LOG=enabled
```

#### Step 2: Investigate

```bash
# Review access logs
kubectl logs -l app=backend -n voicecon --since=2h | \
  grep -E "(401|403|500)" > security-audit.log

# Check for unauthorized access
kubectl exec -it postgres-0 -n voicecon -- psql -U voicecon -c "
SELECT
  user_id,
  COUNT(*) as failed_attempts,
  MAX(created_at) as last_attempt
FROM auth_logs
WHERE success = false
  AND created_at > NOW() - INTERVAL '2 hours'
GROUP BY user_id
HAVING COUNT(*) > 5;
"

# Review Sentry events
# Check for unusual patterns in error logs
```

#### Step 3: Notify

```bash
# Notify security team
curl -X POST $SLACK_WEBHOOK_URL \
  -d '{
    "text":"🚨 SECURITY INCIDENT",
    "attachments":[{
      "color":"danger",
      "fields":[
        {"title":"Severity","value":"P1 - Critical"},
        {"title":"Type","value":"Unauthorized access"},
        {"title":"Status","value":"Contained, investigating"}
      ]
    }]
  }'

# If data breach, notify legal/compliance
```

#### Step 4: Remediate

```bash
# Patch vulnerability
# Update affected systems
# Reset all compromised credentials
# Review and update security policies
```

#### Step 5: Document

Create incident report with:
- Timeline of events
- Root cause analysis
- Impact assessment
- Remediation steps
- Lessons learned
- Action items to prevent recurrence

---

## Emergency Contacts

### On-Call Rotation
- **Primary**: Check PagerDuty schedule
- **Secondary**: Check PagerDuty schedule
- **Escalation**: CTO / VP Engineering

### External Contacts
- **AWS Support**: 1-800-XXX-XXXX (Premium Support)
- **Twilio Support**: support@twilio.com
- **OpenAI Support**: support@openai.com

### Internal Contacts
- **DevOps Lead**: devops@voicecon.com
- **Security Team**: security@voicecon.com
- **Engineering Manager**: engineering@voicecon.com

---

## Quick Reference

### Common Commands

```bash
# View pod logs
kubectl logs -f deployment/backend -n voicecon

# Execute command in pod
kubectl exec -it deployment/backend -n voicecon -- bash

# Scale deployment
kubectl scale deployment backend --replicas=10 -n voicecon

# Restart deployment
kubectl rollout restart deployment/backend -n voicecon

# View pod resource usage
kubectl top pods -n voicecon

# View events
kubectl get events -n voicecon --sort-by='.lastTimestamp'
```

### Health Check URLs

- **Basic**: https://api.voicecon.com/health
- **Ready**: https://api.voicecon.com/health/ready
- **Detailed**: https://api.voicecon.com/health/detailed

### Dashboard Links

- **Grafana**: https://grafana.voicecon.com
- **DataDog**: https://app.datadoghq.com/dashboard/voicecon
- **Sentry**: https://sentry.io/organizations/voicecon
- **PagerDuty**: https://voicecon.pagerduty.com

---

*Last Updated: December 19, 2025*
*Version: 1.0.0*

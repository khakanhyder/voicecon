# Voicecon Testing Guide

Comprehensive testing guide covering unit tests, integration tests, E2E tests, and load testing.

## Table of Contents

1. [Overview](#overview)
2. [Test Coverage Goals](#test-coverage-goals)
3. [Testing Infrastructure](#testing-infrastructure)
4. [Unit Tests](#unit-tests)
5. [Integration Tests](#integration-tests)
6. [E2E Tests](#e2e-tests)
7. [Load Testing](#load-testing)
8. [Running Tests](#running-tests)
9. [CI/CD Integration](#cicd-integration)
10. [Best Practices](#best-practices)

## Overview

Voicecon uses a comprehensive testing strategy to ensure code quality and reliability:

- **Unit Tests**: Test individual components in isolation (pytest)
- **Integration Tests**: Test API endpoints and database interactions (pytest)
- **E2E Tests**: Test complete user flows (Playwright)
- **Load Tests**: Test system performance under load (Locust)

**Current Coverage**: 80%+ (target achieved)

## Test Coverage Goals

### Overall Target: 80%+

#### By Component:
- **Core Services**: 90%+ (billing, agents, calls)
- **API Endpoints**: 85%+ (REST APIs)
- **Critical Flows**: 100% (auth, billing, calls)
- **Utils/Helpers**: 75%+

### Critical Flows to Test:

1. ✅ **Complete call flow** (inbound/outbound)
2. ✅ **Agent creation and deployment**
3. ✅ **Integration connection and workflow execution**
4. ✅ **Billing and subscriptions**
5. ✅ **Authentication and authorization**

## Testing Infrastructure

### Backend (Python/FastAPI)

**Framework**: pytest
**Tools**:
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-xdist` - Parallel execution
- `httpx` - HTTP client for testing
- `faker` - Test data generation

**Configuration**: [`backend/pytest.ini`](backend/pytest.ini)

### Frontend (Next.js/React)

**Framework**: Playwright
**Tools**:
- `@playwright/test` - E2E testing
- `playwright` - Browser automation
- Multiple browsers (Chrome, Firefox, Safari)

**Configuration**: [`frontend/playwright.config.ts`](frontend/playwright.config.ts)

### Load Testing

**Framework**: Locust
**Features**:
- Distributed load generation
- Real-time metrics
- Multiple user types
- Spike/stress testing

**Configuration**: [`backend/tests/load/locustfile.py`](backend/tests/load/locustfile.py)

## Unit Tests

Unit tests validate individual components in isolation.

### Location

```
backend/tests/unit/
├── test_billing_service.py
├── test_agent_service.py
├── test_call_service.py
├── test_auth_service.py
└── test_usage_tracker.py
```

### Example: Testing Billing Service

```python
import pytest
from app.services.billing import StripeService

@pytest.mark.unit
@pytest.mark.billing
class TestStripeService:
    """Test Stripe service functionality."""

    async def test_create_subscription_plan(
        self, db_session, stripe_service, monkeypatch
    ):
        """Test creating a subscription plan."""
        # Mock Stripe API
        mock_product = type('obj', (object,), {'id': 'prod_123'})()
        monkeypatch.setattr('stripe.Product.create', lambda **kwargs: mock_product)

        # Create plan
        plan = await stripe_service.create_subscription_plan(
            db=db_session,
            name="Professional",
            price_monthly=Decimal("99.00"),
            # ... other params
        )

        assert plan.name == "Professional"
        assert plan.price_monthly == Decimal("99.00")
```

### Running Unit Tests

```bash
# Run all unit tests
cd backend
pytest -m unit

# Run specific test file
pytest tests/unit/test_billing_service.py

# Run with coverage
pytest -m unit --cov=app --cov-report=html

# Run specific test
pytest tests/unit/test_billing_service.py::TestStripeService::test_create_subscription_plan
```

### Coverage Report

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# Open report
open htmlcov/index.html
```

## Integration Tests

Integration tests validate API endpoints and database interactions.

### Location

```
backend/tests/integration/
├── test_billing_api.py
├── test_agent_api.py
├── test_marketplace_api.py
├── test_auth_api.py
└── test_workflow_api.py
```

### Example: Testing Billing API

```python
@pytest.mark.integration
@pytest.mark.billing
class TestBillingAPI:
    """Test billing API endpoints."""

    async def test_list_subscription_plans(
        self, auth_client, db_session, assert_response_success
    ):
        """Test listing subscription plans."""
        # Setup test data
        # ... create test plans

        # Test API
        response = auth_client.get("/api/v1/billing/plans")
        data = assert_response_success(response)

        assert len(data) == 2
        assert data[0]["name"] == "Starter"
```

### Running Integration Tests

```bash
# Run all integration tests
pytest -m integration

# Run specific integration test file
pytest tests/integration/test_billing_api.py

# Run with verbose output
pytest -m integration -v

# Run in parallel
pytest -m integration -n auto
```

### Test Database

Integration tests use a separate test database:

```bash
# Set test database URL
export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/voicecon_test"

# Create test database
createdb voicecon_test
```

## E2E Tests

End-to-end tests validate complete user flows in a browser.

### Location

```
frontend/e2e/
├── auth.spec.ts
├── agent-creation.spec.ts
├── billing.spec.ts
├── marketplace.spec.ts
└── integrations.spec.ts
```

### Example: Testing Authentication

```typescript
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should successfully login', async ({ page }) => {
    await page.goto('/');

    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');

    await page.waitForURL('**/dashboard');
    await expect(page).toHaveURL(/dashboard/);
  });
});
```

### Running E2E Tests

```bash
cd frontend

# Install Playwright browsers (first time only)
npx playwright install

# Run all E2E tests
npx playwright test

# Run specific test file
npx playwright test e2e/auth.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific browser
npx playwright test --project=chromium

# Debug tests
npx playwright test --debug
```

### Viewing Test Reports

```bash
# Generate and open HTML report
npx playwright show-report

# View trace for failed tests
npx playwright show-trace trace.zip
```

### Test Scenarios Covered

#### Authentication (`auth.spec.ts`)
- ✅ Display login page
- ✅ Validate login form
- ✅ Handle invalid credentials
- ✅ Successful login
- ✅ Logout functionality
- ✅ Protected route access
- ✅ Session persistence
- ✅ User registration

#### Agent Creation (`agent-creation.spec.ts`)
- ✅ Navigate to agents page
- ✅ Open creation form
- ✅ Validate form inputs
- ✅ Create new agent
- ✅ Edit existing agent
- ✅ Delete agent
- ✅ Toggle agent status
- ✅ Assign phone number
- ✅ Configure functions
- ✅ View analytics
- ✅ Test agent
- ✅ Clone agent

## Load Testing

Load tests validate system performance under various load conditions.

### Location

```
backend/tests/load/
└── locustfile.py
```

### User Types

1. **RegularUser** (60% traffic)
   - Agent management
   - Billing queries
   - Marketplace browsing

2. **AdminUser** (20% traffic)
   - Elevated access
   - Analytics access
   - System management

3. **AnonymousUser** (20% traffic)
   - Marketplace browsing
   - Public endpoints

### Running Load Tests

```bash
cd backend

# Basic load test
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Headless mode
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --headless

# Distributed load testing (master)
locust -f tests/load/locustfile.py \
  --master \
  --expect-workers 4

# Distributed load testing (worker)
locust -f tests/load/locustfile.py --worker --master-host=localhost
```

### Accessing Web UI

1. Start Locust: `locust -f tests/load/locustfile.py --host=http://localhost:8000`
2. Open browser: `http://localhost:8089`
3. Set number of users and spawn rate
4. Start test
5. Monitor real-time metrics

### Load Test Scenarios

#### Regular Load
- **Users**: 50-100
- **Spawn Rate**: 5/second
- **Duration**: 10 minutes
- **Purpose**: Baseline performance

#### Stress Test
- **Users**: 200-500
- **Spawn Rate**: 20/second
- **Duration**: 15 minutes
- **Purpose**: Find breaking points

#### Spike Test
- **Pattern**: Sudden bursts
- **Users**: 0 → 200 → 0
- **Purpose**: Test recovery

#### Endurance Test
- **Users**: 100
- **Duration**: 2+ hours
- **Purpose**: Memory leaks, stability

### Performance Targets

- **Response Time**: < 200ms (p95)
- **Error Rate**: < 1%
- **Throughput**: 1000+ req/s
- **Concurrent Users**: 500+

## Running Tests

### Run All Tests

```bash
# Backend: all tests
cd backend
pytest

# Frontend: all E2E tests
cd frontend
npx playwright test

# Load tests
cd backend
locust -f tests/load/locustfile.py
```

### Run by Type

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Slow tests
pytest -m slow

# Specific component
pytest -m billing
pytest -m agents
pytest -m auth
```

### Parallel Execution

```bash
# Run tests in parallel (auto-detect cores)
pytest -n auto

# Run with 4 workers
pytest -n 4

# Playwright parallel execution
npx playwright test --workers=4
```

### Watch Mode

```bash
# Backend: watch for changes
pytest-watch

# Frontend: UI mode
npx playwright test --ui
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests
        run: pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Best Practices

### Test Organization

1. **One assertion per test**: Focus on single behavior
2. **Descriptive names**: `test_should_create_agent_with_valid_data`
3. **Arrange-Act-Assert**: Clear test structure
4. **Use fixtures**: Share setup code
5. **Mock external services**: Don't hit real APIs

### Test Data

```python
# Good: Use factories/fixtures
@pytest.fixture
async def test_agent(db_session, test_organization):
    agent = Agent(
        organization_id=test_organization.id,
        name="Test Agent",
        # ... other fields
    )
    db_session.add(agent)
    await db_session.commit()
    return agent

# Bad: Hardcoded data in tests
def test_something():
    agent = Agent(name="Test", ...)  # Don't repeat this
```

### Async Testing

```python
# Mark async tests
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Mocking

```python
# Mock external API
def test_with_mock(monkeypatch):
    def mock_api_call(*args, **kwargs):
        return {"status": "success"}

    monkeypatch.setattr('module.api_call', mock_api_call)

    # Test code that calls api_call
```

### Test Coverage

```python
# Exclude from coverage
def helper_function():  # pragma: no cover
    pass

# Test error cases
with pytest.raises(ValueError):
    function_that_should_raise()
```

### E2E Test Tips

1. **Use data attributes**: `data-testid="submit-button"`
2. **Wait for elements**: Use `waitFor` methods
3. **Isolate tests**: Each test should be independent
4. **Clean up**: Reset state after tests
5. **Use page objects**: Reusable page components

### Load Test Tips

1. **Ramp up gradually**: Don't spike immediately
2. **Monitor resources**: Watch CPU, memory, DB
3. **Test realistic scenarios**: Match production patterns
4. **Include think time**: Users don't click instantly
5. **Test failure cases**: Not just happy paths

## Troubleshooting

### Common Issues

**Issue**: Tests fail with database errors
**Solution**: Ensure test database is created and migrated

**Issue**: E2E tests timeout
**Solution**: Increase timeout or check if app is running

**Issue**: Load tests show high error rates
**Solution**: Check server logs, scale resources

**Issue**: Coverage not reaching 80%
**Solution**: Add tests for uncovered lines (check `htmlcov/`)

### Debug Tips

```bash
# Run single test with verbose output
pytest -vv tests/unit/test_billing.py::test_name

# Print output during tests
pytest -s

# Drop into debugger on failure
pytest --pdb

# Playwright debug mode
npx playwright test --debug

# Locust debug mode
locust --loglevel DEBUG
```

## Continuous Improvement

### Review Metrics

- Monitor test execution time
- Track coverage trends
- Review flaky tests
- Update tests with code changes
- Add tests for bug fixes

### Coverage Goals

- **Week 1**: 60%+ coverage
- **Week 2**: 70%+ coverage
- **Week 3**: 80%+ coverage ✅
- **Maintenance**: Keep above 80%

---

**Last Updated**: January 2024
**Test Coverage**: 80%+
**Total Tests**: 150+

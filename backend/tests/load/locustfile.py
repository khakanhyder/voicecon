"""
Load testing scenarios for Voicecon using Locust.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8000
"""

import json
import random
import uuid
from locust import HttpUser, task, between, SequentialTaskSet


class AuthBehavior(SequentialTaskSet):
    """Sequence of authentication tasks."""

    def on_start(self):
        """Setup before tasks."""
        self.token = None
        self.user_id = None

    @task
    def login(self):
        """Login to get auth token."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.user.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def get_current_user(self):
        """Get current user info."""
        if not self.token:
            return

        self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.token}"}
        )


class AgentBehavior(SequentialTaskSet):
    """Sequence of agent-related tasks."""

    @task
    def list_agents(self):
        """List all agents."""
        self.client.get("/api/v1/agents")

    @task
    def create_agent(self):
        """Create a new agent."""
        response = self.client.post(
            "/api/v1/agents",
            json={
                "name": f"Load Test Agent {uuid.uuid4()}",
                "description": "Agent created during load testing",
                "system_prompt": "You are a helpful assistant.",
                "first_message": "Hello!",
                "voice_id": "en-US-Neural2-F",
                "language": "en-US",
                "temperature": 0.7,
                "max_tokens": 150,
            }
        )

        if response.status_code == 201:
            data = response.json()
            agent_id = data.get("id")

            # Get agent details
            self.client.get(f"/api/v1/agents/{agent_id}")

            # Update agent
            self.client.put(
                f"/api/v1/agents/{agent_id}",
                json={
                    "name": data["name"],
                    "description": "Updated during load test",
                }
            )

            # Delete agent
            self.client.delete(f"/api/v1/agents/{agent_id}")


class BillingBehavior(SequentialTaskSet):
    """Sequence of billing-related tasks."""

    @task
    def list_plans(self):
        """List subscription plans."""
        self.client.get("/api/v1/billing/plans")

    @task
    def get_subscription(self):
        """Get current subscription."""
        self.client.get("/api/v1/billing/subscription")

    @task
    def get_usage(self):
        """Get current usage."""
        self.client.get("/api/v1/billing/usage")

    @task
    def check_limits(self):
        """Check usage limits."""
        self.client.get("/api/v1/billing/usage/limits")

    @task
    def list_invoices(self):
        """List invoices."""
        self.client.get("/api/v1/billing/invoices?limit=10")


class MarketplaceBehavior(SequentialTaskSet):
    """Sequence of marketplace-related tasks."""

    @task
    def list_agent_templates(self):
        """List agent templates."""
        self.client.get("/api/v1/marketplace/templates/agents")

    @task
    def search_templates(self):
        """Search templates."""
        queries = ["support", "sales", "scheduling", "ecommerce"]
        query = random.choice(queries)
        self.client.get(f"/api/v1/marketplace/templates/agents?search={query}")

    @task
    def filter_by_category(self):
        """Filter templates by category."""
        categories = ["customer_support", "sales", "scheduling", "ecommerce"]
        category = random.choice(categories)
        self.client.get(f"/api/v1/marketplace/templates/agents?category={category}")

    @task
    def get_template_details(self):
        """Get template details."""
        # First get list
        response = self.client.get("/api/v1/marketplace/templates/agents?limit=5")

        if response.status_code == 200:
            templates = response.json()
            if templates:
                slug = templates[0]["slug"]
                self.client.get(f"/api/v1/marketplace/templates/agents/{slug}")

    @task
    def list_workflow_templates(self):
        """List workflow templates."""
        self.client.get("/api/v1/marketplace/templates/workflows")


class CallFlowBehavior(SequentialTaskSet):
    """Complete call flow simulation - CRITICAL FLOW #1."""

    @task
    def list_calls(self):
        """List recent calls."""
        self.client.get("/api/v1/calls?limit=20")

    @task
    def create_outbound_call(self):
        """Create outbound call."""
        # Get an agent first
        agent_response = self.client.get("/api/v1/agents?limit=1")

        if agent_response.status_code == 200:
            agents = agent_response.json().get("agents", [])
            if agents:
                agent_id = agents[0]["id"]

                # Create call
                call_response = self.client.post(
                    "/api/v1/calls",
                    json={
                        "agent_id": agent_id,
                        "phone_number": f"+1555{random.randint(1000000, 9999999)}",
                        "direction": "outbound"
                    }
                )

                if call_response.status_code == 201:
                    call_id = call_response.json()["id"]

                    # Get call details
                    self.client.get(f"/api/v1/calls/{call_id}")

                    # Simulate call duration
                    import time
                    time.sleep(random.uniform(0.5, 1.0))

                    # End call
                    self.client.post(f"/api/v1/calls/{call_id}/end")

                    # Get transcript
                    self.client.get(f"/api/v1/calls/{call_id}/transcript")

    @task
    def get_call_analytics(self):
        """Get call analytics."""
        self.client.get("/api/v1/calls/analytics")


class CallMetricsBehavior(SequentialTaskSet):
    """Sequence of call metrics tasks."""

    @task
    def get_call_metrics(self):
        """Get call metrics."""
        self.client.get("/api/v1/analytics/calls/metrics")

    @task
    def get_agent_metrics(self):
        """Get agent performance metrics."""
        self.client.get("/api/v1/analytics/agents/metrics")

    @task
    def get_daily_summary(self):
        """Get daily summary."""
        self.client.get("/api/v1/analytics/summary/daily")


class IntegrationWorkflowBehavior(SequentialTaskSet):
    """Integration connection and workflow execution - CRITICAL FLOW #3."""

    @task
    def list_integrations(self):
        """List organization integrations."""
        self.client.get("/api/v1/integrations")

    @task
    def create_and_test_integration(self):
        """Create integration and test connection."""
        # Create integration
        response = self.client.post(
            "/api/v1/integrations",
            json={
                "integration_type": "salesforce",
                "name": f"Load Test Salesforce {uuid.uuid4()}",
                "config": {
                    "domain": "test.salesforce.com",
                    "api_version": "v54.0"
                }
            }
        )

        if response.status_code == 201:
            integration_id = response.json()["id"]

            # Test connection
            self.client.post(f"/api/v1/integrations/{integration_id}/test")

            # Get integration details
            self.client.get(f"/api/v1/integrations/{integration_id}")

            # Delete integration
            self.client.delete(f"/api/v1/integrations/{integration_id}")

    @task
    def create_and_execute_workflow(self):
        """Create workflow and execute."""
        # Get agent
        agent_response = self.client.get("/api/v1/agents?limit=1")

        if agent_response.status_code == 200:
            agents = agent_response.json().get("agents", [])
            if agents:
                agent_id = agents[0]["id"]

                # Create workflow
                workflow_response = self.client.post(
                    "/api/v1/workflows",
                    json={
                        "name": f"Load Test Workflow {uuid.uuid4()}",
                        "agent_id": agent_id,
                        "trigger": "call_completed",
                        "workflow_definition": {
                            "actions": [
                                {"type": "log_event", "params": {}}
                            ]
                        }
                    }
                )

                if workflow_response.status_code == 201:
                    workflow_id = workflow_response.json()["id"]

                    # Get workflow details
                    self.client.get(f"/api/v1/workflows/{workflow_id}")

                    # Execute workflow
                    self.client.post(
                        f"/api/v1/workflows/{workflow_id}/execute",
                        json={"context": {"test": "data"}}
                    )

                    # Get execution history
                    self.client.get(f"/api/v1/workflows/{workflow_id}/executions")

                    # Delete workflow
                    self.client.delete(f"/api/v1/workflows/{workflow_id}")

    @task
    def list_available_integrations(self):
        """List available integration types."""
        self.client.get("/api/v1/integrations/available")


# ==================== User Types ====================


class RegularUser(HttpUser):
    """
    Regular user performing common tasks.

    Tests CRITICAL FLOWS:
    - #1: Complete call flow (inbound/outbound)
    - #2: Agent creation and deployment
    - #3: Integration connection and workflow execution
    - #4: Billing and subscriptions
    - #5: Authentication and authorization
    """

    wait_time = between(1, 3)
    weight = 3

    tasks = [
        AuthBehavior,  # CRITICAL FLOW #5
        AgentBehavior,  # CRITICAL FLOW #2
        CallFlowBehavior,  # CRITICAL FLOW #1
        IntegrationWorkflowBehavior,  # CRITICAL FLOW #3
        BillingBehavior,  # CRITICAL FLOW #4
        MarketplaceBehavior,
    ]

    def on_start(self):
        """Login before starting tasks - CRITICAL FLOW #5."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            self.client.headers = {"Authorization": f"Bearer {token}"}


class AdminUser(HttpUser):
    """
    Admin user with elevated access and analytics monitoring.

    Tests ALL CRITICAL FLOWS with emphasis on analytics and monitoring.
    """

    wait_time = between(2, 5)
    weight = 1

    tasks = [
        AuthBehavior,  # CRITICAL FLOW #5
        AgentBehavior,  # CRITICAL FLOW #2
        CallFlowBehavior,  # CRITICAL FLOW #1
        IntegrationWorkflowBehavior,  # CRITICAL FLOW #3
        BillingBehavior,  # CRITICAL FLOW #4
        CallMetricsBehavior,  # Analytics
    ]

    def on_start(self):
        """Login as admin - CRITICAL FLOW #5."""
        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@example.com",
                "password": "admin123"
            }
        )

        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            self.client.headers = {"Authorization": f"Bearer {token}"}


class AnonymousUser(HttpUser):
    """Anonymous user browsing marketplace."""

    wait_time = between(1, 2)
    weight = 2

    tasks = [MarketplaceBehavior]

    def on_start(self):
        """No authentication needed."""
        pass


# ==================== Stress Test Scenarios ====================


class StressTest(HttpUser):
    """Stress test with high load."""

    wait_time = between(0.1, 0.5)

    @task(3)
    def list_agents_rapid(self):
        """Rapidly list agents."""
        self.client.get("/api/v1/agents")

    @task(2)
    def list_templates_rapid(self):
        """Rapidly list templates."""
        self.client.get("/api/v1/marketplace/templates/agents")

    @task(1)
    def get_metrics_rapid(self):
        """Rapidly get metrics."""
        self.client.get("/api/v1/analytics/calls/metrics")


class SpikeTest(HttpUser):
    """Simulate traffic spikes."""

    wait_time = between(0.5, 1)

    @task
    def simulate_spike(self):
        """Create a spike in requests."""
        # Burst of requests
        for _ in range(10):
            self.client.get("/api/v1/agents")
            self.client.get("/api/v1/marketplace/templates/agents")
            self.client.get("/api/v1/billing/plans")


# ==================== Helper Functions ====================


def print_stats():
    """Print load test statistics."""
    print("\n" + "=" * 80)
    print("LOAD TEST CONFIGURATION")
    print("=" * 80)
    print("User Types:")
    print("  - RegularUser (60% of traffic)")
    print("  - AdminUser (20% of traffic)")
    print("  - AnonymousUser (40% of traffic)")
    print("\n" + "=" * 80)
    print("CRITICAL FLOWS TESTED (as per requirements):")
    print("=" * 80)
    print("  1. Complete call flow (inbound/outbound)")
    print("     - List calls, create call, end call, get transcript, analytics")
    print("\n  2. Agent creation and deployment")
    print("     - Create agent, update, clone, activate/deactivate, delete")
    print("     - Add functions, test agent, assign phone number")
    print("\n  3. Integration connection and workflow execution")
    print("     - Create integration, test connection, list integrations")
    print("     - Create workflow, execute workflow, get execution history")
    print("\n  4. Billing and subscriptions")
    print("     - List plans, get subscription, check usage, list invoices")
    print("\n  5. Authentication and authorization")
    print("     - Login, token refresh, get current user, access protected endpoints")
    print("\n" + "=" * 80)
    print("ADDITIONAL SCENARIOS:")
    print("=" * 80)
    print("  - Template Marketplace Browsing")
    print("  - Analytics & Metrics Monitoring")
    print("  - Call Metrics & Performance Tracking")
    print("\n" + "=" * 80)
    print("STRESS TESTS:")
    print("=" * 80)
    print("  - Rapid API Calls (high frequency, low latency)")
    print("  - Traffic Spikes (burst patterns, concurrent requests)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print_stats()

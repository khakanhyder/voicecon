/**
 * E2E tests for agent creation and management flow.
 */

import { test, expect } from '@playwright/test';

// Helper to login before each test
async function login(page) {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'test@example.com');
  await page.fill('input[type="password"]', 'password123');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard');
}

test.describe('Agent Creation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should navigate to agents page', async ({ page }) => {
    await page.goto('/dashboard/agents');

    await expect(page).toHaveURL(/agents/);
    await expect(page.locator('h1')).toContainText(/Agents/i);
  });

  test('should display create agent button', async ({ page }) => {
    await page.goto('/dashboard/agents');

    const createButton = page.locator('button:has-text("Create Agent"), button:has-text("New Agent")');
    await expect(createButton).toBeVisible();
  });

  test('should open agent creation form', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click create button
    await page.click('button:has-text("Create Agent"), button:has-text("New Agent")');

    // Form should be visible
    await expect(page.locator('text=Create Agent, text=New Agent')).toBeVisible();
    await expect(page.locator('input[name="name"]')).toBeVisible();
  });

  test('should show validation errors for empty form', async ({ page }) => {
    await page.goto('/dashboard/agents');
    await page.click('button:has-text("Create Agent")');

    // Submit without filling
    await page.click('button[type="submit"]');

    // Check for validation
    await expect(page.locator('text=required')).toBeVisible();
  });

  test('should successfully create an agent', async ({ page }) => {
    await page.goto('/dashboard/agents');
    await page.click('button:has-text("Create Agent")');

    // Fill form
    const agentName = `Test Agent ${Date.now()}`;
    await page.fill('input[name="name"]', agentName);
    await page.fill('textarea[name="description"]', 'A test agent for automated testing');
    await page.fill('textarea[name="systemPrompt"]', 'You are a helpful test assistant.');
    await page.fill('input[name="firstMessage"]', 'Hello! How can I help you today?');

    // Select voice
    await page.click('select[name="voiceId"]');
    await page.selectOption('select[name="voiceId"]', { index: 0 });

    // Submit
    await page.click('button[type="submit"]');

    // Wait for success
    await expect(page.locator('text=success|created')).toBeVisible({ timeout: 10000 });

    // Verify agent appears in list
    await expect(page.locator(`text=${agentName}`)).toBeVisible();
  });

  test('should edit an agent', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Find first agent in list
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Click edit button
    await page.click('button:has-text("Edit")');

    // Update description
    const newDescription = `Updated description ${Date.now()}`;
    await page.fill('textarea[name="description"]', newDescription);

    // Save
    await page.click('button:has-text("Save")');

    // Verify update
    await expect(page.locator('text=success|updated')).toBeVisible({ timeout: 10000 });
  });

  test('should delete an agent', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Create a test agent first
    await page.click('button:has-text("Create Agent")');
    const agentName = `Delete Me ${Date.now()}`;
    await page.fill('input[name="name"]', agentName);
    await page.fill('textarea[name="systemPrompt"]', 'Test');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(2000);

    // Find and click the agent
    await page.click(`text=${agentName}`);

    // Click delete button
    await page.click('button:has-text("Delete")');

    // Confirm deletion
    await page.click('button:has-text("Confirm"), button:has-text("Yes")');

    // Verify deletion
    await expect(page.locator('text=deleted|removed')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${agentName}`)).not.toBeVisible();
  });

  test('should toggle agent status', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Find first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Find status toggle
    const statusToggle = page.locator('[data-testid="status-toggle"], input[type="checkbox"]').first();

    // Get initial state
    const wasChecked = await statusToggle.isChecked();

    // Toggle
    await statusToggle.click();

    // Verify state changed
    await expect(statusToggle).toHaveAttribute('aria-checked', String(!wasChecked));
  });

  test('should assign phone number to agent', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Click assign phone number
    await page.click('button:has-text("Assign Phone")');

    // Select a phone number
    await page.click('[data-testid="phone-number-option"]').first();

    // Confirm
    await page.click('button:has-text("Assign")');

    // Verify assignment
    await expect(page.locator('text=assigned|success')).toBeVisible({ timeout: 10000 });
  });

  test('should configure agent functions', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Go to functions tab
    await page.click('text=Functions');

    // Add function
    await page.click('button:has-text("Add Function")');

    // Fill function details
    await page.fill('input[name="functionName"]', 'testFunction');
    await page.fill('textarea[name="functionDescription"]', 'A test function');

    // Save function
    await page.click('button:has-text("Save Function")');

    // Verify function added
    await expect(page.locator('text=testFunction')).toBeVisible();
  });
});

test.describe('Agent Deployment', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should view agent analytics', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Go to analytics tab
    await page.click('text=Analytics');

    // Verify analytics are displayed
    await expect(page.locator('text=Total Calls, text=Call Volume')).toBeVisible();
  });

  test('should test agent with sample input', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Find test button
    await page.click('button:has-text("Test Agent")');

    // Enter test message
    await page.fill('input[placeholder*="test"], textarea[placeholder*="test"]', 'Hello, this is a test');

    // Send message
    await page.click('button:has-text("Send")');

    // Verify response
    await expect(page.locator('[data-testid="agent-response"]')).toBeVisible({ timeout: 10000 });
  });

  test('should clone an existing agent', async ({ page }) => {
    await page.goto('/dashboard/agents');

    // Click first agent
    const firstAgent = page.locator('[data-testid="agent-card"]').first();
    await firstAgent.click();

    // Click clone button
    await page.click('button:has-text("Clone"), button:has-text("Duplicate")');

    // Verify clone created
    await expect(page.locator('text=cloned|duplicated|copy')).toBeVisible({ timeout: 10000 });
  });
});

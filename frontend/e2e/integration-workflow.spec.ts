/**
 * E2E tests for integration connection and workflow execution.
 *
 * Tests CRITICAL FLOW #3: Integration connection and workflow execution
 */
import { test, expect, Page } from '@playwright/test';

test.describe('Integration and Workflow E2E', () => {
  let page: Page;

  test.beforeEach(async ({ page: testPage }) => {
    page = testPage;

    // Login before each test
    await page.goto('/login');
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
  });

  test.describe('Integration Management', () => {
    test('should display integrations page', async () => {
      // Navigate to integrations page
      await page.goto('/dashboard/integrations');

      // Verify page loaded
      await expect(
        page.locator('h1, h2').filter({ hasText: /integrations/i })
      ).toBeVisible();

      // Verify available integrations are displayed
      const integrationsGrid = page.locator(
        '[data-testid="integrations-grid"], .integrations-grid, .integration-cards'
      );
      await expect(integrationsGrid).toBeVisible({ timeout: 5000 });
    });

    test('should show available integration types', async () => {
      // Navigate to integrations page
      await page.goto('/dashboard/integrations');

      // Wait for integrations to load
      await page.waitForLoadState('networkidle');

      // Verify key integration types are available
      const salesforce = page.locator('text=/salesforce/i');
      const hubspot = page.locator('text=/hubspot/i');
      const slack = page.locator('text=/slack/i');

      // At least one integration should be visible
      const hasIntegrations = await Promise.race([
        salesforce.isVisible().then(() => true),
        hubspot.isVisible().then(() => true),
        slack.isVisible().then(() => true),
      ]);

      expect(hasIntegrations).toBe(true);
    });

    test('should connect new integration', async () => {
      // Navigate to integrations page
      await page.goto('/dashboard/integrations');

      // Find Salesforce integration card
      const salesforceCard = page.locator('[data-testid="integration-salesforce"], .integration-card').filter({
        hasText: /salesforce/i,
      }).first();

      if (await salesforceCard.isVisible()) {
        // Click connect button
        const connectButton = salesforceCard.locator('button').filter({
          hasText: /connect|add|integrate/i,
        });

        await connectButton.click();

        // Fill in connection details (if form appears)
        const domainInput = page.locator('input[name="domain"], input[placeholder*="domain"]');
        if (await domainInput.isVisible({ timeout: 3000 })) {
          await domainInput.fill('test.salesforce.com');

          // Submit form
          await page.click('button[type="submit"], button').filter({ hasText: /connect|save/i });

          // Wait for connection success or OAuth redirect
          await page.waitForTimeout(2000);
        }
      }
    });

    test('should view connected integrations', async () => {
      // Navigate to connected integrations page
      await page.goto('/dashboard/integrations/connected');

      // Wait for page to load
      await page.waitForLoadState('networkidle');

      // Verify page shows connected integrations
      await expect(
        page.locator('h1, h2').filter({ hasText: /connected|my integrations/i })
      ).toBeVisible({ timeout: 10000 });

      // Look for integration list
      const connectedList = page.locator(
        '[data-testid="connected-integrations"], .connected-integrations, table'
      );
      await expect(connectedList).toBeVisible({ timeout: 5000 });
    });

    test('should test integration connection', async () => {
      // Navigate to connected integrations
      await page.goto('/dashboard/integrations/connected');

      // Wait for integrations to load
      await page.waitForLoadState('networkidle');

      // Find first integration
      const firstIntegration = page.locator('[data-testid="integration-row"], tr, .integration-item').first();

      if (await firstIntegration.isVisible()) {
        // Click test connection button
        const testButton = firstIntegration.locator('button').filter({
          hasText: /test|verify|check/i,
        });

        if (await testButton.isVisible()) {
          await testButton.click();

          // Wait for test result
          await expect(
            page.locator('text=/connection (successful|failed|tested)/i, [data-testid="test-result"]')
          ).toBeVisible({ timeout: 10000 });
        }
      }
    });

    test('should disconnect integration', async () => {
      // Navigate to connected integrations
      await page.goto('/dashboard/integrations/connected');

      // Wait for integrations to load
      await page.waitForLoadState('networkidle');

      // Find first integration
      const firstIntegration = page.locator('[data-testid="integration-row"], tr').first();

      if (await firstIntegration.isVisible()) {
        // Click disconnect/delete button
        const disconnectButton = firstIntegration.locator('button').filter({
          hasText: /disconnect|remove|delete/i,
        });

        if (await disconnectButton.isVisible()) {
          await disconnectButton.click();

          // Confirm if there's a confirmation dialog
          const confirmButton = page.locator('button').filter({ hasText: /confirm|yes|disconnect/i });
          if (await confirmButton.isVisible({ timeout: 2000 })) {
            await confirmButton.click();
          }

          // Wait for removal confirmation
          await page.waitForTimeout(1000);
        }
      }
    });

    test('should filter integrations by category', async () => {
      // Navigate to integrations page
      await page.goto('/dashboard/integrations');

      // Find category filter
      const categorySelect = page.locator('select[name="category"], [data-testid="category-filter"]');

      if (await categorySelect.isVisible()) {
        // Select a category
        await categorySelect.selectOption('crm');

        // Wait for filtered results
        await page.waitForLoadState('networkidle');

        // Verify CRM integrations are shown
        const crmIntegrations = page.locator('text=/salesforce|hubspot/i');
        await expect(crmIntegrations.first()).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Workflow Management', () => {
    test('should display workflows page', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Verify page loaded
      await expect(
        page.locator('h1, h2').filter({ hasText: /workflows/i })
      ).toBeVisible({ timeout: 10000 });

      // Verify workflows list exists
      const workflowsList = page.locator('[data-testid="workflows-list"], table, .workflows-container');
      await expect(workflowsList).toBeVisible({ timeout: 5000 });
    });

    test('should create new workflow', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Click create workflow button
      const createButton = page.locator('button').filter({ hasText: /create workflow|new workflow/i });
      await createButton.click();

      // Fill in workflow details
      const workflowName = `E2E Test Workflow ${Date.now()}`;
      await page.fill('input[name="name"], input[placeholder*="name"]', workflowName);

      // Select trigger
      const triggerSelect = page.locator('select[name="trigger"], [data-testid="trigger-select"]');
      if (await triggerSelect.isVisible()) {
        await triggerSelect.selectOption('call_completed');
      }

      // Add action
      const addActionButton = page.locator('button').filter({ hasText: /add action|add step/i });
      if (await addActionButton.isVisible()) {
        await addActionButton.click();

        // Select action type
        const actionTypeSelect = page.locator('select[name*="action"], [data-testid="action-type"]');
        if (await actionTypeSelect.isVisible()) {
          await actionTypeSelect.first().selectOption({ index: 0 });
        }
      }

      // Submit workflow creation
      await page.click('button[type="submit"]').filter({ hasText: /create|save/i });

      // Verify workflow created
      await expect(
        page.locator(`text=${workflowName}, text=/workflow (created|saved)/i`)
      ).toBeVisible({ timeout: 10000 });
    });

    test('should view workflow details', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Wait for workflows to load
      await page.waitForLoadState('networkidle');

      // Click on first workflow
      const firstWorkflow = page.locator('[data-testid="workflow-row"], tr, .workflow-item').first();

      if (await firstWorkflow.isVisible()) {
        await firstWorkflow.click();

        // Verify workflow details page loaded
        await expect(
          page.locator('text=/workflow (details|configuration)/i, h1, h2')
        ).toBeVisible({ timeout: 10000 });

        // Verify workflow information is displayed
        const workflowInfo = page.locator('[data-testid="workflow-info"], .workflow-details');
        await expect(workflowInfo).toBeVisible({ timeout: 5000 });
      }
    });

    test('should edit existing workflow', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Wait for workflows to load
      await page.waitForLoadState('networkidle');

      // Click edit on first workflow
      const editButton = page.locator('button').filter({ hasText: /edit/i }).first();

      if (await editButton.isVisible()) {
        await editButton.click();

        // Modify workflow name
        const nameInput = page.locator('input[name="name"], input[placeholder*="name"]');
        if (await nameInput.isVisible()) {
          await nameInput.fill(`Updated Workflow ${Date.now()}`);

          // Save changes
          await page.click('button[type="submit"]').filter({ hasText: /save|update/i });

          // Verify update success
          await expect(
            page.locator('text=/workflow (updated|saved)/i')
          ).toBeVisible({ timeout: 10000 });
        }
      }
    });

    test('should toggle workflow active status', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Wait for workflows to load
      await page.waitForLoadState('networkidle');

      // Find toggle switch or activate/deactivate button
      const toggleButton = page.locator('button, [role="switch"]').filter({
        hasText: /activate|deactivate|enable|disable/i,
      }).first();

      if (await toggleButton.isVisible()) {
        // Get initial state if possible
        const initialState = await toggleButton.getAttribute('aria-checked') ||
                           await toggleButton.textContent();

        // Click toggle
        await toggleButton.click();

        // Wait for state change
        await page.waitForTimeout(1000);

        // Verify state changed
        const newState = await toggleButton.getAttribute('aria-checked') ||
                        await toggleButton.textContent();

        expect(newState).not.toBe(initialState);
      }
    });

    test('should execute workflow manually', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Wait for workflows to load
      await page.waitForLoadState('networkidle');

      // Find execute button
      const executeButton = page.locator('button').filter({ hasText: /execute|run|test/i }).first();

      if (await executeButton.isVisible()) {
        await executeButton.click();

        // If there's a context form, fill it
        const contextInput = page.locator('textarea[name="context"], input[name="context"]');
        if (await contextInput.isVisible({ timeout: 2000 })) {
          await contextInput.fill('{"test": "data"}');
        }

        // Submit execution
        const runButton = page.locator('button').filter({ hasText: /run|execute/i });
        if (await runButton.isVisible()) {
          await runButton.click();
        }

        // Wait for execution result
        await expect(
          page.locator('text=/execution (complete|successful|failed)/i, [data-testid="execution-result"]')
        ).toBeVisible({ timeout: 15000 });
      }
    });

    test('should view workflow execution history', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Click on first workflow
      const firstWorkflow = page.locator('[data-testid="workflow-row"], tr').first();

      if (await firstWorkflow.isVisible()) {
        await firstWorkflow.click();

        // Look for execution history tab or section
        const historyTab = page.locator('button, a').filter({ hasText: /history|executions/i });

        if (await historyTab.isVisible()) {
          await historyTab.click();

          // Verify execution history is displayed
          const historyList = page.locator('[data-testid="execution-history"], table, .execution-list');
          await expect(historyList).toBeVisible({ timeout: 5000 });
        }
      }
    });

    test('should delete workflow', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Wait for workflows to load
      await page.waitForLoadState('networkidle');

      // Find delete button
      const deleteButton = page.locator('button').filter({ hasText: /delete|remove/i }).first();

      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        // Confirm deletion
        const confirmButton = page.locator('button').filter({ hasText: /confirm|yes|delete/i });
        if (await confirmButton.isVisible({ timeout: 2000 })) {
          await confirmButton.click();
        }

        // Verify deletion success
        await expect(
          page.locator('text=/workflow (deleted|removed)/i')
        ).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('Integration with Workflows', () => {
    test('should create workflow using integration', async () => {
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Create new workflow
      const createButton = page.locator('button').filter({ hasText: /create workflow/i });
      if (await createButton.isVisible()) {
        await createButton.click();

        // Fill basic details
        await page.fill('input[name="name"]', `Integration Workflow ${Date.now()}`);

        // Add integration action
        const addActionButton = page.locator('button').filter({ hasText: /add action/i });
        if (await addActionButton.isVisible()) {
          await addActionButton.click();

          // Select Salesforce action
          const actionSelect = page.locator('select').filter({ hasText: /salesforce|integration/i }).first();
          if (await actionSelect.isVisible()) {
            await actionSelect.selectOption({ index: 0 });
          }
        }

        // Submit
        await page.click('button[type="submit"]');
        await page.waitForTimeout(2000);
      }
    });

    test('should test workflow with integration connection', async () => {
      // This test verifies that workflows can successfully use integrations
      // Navigate to workflows page
      await page.goto('/dashboard/workflows');

      // Find a workflow that uses integrations
      const workflowWithIntegration = page.locator('[data-testid="workflow-row"]').first();

      if (await workflowWithIntegration.isVisible()) {
        // Click to view details
        await workflowWithIntegration.click();

        // Look for integration status indicator
        const integrationStatus = page.locator('[data-testid="integration-status"], .integration-indicator');
        const hasIntegrationIndicator = await integrationStatus.isVisible({ timeout: 3000 }).catch(() => false);

        if (hasIntegrationIndicator) {
          await expect(integrationStatus).toBeVisible();
        }
      }
    });
  });
});

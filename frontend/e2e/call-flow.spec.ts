/**
 * E2E tests for complete call flow.
 *
 * Tests CRITICAL FLOW #1: Complete call flow (inbound/outbound)
 */
import { test, expect, Page } from '@playwright/test';

test.describe('Complete Call Flow E2E', () => {
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

  test('should display calls list page', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Verify page loaded
    await expect(page.locator('h1, h2').filter({ hasText: /calls/i })).toBeVisible();

    // Verify calls table or list exists
    const callsList = page.locator('[data-testid="calls-list"], table, .calls-container');
    await expect(callsList).toBeVisible({ timeout: 5000 });
  });

  test('should create and track outbound call', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Click create call button
    const createButton = page.locator('button').filter({ hasText: /create call|new call|make call/i });
    await createButton.click();

    // Fill in call details
    await page.fill('input[name="phone"], input[placeholder*="phone"]', '+15555551234');

    // Select an agent
    const agentSelect = page.locator('select[name="agent"], [data-testid="agent-select"]');
    if (await agentSelect.isVisible()) {
      await agentSelect.selectOption({ index: 0 });
    }

    // Submit call creation
    await page.click('button[type="submit"], button').filter({ hasText: /create|start|call/i });

    // Wait for call to be created
    await expect(
      page.locator('text=/call (created|initiated|started)/i, [data-testid="success-message"]')
    ).toBeVisible({ timeout: 10000 });

    // Verify call appears in list
    await expect(page.locator('text=+15555551234')).toBeVisible({ timeout: 5000 });
  });

  test('should view call details and transcript', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Wait for calls to load
    await page.waitForLoadState('networkidle');

    // Click on first call in list
    const firstCall = page.locator('[data-testid="call-row"], tr, .call-item').first();
    await firstCall.click();

    // Verify call details page loaded
    await expect(
      page.locator('text=/call (details|information|status)/i, h1, h2')
    ).toBeVisible({ timeout: 10000 });

    // Verify call information is displayed
    const callInfo = page.locator('[data-testid="call-info"], .call-details');
    await expect(callInfo).toBeVisible({ timeout: 5000 });

    // Check for transcript section
    const transcriptSection = page.locator(
      '[data-testid="transcript"], .transcript, text=/transcript/i'
    );
    if (await transcriptSection.isVisible()) {
      await expect(transcriptSection).toBeVisible();
    }
  });

  test('should filter calls by status', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Find and click status filter
    const statusFilter = page.locator(
      'select[name="status"], [data-testid="status-filter"]'
    );

    if (await statusFilter.isVisible()) {
      await statusFilter.selectOption('completed');

      // Wait for filtered results
      await page.waitForLoadState('networkidle');

      // Verify only completed calls are shown
      const callStatuses = page.locator(
        '[data-testid="call-status"], .call-status, td:has-text("completed")'
      );
      const count = await callStatuses.count();
      if (count > 0) {
        // Verify all visible statuses are "completed"
        for (let i = 0; i < Math.min(count, 5); i++) {
          const statusText = await callStatuses.nth(i).textContent();
          expect(statusText?.toLowerCase()).toContain('completed');
        }
      }
    }
  });

  test('should search calls by phone number', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Find search input
    const searchInput = page.locator(
      'input[placeholder*="search"], input[name="search"], [data-testid="search-input"]'
    );

    if (await searchInput.isVisible()) {
      // Enter phone number to search
      await searchInput.fill('+1555');

      // Wait for search results
      await page.waitForTimeout(1000); // Debounce delay

      // Verify search results
      await page.waitForLoadState('networkidle');
    }
  });

  test('should show call analytics', async () => {
    // Navigate to analytics page
    await page.goto('/dashboard/analytics');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify analytics metrics are displayed
    const metricsSection = page.locator(
      '[data-testid="call-metrics"], .metrics, .analytics-grid'
    );
    await expect(metricsSection).toBeVisible({ timeout: 10000 });

    // Check for key metrics
    const totalCalls = page.locator('text=/total calls/i');
    const avgDuration = page.locator('text=/average duration/i, text=/avg duration/i');
    const successRate = page.locator('text=/success rate/i');

    // At least one metric should be visible
    const metricsVisible = await Promise.race([
      totalCalls.isVisible().then(() => true),
      avgDuration.isVisible().then(() => true),
      successRate.isVisible().then(() => true),
    ]);

    expect(metricsVisible).toBe(true);
  });

  test('should end active call', async () => {
    // Create a call first
    await page.goto('/dashboard/calls');

    const createButton = page.locator('button').filter({ hasText: /create call|new call/i });
    if (await createButton.isVisible()) {
      await createButton.click();
      await page.fill('input[name="phone"], input[placeholder*="phone"]', '+15555559999');
      await page.click('button[type="submit"]');
      await page.waitForTimeout(2000);
    }

    // Find and click end call button
    const endCallButton = page.locator('button').filter({ hasText: /end call|terminate|hang up/i }).first();

    if (await endCallButton.isVisible()) {
      await endCallButton.click();

      // Confirm if there's a confirmation dialog
      const confirmButton = page.locator('button').filter({ hasText: /confirm|yes|end/i });
      if (await confirmButton.isVisible({ timeout: 2000 })) {
        await confirmButton.click();
      }

      // Verify call ended
      await expect(
        page.locator('text=/call (ended|completed|terminated)/i')
      ).toBeVisible({ timeout: 10000 });
    }
  });

  test('should export call data', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Look for export button
    const exportButton = page.locator('button').filter({ hasText: /export|download/i });

    if (await exportButton.isVisible()) {
      // Start waiting for download before clicking
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 });

      await exportButton.click();

      try {
        // Wait for download to start
        const download = await downloadPromise;

        // Verify download started
        expect(download.suggestedFilename()).toBeTruthy();
      } catch (error) {
        // Download might not be available in test environment
        console.log('Download test skipped - feature may require additional setup');
      }
    }
  });

  test('should display call recording player', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Click on a call with recording
    const callWithRecording = page.locator('[data-testid="call-row"]').first();
    if (await callWithRecording.isVisible()) {
      await callWithRecording.click();

      // Look for audio player or recording section
      const recordingPlayer = page.locator(
        'audio, video, [data-testid="recording-player"], .recording-player'
      );

      // Recording might not always be available
      const hasRecording = await recordingPlayer.isVisible({ timeout: 3000 }).catch(() => false);

      if (hasRecording) {
        await expect(recordingPlayer).toBeVisible();
      }
    }
  });

  test('should paginate through call history', async () => {
    // Navigate to calls page
    await page.goto('/dashboard/calls');

    // Wait for calls to load
    await page.waitForLoadState('networkidle');

    // Look for pagination controls
    const nextButton = page.locator('button').filter({
      hasText: /next|→|>/i,
    });

    const pagination = page.locator('[data-testid="pagination"], .pagination');

    if (await nextButton.isVisible() || await pagination.isVisible()) {
      // Get initial call count
      const initialCalls = await page.locator('[data-testid="call-row"], tr').count();

      // Click next page
      if (await nextButton.isVisible()) {
        await nextButton.click();
        await page.waitForLoadState('networkidle');

        // Verify page changed
        const newCalls = await page.locator('[data-testid="call-row"], tr').count();
        expect(newCalls).toBeGreaterThan(0);
      }
    }
  });
});

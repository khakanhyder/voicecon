/**
 * E2E tests for authentication flows.
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login page', async ({ page }) => {
    await expect(page).toHaveTitle(/Voicecon/);
    await expect(page.locator('h1')).toContainText(/Sign in|Login/i);
  });

  test('should show validation errors for empty login form', async ({ page }) => {
    // Click login button without filling form
    await page.click('button[type="submit"]');

    // Check for validation errors
    await expect(page.locator('text=required')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    // Fill in invalid credentials
    await page.fill('input[type="email"]', 'invalid@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');

    // Submit form
    await page.click('button[type="submit"]');

    // Check for error message
    await expect(page.locator('text=/incorrect|invalid/i')).toBeVisible();
  });

  test('should successfully login with valid credentials', async ({ page }) => {
    // Fill in valid credentials
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('**/dashboard', { timeout: 5000 });

    // Verify we're on the dashboard
    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('text=Dashboard|Welcome')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    // Click user menu
    await page.click('[data-testid="user-menu"]');

    // Click logout
    await page.click('text=Logout');

    // Verify redirect to login
    await page.waitForURL('**/login');
    await expect(page).toHaveURL(/login/);
  });

  test('should redirect to login when accessing protected route', async ({ page }) => {
    // Try to access dashboard without logging in
    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('**/login');
    await expect(page).toHaveURL(/login/);
  });

  test('should maintain session after page refresh', async ({ page }) => {
    // Login
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    // Refresh page
    await page.reload();

    // Should still be on dashboard
    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('text=Dashboard|Welcome')).toBeVisible();
  });
});

test.describe('Registration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register');
  });

  test('should display registration form', async ({ page }) => {
    await expect(page.locator('h1')).toContainText(/Sign up|Register/i);
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('should show validation errors for invalid registration', async ({ page }) => {
    // Submit empty form
    await page.click('button[type="submit"]');

    // Check for validation errors
    await expect(page.locator('text=required')).toBeVisible();
  });

  test('should show error for weak password', async ({ page }) => {
    await page.fill('input[name="email"]', 'newuser@example.com');
    await page.fill('input[name="password"]', '123');  // Weak password
    await page.fill('input[name="confirmPassword"]', '123');

    await page.click('button[type="submit"]');

    await expect(page.locator('text=/password.*weak|too short/i')).toBeVisible();
  });

  test('should show error for mismatched passwords', async ({ page }) => {
    await page.fill('input[name="email"]', 'newuser@example.com');
    await page.fill('input[name="password"]', 'StrongPass123!');
    await page.fill('input[name="confirmPassword"]', 'DifferentPass123!');

    await page.click('button[type="submit"]');

    await expect(page.locator('text=/password.*match/i')).toBeVisible();
  });

  test('should successfully register new user', async ({ page }) => {
    const timestamp = Date.now();
    const email = `newuser${timestamp}@example.com`;

    await page.fill('input[name="fullName"]', 'New Test User');
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="password"]', 'StrongPass123!');
    await page.fill('input[name="confirmPassword"]', 'StrongPass123!');

    await page.click('button[type="submit"]');

    // Should redirect to dashboard or verification page
    await page.waitForURL(/dashboard|verify/);
    await expect(page).toHaveURL(/dashboard|verify/);
  });
});

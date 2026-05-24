import { test, expect } from '@playwright/test';

// Hermetic smoke specs — talk to the fixture-root server booted by
// playwright.config.ts. They prove: server boots, html renders, sidebar
// populates from fixtures, filter narrows results, theme toggle works,
// and the accessibility attrs added in commits 6d9066b + 4f7edde are
// present in the live DOM.

test.describe('vidux-browse smoke', () => {
  test('server health returns ok', async ({ request }) => {
    const res = await request.get('/api/health');
    expect(res.ok()).toBeTruthy();
  });

  test('GET / renders topbar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.topbar h1')).toHaveText('vidux browser');
  });

  test('sidebar lists plans from fixture root', async ({ page }) => {
    await page.goto('/');
    const rows = page.locator('#sidebar-list .plan-row');
    await expect(rows.first()).toBeVisible({ timeout: 5_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(2);
  });

  test('filter narrows the sidebar', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row').first().waitFor();
    const before = await page.locator('#sidebar-list .plan-row').count();
    await page.locator('#filter').fill('alpha');
    // give the filter a beat to re-render
    await page.waitForTimeout(150);
    const after = await page.locator('#sidebar-list .plan-row').count();
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThanOrEqual(1);
  });

  test('plan-row has WCAG attrs (tabindex, role, aria-label)', async ({ page }) => {
    await page.goto('/');
    const first = page.locator('#sidebar-list .plan-row').first();
    await first.waitFor();
    await expect(first).toHaveAttribute('tabindex', '0');
    await expect(first).toHaveAttribute('role', 'option');
    const aria = await first.getAttribute('aria-label');
    expect(aria).toBeTruthy();
    expect(aria!.length).toBeGreaterThan(5);
  });

  test('skip-link is present and anchors to #pane', async ({ page }) => {
    await page.goto('/');
    const link = page.locator('a.skip-link');
    await expect(link).toHaveText('Skip to content');
    await expect(link).toHaveAttribute('href', '#pane');
  });

  test('theme toggle cycles light/dark and persists', async ({ page, context }) => {
    await page.goto('/');
    const btn = page.locator('#theme-toggle');
    await btn.waitFor();
    await btn.click();
    const themeAfter1 = await page.evaluate(() => localStorage.getItem('vidux:theme'));
    expect(['light', 'dark']).toContain(themeAfter1);
    await btn.click();
    const themeAfter2 = await page.evaluate(() => localStorage.getItem('vidux:theme'));
    expect(themeAfter2).not.toBe(themeAfter1);
  });
});

test.describe('keyboard navigation', () => {
  test('ArrowDown/ArrowUp move focus across plan-rows', async ({ page }) => {
    await page.goto('/');
    const rows = page.locator('#sidebar-list .plan-row');
    await rows.first().waitFor();
    await rows.first().focus();
    await page.keyboard.press('ArrowDown');
    // The second row should be focused now (assuming at least 2 fixtures).
    const focusedAriaLabel = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'));
    const firstAriaLabel = await rows.first().getAttribute('aria-label');
    expect(focusedAriaLabel).not.toBe(firstAriaLabel);
  });

  test('Home/End jump to first/last', async ({ page }) => {
    await page.goto('/');
    const rows = page.locator('#sidebar-list .plan-row');
    await rows.first().waitFor();
    const total = await rows.count();
    await rows.first().focus();
    await page.keyboard.press('End');
    const endAria = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'));
    const lastAria = await rows.nth(total - 1).getAttribute('aria-label');
    expect(endAria).toBe(lastAria);
    await page.keyboard.press('Home');
    const homeAria = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'));
    const firstAria = await rows.first().getAttribute('aria-label');
    expect(homeAria).toBe(firstAria);
  });
});

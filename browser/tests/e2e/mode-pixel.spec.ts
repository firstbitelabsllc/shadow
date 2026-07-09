import { test, expect, type Page } from '@playwright/test';

// V-PIXEL — Simple ↔ Advanced mode smoke (Vidux UI only).
// Opt-in: `npm run test:pixel` (NOT part of `npm run test:thin`).
// Annotation FAB + read-aloud player were removed from the main shell;
// this suite covers mode toggle, advanced tabs, and soft layout only.

async function openFirstPlan(page: Page) {
  const sidebarToggle = page.locator('#sidebar-toggle');
  if (await sidebarToggle.isVisible()) {
    await sidebarToggle.click();
    await expect(page.locator('#sidebar')).toHaveClass(/is-open/);
  }
  await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().waitFor();
  await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().click();
  if (await sidebarToggle.isVisible()) {
    await expect(sidebarToggle).toHaveAttribute('aria-expanded', 'false');
  }
}

test.describe('Simple ↔ Advanced mode pixel/contract smoke', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('defaults to Simple: no advanced chrome, mode toggle idle', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row').first().waitFor();

    await expect(page.locator('html')).not.toHaveClass(/advanced-mode/);
    expect(await page.evaluate(() => localStorage.getItem('vidux:advancedMode'))).not.toBe('1');

    const toggle = page.locator('#mode-toggle');
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveText('Advanced');
    await expect(toggle).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('#sort')).toBeHidden();
    await expect(page.locator('.sidebar-filter-chips')).toBeHidden();

    // Main shell no longer mounts operator FAB / read-aloud footer.
    await expect(page.locator('#root-annotation-toggle')).toHaveCount(0);
    await expect(page.locator('#readaloud-player')).toHaveCount(0);

    await openFirstPlan(page);
    await expect(page.locator('.pane-tabs button', { hasText: 'Decision Log' })).toBeVisible();
    await expect(page.locator('.pane-tabs button', { hasText: 'Sessions' })).toHaveCount(0);
    await expect(page.locator('.pane-tabs button', { hasText: 'Ledger' })).toHaveCount(0);

    const boxes = await page.evaluate(() => {
      const box = (sel: string) => {
        const el = document.querySelector(sel);
        if (!el) throw new Error(`missing ${sel}`);
        const r = el.getBoundingClientRect();
        return { top: r.top, bottom: r.bottom, right: r.right, width: r.width };
      };
      return {
        topbar: box('.topbar'),
        pane: box('#pane'),
        bodyW: document.documentElement.clientWidth,
        scrollW: document.documentElement.scrollWidth,
      };
    });
    expect(boxes.topbar.bottom).toBeLessThan(boxes.pane.bottom);
    expect(boxes.scrollW).toBeLessThanOrEqual(boxes.bodyW + 1);
    expect(boxes.topbar.right).toBeLessThanOrEqual(boxes.bodyW + 1);
  });

  test('toggle Advanced shows advanced tabs and persists', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row').first().waitFor();

    await page.locator('#mode-toggle').click();
    await expect(page.locator('html')).toHaveClass(/advanced-mode/);
    await expect(page.locator('#mode-toggle')).toHaveText('Simple');
    await expect(page.locator('#mode-toggle')).toHaveAttribute('aria-pressed', 'true');
    expect(await page.evaluate(() => localStorage.getItem('vidux:advancedMode'))).toBe('1');
    await expect(page.locator('#sort')).toBeVisible();
    await expect(page.locator('.sidebar-filter-chips')).toBeVisible();

    // Still no FAB/player after Advanced — they were deleted, not mode-gated.
    await expect(page.locator('#root-annotation-toggle')).toHaveCount(0);
    await expect(page.locator('#readaloud-player')).toHaveCount(0);

    await openFirstPlan(page);
    await expect(page.locator('.pane-tabs button', { hasText: 'Decision Log' })).toBeVisible();
    await expect(page.locator('.pane-tabs button', { hasText: 'Sessions' })).toBeVisible();
    await expect(page.locator('.pane-tabs button', { hasText: 'Ledger' })).toBeVisible();

    await page.reload();
    await page.locator('#sidebar-list .plan-row').first().waitFor();
    await expect(page.locator('html')).toHaveClass(/advanced-mode/);
    await expect(page.locator('#mode-toggle')).toHaveText('Simple');
  });

  test('drop to Simple while on advanced-only Sessions tab snaps to PLAN.md', async ({ page }) => {
    await page.goto('/');
    await page.locator('#mode-toggle').click();
    await expect(page.locator('html')).toHaveClass(/advanced-mode/);
    await openFirstPlan(page);

    await page.locator('.pane-tabs button', { hasText: 'Sessions' }).click();
    await expect(page.locator('.pane-tabs button.is-active', { hasText: 'Sessions' })).toBeVisible();

    await page.locator('#mode-toggle').click();
    await expect(page.locator('html')).not.toHaveClass(/advanced-mode/);
    await expect(page.locator('#mode-toggle')).toHaveText('Advanced');
    expect(await page.evaluate(() => localStorage.getItem('vidux:advancedMode'))).toBe('0');

    await expect(page.locator('.pane-tabs button', { hasText: 'Decision Log' })).toBeVisible();
    await expect(page.locator('.pane-tabs button.is-active', { hasText: 'PLAN.md' })).toBeVisible();
  });
});

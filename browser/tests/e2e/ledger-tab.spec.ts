import { test, expect, type Page } from '@playwright/test';

// The Ledger is the owner's protected telemetry surface. It used to be gated
// behind advanced mode, which meant deleting advanced mode would silently make
// it unreachable — and nothing in the suite noticed (mutating the tabs array to
// drop the Ledger left e2e, vitest and the python suite entirely green).
//
// These specs are that missing tripwire. They pin two separate lines:
//   1. the tab-list composition (Ledger is offered in SIMPLE mode)
//   2. the leaving-advanced snap-back guard (Ledger is not an advanced-only tab
//      any more, so dropping to Simple must NOT kick the user off it)
// Reverting either one turns one of these red.

const PLAN = '/?plan=proj-alpha%2FPLAN.md';

async function openDrawerIfNeeded(page: Page) {
  const toggle = page.locator('#sidebar-toggle');
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true') {
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  }
}

async function closeDrawerIfOpen(page: Page) {
  const toggle = page.locator('#sidebar-toggle');
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') === 'true') {
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  }
}

// On narrow viewports #mode-toggle is hidden and the only mode control lives
// inside the drawer — which then overlays the tab strip. Close it again, or
// the very next tab click is intercepted and times out.
async function clickModeToggle(page: Page) {
  const topbar = page.locator('#mode-toggle');
  if (await topbar.isVisible()) {
    await topbar.click();
    return;
  }
  await openDrawerIfNeeded(page);
  await page.locator('#sidebar-mode-toggle').click();
  await closeDrawerIfOpen(page);
}

test.describe('Ledger tab is reachable in simple mode', () => {
  test('simple mode offers the Ledger tab and still hides Sessions', async ({ page }) => {
    await page.goto(PLAN);

    // Positive control: prove the plan pane actually rendered its tab strip
    // before asserting anything about Ledger. Without this a fixture/selector
    // mistake is indistinguishable from a genuine "Ledger is missing" red.
    await expect(page.locator('[data-tab="PLAN.md"]')).toBeVisible();
    await expect(page.locator('[data-tab="Decision Log"]')).toBeVisible();

    // Default is Simple — no advanced-mode class on <html>.
    await expect(page.locator('html')).not.toHaveClass(/advanced-mode/);

    // The protected telemetry surface is offered without opting into advanced.
    await expect(page.locator('[data-tab="Ledger"]')).toBeVisible();

    // Sessions stays gated — this promotion is Ledger-only. If someone
    // promotes the whole advanced tab pair, this fails.
    await expect(page.locator('[data-tab="Sessions"]')).toHaveCount(0);
  });

  test('the Ledger tab actually renders its panel in simple mode', async ({ page }) => {
    await page.goto(PLAN);
    await expect(page.locator('html')).not.toHaveClass(/advanced-mode/);

    await page.locator('[data-tab="Ledger"]').click();

    await expect(page.locator('[data-tab="Ledger"]')).toHaveClass(/is-active/);
    // renderLedgerPanel emits .ledger-panel for both the populated and the
    // "no activity ledger found" states, so this holds on a bare fixture.
    await expect(page.locator('.ledger-panel')).toBeVisible();
  });

  test('leaving advanced mode does not kick the user off the Ledger tab', async ({ page }) => {
    await page.goto(PLAN);

    await clickModeToggle(page);
    await expect(page.locator('html')).toHaveClass(/advanced-mode/);

    await page.locator('[data-tab="Ledger"]').click();
    await expect(page.locator('[data-tab="Ledger"]')).toHaveClass(/is-active/);

    // Back to Simple. The old snap-back guard treated Ledger as advanced-only
    // and force-reset activeTab to PLAN.md here.
    await clickModeToggle(page);
    await expect(page.locator('html')).not.toHaveClass(/advanced-mode/);

    await expect(page.locator('[data-tab="Ledger"]')).toHaveClass(/is-active/);
    await expect(page.locator('.ledger-panel')).toBeVisible();
    await expect(page.locator('[data-tab="PLAN.md"]')).not.toHaveClass(/is-active/);
  });
});

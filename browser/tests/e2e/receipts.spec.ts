import { test, expect } from '@playwright/test';

async function waitForFixtureCorpus(page) {
  const health = await page.request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  const payload = await health.json();
  expect(payload.receipt_corpus_path).toContain('browser/tests/fixtures/receipts/corpus.jsonl');
  await expect(page.locator('#list-status')).toHaveText('loaded 0');
  await expect(page.locator('#grid .card')).toHaveCount(0);
}

// Round-3 open-source panel finding (accessibility lens): receipts.html's
// corpus status filter chips were plain <span> elements with click-only
// handlers -- no tabindex, no role, no keydown handler -- so a keyboard-only
// or screen-reader user could not reach or activate them at all (WCAG 2.1.1
// Level A failure). Fixed by making them real <button> elements, which are
// natively focusable and natively fire click on both Enter and Space.

test.describe('receipts corpus filter accessibility', () => {
  test('filter chips are real buttons, keyboard-focusable and keyboard-activatable', async ({ page }) => {
    await page.goto('/static/receipts.html');
    await waitForFixtureCorpus(page);

    const tagName = await page.locator('#chip-stub').evaluate(el => el.tagName);
    expect(tagName).toBe('BUTTON');

    const stubChip = page.locator('#chip-stub');
    await stubChip.focus();
    await expect(stubChip).toBeFocused();

    await page.keyboard.press('Enter');
    await expect(stubChip).toHaveClass(/active/);
    await expect(page.locator('#chip-all')).not.toHaveClass(/active/);
  });

  // Round-4 panel finding (accessibility lens, non-blocking): the button
  // conversion above fixed keyboard reachability but never set aria-pressed,
  // unlike the identical toggle-chip pattern in sidebar-filters.js's
  // syncButtons(). Screen readers had no way to announce which filter was
  // currently selected.
  test('filter chips announce pressed state via aria-pressed', async ({ page }) => {
    await page.goto('/static/receipts.html');
    await waitForFixtureCorpus(page);

    await expect(page.locator('#chip-all')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#chip-stub')).toHaveAttribute('aria-pressed', 'false');

    await page.locator('#chip-stub').click();

    await expect(page.locator('#chip-stub')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#chip-all')).toHaveAttribute('aria-pressed', 'false');
  });
});

test.describe('receipt image access boundary', () => {
  const publicRow = {
    id: 'lan-public-row',
    name: 'Public lunch receipt',
    private: false,
    image_path: 'images/lan-public-row.png',
    annotations: { tags: ['lunch'] },
    expected: null,
  };

  test('LAN state is visible and never requests host-only pixels', async ({ page }) => {
    let imageRequests = 0;
    await page.setViewportSize({ width: 320, height: 900 });
    await page.route('**/api/receipts/list', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        count: 1,
        rows: [publicRow],
        image_access: { available: false, policy: 'loopback_only' },
      }),
    }));
    await page.route('**/api/receipts/lan-public-row/image', route => {
      imageRequests += 1;
      return route.fulfill({ status: 500, body: 'must not be requested' });
    });

    await page.goto('/static/receipts.html');

    await expect(page.locator('#image-access-banner')).toBeVisible();
    await expect(page.locator('#image-access-banner')).toContainText('Receipt photos stay on the host');
    await expect(page.locator('.pixel-guard')).toHaveText('Photo available on the host only');
    await expect(page.locator('img.thumb')).toHaveCount(0);
    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(widths.content).toBeLessThanOrEqual(widths.viewport);
    expect(imageRequests).toBe(0);
  });

  test('loopback state keeps stored photos available', async ({ page }) => {
    let imageRequests = 0;
    await page.route('**/api/receipts/list', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        count: 1,
        rows: [publicRow],
        image_access: { available: true, policy: 'loopback_only' },
      }),
    }));
    await page.route('**/api/receipts/lan-public-row/image', route => {
      imageRequests += 1;
      const pixel = Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        'base64',
      );
      return route.fulfill({ status: 200, contentType: 'image/png', body: pixel });
    });

    await page.goto('/static/receipts.html');

    await expect(page.locator('#image-access-banner')).toBeHidden();
    await expect(page.locator('img.thumb')).toHaveAttribute('src', '/api/receipts/lan-public-row/image');
    await expect.poll(() => imageRequests).toBe(1);
    await expect(page.locator('.pixel-guard')).toHaveCount(0);
  });
});

import { test, expect } from '@playwright/test';

// Round-3 open-source panel finding (accessibility lens): receipts.html's
// corpus status filter chips were plain <span> elements with click-only
// handlers -- no tabindex, no role, no keydown handler -- so a keyboard-only
// or screen-reader user could not reach or activate them at all (WCAG 2.1.1
// Level A failure). Fixed by making them real <button> elements, which are
// natively focusable and natively fire click on both Enter and Space.

test.describe('receipts corpus filter accessibility', () => {
  test('filter chips are real buttons, keyboard-focusable and keyboard-activatable', async ({ page }) => {
    await page.goto('/static/receipts.html');
    await page.waitForSelector('#chip-stub');

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
    await page.waitForSelector('#chip-stub');

    await expect(page.locator('#chip-all')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#chip-stub')).toHaveAttribute('aria-pressed', 'false');

    await page.locator('#chip-stub').click();

    await expect(page.locator('#chip-stub')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#chip-all')).toHaveAttribute('aria-pressed', 'false');
  });
});

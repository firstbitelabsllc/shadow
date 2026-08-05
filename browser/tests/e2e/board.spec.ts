import { expect, test } from '@playwright/test';

test('board groups plans into entity lanes with counts only and stays read-only', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Board', exact: true }).click();
  const board = page.locator('#board');
  await expect(board.locator('.lane-title', { hasText: 'snowcubes' })).toBeVisible();
  await expect(board.locator('.lane-title', { hasText: 'demo' })).toBeVisible();
  const gift = board.locator('.board-card', { hasText: 'Gift flow live' });
  await expect(gift.locator('.mode-chip')).toHaveText('close');
  await expect(gift.locator('.board-milestone')).toHaveText('Gift flow live on storefront');
  await expect(gift.locator('.meter-count')).toHaveText('Checkpoints 1/3');
  const interactive = await board.locator('button:not(.board-card), a, input, select, textarea').count();
  expect(interactive).toBe(0);
  const raw = await board.textContent();
  expect(raw).not.toContain('npm run');
  expect(raw).not.toContain('/Users/');
});

test('selecting a card opens its brief', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Board', exact: true }).click();
  await page.locator('.board-card', { hasText: 'Gift flow live' }).click();
  await expect(page.locator('#board')).toBeHidden();
  await expect(page.locator('#main')).toContainText('Gifting works end to end');
});

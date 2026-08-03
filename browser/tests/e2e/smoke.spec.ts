import { expect, test } from '@playwright/test';

test('briefs the person and records one honest A/B/C choice', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Pilot Puppy');
  await expect(page.getByRole('heading', { name: 'Pilot Puppy' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Publish release notes people can trust.' })).toBeVisible();
  await expect(page.getByRole('button', { name: /A Ship now/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /B Run a cold review/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /C Hold the release/ })).toBeVisible();
  await page.getByRole('button', { name: /B Run a cold review/ }).click();
  await expect(page.getByText('Choice received locally. Your coding host still needs to apply it.')).toBeVisible();
});

test('exposes proof without implementation machinery', async ({ page }) => {
  await page.goto('/');
  await page.getByText('See proof').click();
  await expect(page.getByText('Browser contract tests pass.')).toBeVisible();
  await expect(page.getByText('tests/test_browser.py')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('provider');
  await expect(page.locator('body')).not.toContainText('transcript');
});

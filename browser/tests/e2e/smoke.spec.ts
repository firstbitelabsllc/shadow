import { expect, test } from '@playwright/test';

test('briefs the person and records one honest choice', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Shadow');
  await expect(page.getByRole('heading', { name: 'Shadow', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Publish release notes people can trust.' })).toBeVisible();
  await expect(page.getByText('Now', { exact: true })).toBeVisible();
  await expect(page.getByText('Change', { exact: true })).toBeVisible();
  await expect(page.getByText('Choose what happens next', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /A Ship now/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /B Run a cold review/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /C Hold the release/ })).toBeVisible();
  await page.getByRole('button', { name: /B Run a cold review/ }).click();
  await expect(page.getByText('Choice saved. Nothing starts until you ask.')).toBeVisible();
});

test('exposes proof without implementation machinery', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Proof', { exact: true }).click();
  await expect(page.getByText('Browser contract tests pass.')).toBeVisible();
  await expect(page.getByText('tests/test_browser.py')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('provider');
  await expect(page.locator('body')).not.toContainText('transcript');
});

test('explains its help in everyday language', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('How Shadow can help')).toBeVisible();
  await expect(page.getByText('Think it through')).toBeVisible();
  await expect(page.getByText('Make a small change')).toBeVisible();
  await expect(page.getByText('Fix something broken')).toBeVisible();
  await expect(page.getByText('Take on a hard build')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('planner');
  await expect(page.locator('body')).not.toContainText('hard-dev');
});

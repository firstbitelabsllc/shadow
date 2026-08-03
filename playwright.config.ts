import { defineConfig, devices } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const PORT = process.env.PILOT_PUPPY_TEST_PORT ?? String(7400 + (process.pid % 1000));
process.env.PILOT_PUPPY_TEST_PORT = PORT;
const LIVE_ROOT = resolve('.pilot-puppy-test', `root-${PORT}-${process.pid}`);
process.env.PILOT_PUPPY_TEST_DEV_ROOT = LIVE_ROOT;
mkdirSync(LIVE_ROOT, { recursive: true });

export default defineConfig({
  testDir: 'browser/tests/e2e',
  globalSetup: 'browser/tests/e2e/global-setup.ts',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['html']] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'], viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `python3 browser/server.py --no-open --root ${JSON.stringify(LIVE_ROOT)} --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});

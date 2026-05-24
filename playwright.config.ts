import { defineConfig, devices } from '@playwright/test';

// Playwright config for vidux-browser e2e + visual smoke. The webServer
// directive boots browser/server.py against a fixture root + ephemeral port
// so tests are hermetic — they don't scan the contributor's real
// ~/Development/. The argparse flags added in commit 5ac7327 make this work.
//
// Visual regression is Linux-only (font hinting diverges between macOS and
// Ubuntu; snapshots flap otherwise). Local Mac runs skip visual specs by
// default; CI on Linux runs them.

const PORT = process.env.VIDUX_TEST_PORT ?? '7291';
const isMac = process.platform === 'darwin';

export default defineConfig({
  testDir: 'browser/tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html']] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'ipad-portrait',
      use: { ...devices['Desktop Chrome'], viewport: { width: 800, height: 1100 } },
    },
    {
      name: 'iphone-portrait',
      use: { ...devices['iPhone 14'], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: `python3 browser/server.py --root browser/tests/fixtures/fake-dev-root --port ${PORT} --comments-path browser/tests/fixtures/comments.jsonl`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  // Visual specs are gated by env — skip on Mac (font drift), enable in CI.
  // To force visuals locally: `PLAYWRIGHT_RUN_VISUAL=1 npm run test:e2e`.
  grepInvert: (!process.env.CI && isMac && !process.env.PLAYWRIGHT_RUN_VISUAL) ? /@visual/ : undefined,
});

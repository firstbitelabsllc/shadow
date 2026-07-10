import { test, expect, type Page } from '@playwright/test';

async function openDrawerIfNeeded(page: Page) {
  const toggle = page.locator('#sidebar-toggle');
  if (await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true') {
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  }
}

async function expandGroup(page: Page, name: string) {
  await openDrawerIfNeeded(page);
  const button = page.locator('.repo-disclosure', { hasText: name }).first();
  await button.waitFor();
  if (await button.getAttribute('aria-expanded') !== 'true') {
    await button.click();
  }
  await expect(page.locator('.repo-disclosure', { hasText: name }).first()).toHaveAttribute('aria-expanded', 'true');
}

async function expandProjectGroups(page: Page) {
  await openDrawerIfNeeded(page);
  const names = await page.locator('.repo-disclosure').allTextContents();
  for (const raw of names) {
    const name = raw.replace(/[▾▸]/g, '').replace(/\d+\s*$/, '').trim();
    if (name && name !== 'artifacts' && name !== 'recently viewed') {
      await expandGroup(page, name);
    }
  }
}

async function toggleAdvanced(page: Page) {
  const topbar = page.locator('#mode-toggle');
  if (await topbar.isVisible()) {
    await topbar.click();
  } else {
    await openDrawerIfNeeded(page);
    await page.locator('#sidebar-mode-toggle').click();
  }
  await expect(page.locator('html')).toHaveClass(/advanced-mode/);
}

async function visibleThemeToggle(page: Page) {
  const topbar = page.locator('#theme-toggle');
  if (await topbar.isVisible()) return topbar;
  await openDrawerIfNeeded(page);
  return page.locator('#sidebar-theme-toggle');
}

// Hermetic smoke specs — talk to the fixture-root server booted by
// playwright.config.ts. They prove: server boots, html renders, sidebar
// populates from fixtures, filter narrows results, sidebar sort/chips persist,
// theme toggle works, and the accessibility attrs added in commits 6d9066b
// + 4f7edde are present in the live DOM.

test.describe('vidux-browse smoke', () => {
  test('server health returns ok', async ({ request }) => {
    const res = await request.get('/api/health');
    expect(res.ok()).toBeTruthy();
  });

  test('GET / renders topbar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.topbar h1')).toHaveText('Vidux');
  });

  test('simple mode leads with inspectable mission proof and opens its plan', async ({ page }) => {
    await page.goto('/');

    const mission = page.locator('.mission-control');
    await expect(mission).toBeVisible();
    await expect(mission.locator('h2')).toHaveText(
      'Prove the browser leads with one evidence-backed mission.',
    );
    await expect(mission.locator('.mission-metric.status-winning')).toHaveCount(1);
    await expect(mission.locator('.mission-metric.status-losing')).toHaveCount(1);
    await expect(mission.locator('.mission-scorecard-tally')).toHaveAttribute(
      'aria-label',
      '1 winning, 1 losing, 0 unproven',
    );
    await expect(mission.locator('.mission-metric .mission-proof-link')).toHaveCount(2);
    await expect(mission.locator('.mission-details .mission-proof-link')).toHaveCount(1);
    await expect(mission.locator('.freshness-fresh')).toContainText('fresh');
    await expect(page.locator('.dashboard-panel')).toHaveCount(0);

    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(widths.content).toBeLessThanOrEqual(widths.viewport);

    await mission.locator('.mission-open-plan').click();
    await expect(page).toHaveURL(/plan=proj-alpha%2FPLAN\.md/);
    await expect(page.locator('.pane-header h2')).toHaveText('proj-alpha');
  });

  test('mission proof opens the validated evidence file', async ({ page }) => {
    await page.goto('/');
    await page.locator('.mission-proof-link').first().click();
    await expect(page).toHaveURL(/tab=EVD%3A/);
    await expect(page.locator('.pane-header h2')).toHaveText('proj-alpha');
    await expect(page.locator('#md-body')).toContainText('Mission Control Proof');
  });

  test('core app zones remain present without FAB/player chrome', async ({ page }) => {
    await page.goto('/');
    const sidebarToggle = page.locator('#sidebar-toggle');
    await openDrawerIfNeeded(page);
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().click();
    if (await sidebarToggle.isVisible()) {
      await expect(sidebarToggle).toHaveAttribute('aria-expanded', 'false');
    }
    await expect(page.locator('[data-vidux-zone="status-header"]')).toBeVisible();
    await expect(page.locator('[data-vidux-zone="content-pane"]')).toBeVisible();
    await expect(page.locator('[data-vidux-zone="mode-detail"]')).toBeVisible();
    // Deleted from main shell (2026-07).
    await expect(page.locator('#root-annotation-toggle')).toHaveCount(0);
    await expect(page.locator('#readaloud-player')).toHaveCount(0);
    await expect(page.locator('[data-vidux-zone="floating-action"]')).toHaveCount(0);
    await expect(page.locator('[data-vidux-zone="footer-player"]')).toHaveCount(0);

    const zones = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return {
        header: root.getPropertyValue('--z-header').trim(),
        popover: root.getPropertyValue('--z-mode-popover').trim(),
      };
    });
    expect(Number(zones.header)).toBeLessThan(Number(zones.popover));

    const boxes = await page.evaluate(() => {
      function box(selector: string) {
        const el = document.querySelector(selector);
        if (!el) throw new Error(`missing ${selector}`);
        const rect = el.getBoundingClientRect();
        return {
          top: rect.top,
          right: rect.right,
          bottom: rect.bottom,
          left: rect.left,
          width: rect.width,
          height: rect.height,
        };
      }
      return {
        header: box('[data-vidux-zone="status-header"]'),
        pane: box('[data-vidux-zone="content-pane"]'),
        bodyWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      };
    });
    expect(boxes.pane.bottom).toBeGreaterThan(boxes.header.bottom);
    expect(boxes.scrollWidth).toBeLessThanOrEqual(boxes.bodyWidth);
  });

  test('Cmd/Ctrl+Shift+C starts annotation capture without FAB', async ({ page }) => {
    await page.goto('/');
    const sidebarToggle = page.locator('#sidebar-toggle');
    await openDrawerIfNeeded(page);
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().click();
    if (await sidebarToggle.isVisible()) {
      await expect(sidebarToggle).toHaveAttribute('aria-expanded', 'false');
    }
    await expect(page.locator('[data-comment-empty]')).toContainText('Cmd/Ctrl+Shift+C');
    await page.keyboard.press('Control+Shift+C');
    await expect(page.locator('body')).toHaveClass(/is-annotation-mode/);
    await page.locator('.pane-header h2').click();
    await expect(page.locator('#annotation-popover')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#annotation-popover')).toHaveCount(0);
    await expect(page.locator('body')).not.toHaveClass(/is-annotation-mode/);
  });

  test('project navigator indexes fixture plans and expands them on demand', async ({ page }) => {
    await page.goto('/');
    await openDrawerIfNeeded(page);
    await expect(page.locator('#sidebar-list .repo-disclosure')).toHaveCount(3);
    await expect(page.locator('.plan-row[title="proj-alpha/PLAN.md"]')).toBeVisible();
    await expect(page.locator('.plan-row[title="proj-beta/PLAN.md"]')).toHaveCount(0);

    await expandGroup(page, 'proj-beta');
    await expect(page.locator('.plan-row[title="proj-beta/PLAN.md"]')).toBeVisible();
  });

  test('filter narrows the sidebar', async ({ page }) => {
    await page.goto('/');
    await openDrawerIfNeeded(page);
    await page.locator('#sidebar-list .repo-disclosure').first().waitFor();
    const before = await page.locator('#sidebar-list .repo-disclosure').count();
    await page.locator('#filter').fill('alpha');
    // give the filter a beat to re-render
    await page.waitForTimeout(150);
    const after = await page.locator('#sidebar-list .repo-disclosure').count();
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThanOrEqual(1);
  });

  test('sidebar sort menu orders by ETA and persists', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().waitFor();
    await expect(page.locator('#sort')).toBeHidden();
    await toggleAdvanced(page);
    await expect(page.locator('#sort')).toBeVisible();
    await expect(page.locator('#sort')).toHaveValue('mtime');
    await page.locator('#sort').selectOption('eta');
    await expect(page.locator('#sidebar-list .repo-disclosure').first()).toContainText('proj-beta');
    await expect(page.locator('#sort')).toHaveValue('eta');
    await expect(page.locator('#sort option')).toHaveText(['Recently updated', 'ETA', 'Status']);

    await page.reload();
    await expect(page.locator('#sort')).toHaveValue('eta');
    await expect(page.locator('#sidebar-list .repo-disclosure').first()).toContainText('proj-beta');
    expect(await page.evaluate(() => localStorage.getItem('vidux:sidebar-sort'))).toBe('eta');
  });

  test('filter chips narrow by ETA and persist', async ({ page }) => {
    await page.goto('/');
    await toggleAdvanced(page);
    const groups = page.locator('#sidebar-list .repo-disclosure');
    await groups.first().waitFor();
    const before = await groups.count();
    expect(before).toBeGreaterThanOrEqual(3);

    const etaChip = page.locator('[data-filter-chip="eta"]');
    await etaChip.click();
    await expect(etaChip).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.repo-disclosure', { hasText: 'proj-gamma' })).toHaveCount(0);
    const after = await groups.count();
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThanOrEqual(1);

    await page.reload();
    await expect(page.locator('[data-filter-chip="eta"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('.repo-disclosure', { hasText: 'proj-gamma' })).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('vidux:sidebar-filter-chips'))).toBe('["eta"]');
  });

  test('plan rows are native links with useful accessible names', async ({ page }) => {
    await page.goto('/');
    const first = page.locator('#sidebar-list .plan-row[data-kind="plan"]').first();
    await first.waitFor();
    expect(await first.evaluate(el => el.tagName)).toBe('A');
    await expect(first).toHaveAttribute('href', /plan=/);
    await expect(first).not.toHaveAttribute('role', 'option');
    const aria = await first.getAttribute('aria-label');
    expect(aria).toBeTruthy();
    expect(aria!.length).toBeGreaterThan(5);
  });

  test('project navigator uses native nav semantics instead of a mixed listbox', async ({ page }) => {
    await page.goto('/');
    const nav = page.locator('#sidebar-list');
    await nav.locator('.plan-row').first().waitFor();
    expect(await nav.evaluate(el => el.tagName)).toBe('NAV');
    await expect(nav).not.toHaveAttribute('role', 'listbox');
    await expect(nav.locator('[role="option"]')).toHaveCount(0);
  });

  test('collapse-group headers are keyboard-operable (WCAG 2.1.1)', async ({ page }) => {
    // Round-3 readiness panel finding (accessibility lens): the "repo-group"
    // collapse/expand headers were mouse-only -- no tabindex, no role, no
    // keydown handler -- despite toggling visible content.
    await page.goto('/');
    await openDrawerIfNeeded(page);
    const header = page.locator('#sidebar-list .repo-disclosure').first();
    await header.waitFor();
    expect(await header.evaluate(el => el.tagName)).toBe('BUTTON');
    const expandedBefore = await header.getAttribute('aria-expanded');
    await header.focus();
    await page.keyboard.press('Enter');
    // renderSidebar() rebuilds the list on toggle, so re-query rather than
    // reuse the stale `header` locator handle.
    const headerAfter = page.locator('#sidebar-list .repo-disclosure').first();
    await expect(headerAfter).toHaveAttribute('aria-expanded', expandedBefore === 'true' ? 'false' : 'true');
  });

  test('skip-link is present and anchors to #pane', async ({ page }) => {
    await page.goto('/');
    const link = page.locator('a.skip-link');
    await expect(link).toHaveText('Skip to content');
    await expect(link).toHaveAttribute('href', '#pane');
  });

  test('theme toggle cycles light/dark and persists', async ({ page, context }) => {
    await page.goto('/');
    const btn = await visibleThemeToggle(page);
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
    await expandProjectGroups(page);
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
    await expandProjectGroups(page);
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

test.describe('auto-refresh polling', () => {
  test('polls comments, task stats, and artifact content without losing selection', async ({ page }) => {
    // Round-10 panel finding: a 200ms interval made this reliably flaky
    // under Playwright's fullyParallel:true (all 3 projects contending for
    // CPU) -- the comment-marker click below adds a transient
    // .is-anchor-highlight class synchronously, but AUTO_REFRESH_INTERVAL_MS
    // is read once at module load and drives an unconditional
    // window.setInterval(autoRefreshTick, ...) with no busy/interaction
    // guard, so any poll tick that lands between the click and the
    // assertion re-renders .pane-header h2 from scratch and wipes the
    // class. 1000ms gives the click a far wider safe gap to be observed in
    // (Playwright's own assertion polling is near-instant) while still
    // comfortably firing within the propagation checks' timeouts below.
    await page.addInitScript(() => {
      (window as any).__VIDUX_AUTO_REFRESH_INTERVAL_MS = 1000;
    });

    let completedTasks = 0;
    let artifactBody = '<!doctype html><html><body><main><h1 id="artifact-title">artifact version A</h1><button id="artifact-action">Inspect</button></main></body></html>';
    let comments: Array<Record<string, unknown>> = [];

    const planPath = '/tmp/vidux-auto-refresh/PLAN.md';
    const inboxPath = '/tmp/vidux-auto-refresh/INBOX.md';
    const artifactPath = '/tmp/vidux-auto-refresh/artifact.html';

    await page.route('**/api/plans', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          plans: [{
            repo: 'fixture',
            slug: 'auto-refresh',
            rel: 'fixture/auto-refresh/PLAN.md',
            path: planPath,
            status: 'active',
            age_days: 0,
            size: 512,
            siblings: ['INBOX.md'],
            investigations: [],
            children: [],
            task_stats: {
              total: 2,
              counts: { completed: completedTasks, pending: 2 - completedTasks },
            },
            aggregate_stats: {
              total: 2,
              descendants: 0,
              counts: { completed: completedTasks, pending: 2 - completedTasks },
            },
          }],
        }),
      });
    });

    await page.route('**/api/artifacts', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          artifacts: [{
            slug: 'live-artifact',
            title: 'Live Artifact',
            path: artifactPath,
            age_days: 0,
            size: artifactBody.length,
          }],
          artifacts_dir: '/tmp/vidux-auto-refresh',
        }),
      });
    });

    await page.route('**/api/file**', async route => {
      const url = new URL(route.request().url());
      const target = url.searchParams.get('path');
      if (target === artifactPath) {
        await route.fulfill({ contentType: 'text/html', body: artifactBody });
        return;
      }
      if (target === inboxPath) {
        await route.fulfill({ contentType: 'text/plain', body: '# Inbox\n\nAuto-refresh tab fixture.' });
        return;
      }
      await route.fulfill({
        contentType: 'text/plain',
        body: `# Auto Refresh\n\n## Tasks\n- [completed] Done ${completedTasks}\n- [pending] Pending\n`,
      });
    });

    await page.route('**/api/comments**', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ comments }),
      });
    });

    await page.goto('/?plan=fixture%2Fauto-refresh%2FPLAN.md&tab=INBOX.md');
    await expect(page.locator('.pane-tabs button.is-active')).toHaveText('INBOX.md');
    await expect(page.locator('.pane-progress .ratio')).toHaveText('0 of 2 tasks');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-scope', 'current-view');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-state', 'ready');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-count', '0');
    await expect(page.locator('[data-comment-empty]')).toContainText('No comments yet.');
    await expect(page.locator('[data-comment-filter="all"]')).toHaveClass(/is-active/);
    await expect(page.locator('#comment-target-map')).toHaveAttribute('data-comment-target-count', '0');

    completedTasks = 1;
    comments = [
      {
        id: 'c1',
        author: 'Test',
        body: 'poll-loaded comment',
        created_at: '2026-05-24T12:00:00Z',
        anchor: { label: 'Inbox heading', selector: '.pane-header h2' },
      },
      {
        id: 'c2',
        author: 'Test',
        body: 'same target comment',
        created_at: '2026-05-24T12:01:00Z',
        anchor: { label: 'Inbox heading', selector: '.pane-header h2' },
      },
      {
        id: 'c3',
        author: 'Test',
        body: 'tab target comment',
        created_at: '2026-05-24T12:02:00Z',
        anchor: { label: 'Tab strip', selector: '.pane-tabs' },
      },
    ];

    await expect(page.locator('.pane-progress .ratio')).toHaveText('1 of 2 tasks', { timeout: 5_000 });
    await expect(page.locator('#comments-panel')).toHaveClass(/has-comments/);
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-count', '3');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-target-count', '2');
    await expect(page.locator('#comment-count')).toHaveText('3 comments');
    await expect(page.locator('#comment-list')).toContainText('poll-loaded comment');
    await expect(page.locator('#comment-list')).toContainText('same target comment');
    await expect(page.locator('#comment-target-map')).toHaveAttribute('data-comment-target-count', '2');
    await expect(page.locator('#comment-target-map')).toContainText('Inbox heading');
    await expect(page.locator('[data-comment-marker][data-comment-marker-count="2"]')).toBeVisible();
    await expect(page.locator('[data-comment-marker][data-comment-marker-count="1"]')).toBeVisible();
    await page.locator('[data-comment-marker][data-comment-marker-count="2"]').hover();
    await expect(page.locator('.pane-header h2')).toHaveClass(/is-anchor-preview/);
    await page.locator('[data-comment-marker][data-comment-marker-count="2"]').click();
    await expect(page.locator('.pane-header h2')).toHaveClass(/is-anchor-highlight/);
    await page.waitForTimeout(1_600);
    await page.locator('[data-comment-jump="c1"]').click();
    await page.waitForTimeout(800);
    await expect(page.locator('.pane-header h2')).toHaveClass(/is-anchor-highlight/);
    await page.locator('#comment-markers-toggle').click();
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-markers-hidden', 'true');
    await expect(page.locator('[data-comment-marker]')).toHaveCount(0);
    await expect(page.locator('#comment-markers-toggle')).toHaveText('Show');
    await page.locator('#comment-markers-toggle').click();
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-markers-hidden', 'false');
    await expect(page.locator('[data-comment-marker][data-comment-marker-count="2"]')).toBeVisible();
    await page.locator('[data-comment-jump="c1"]').click();
    await expect(page.locator('.pane-header h2')).toHaveClass(/is-anchor-highlight/);
    await expect(page.locator('.pane-tabs button.is-active')).toHaveText('INBOX.md');

    comments = [{
      id: 'a1',
      author: 'Test',
      body: 'artifact target comment',
      created_at: '2026-05-24T12:03:00Z',
      anchor: { label: 'Artifact title', selector: '#artifact-title' },
    }];

    const sidebarToggle = page.locator('#sidebar-toggle');
    await expandGroup(page, 'artifacts');
    const artifactRow = page.locator('#sidebar-list .plan-row[data-kind="artifact"]').first();
    await artifactRow.click();
    const activeArtifactRow = page.locator('#sidebar-list .plan-row[data-kind="artifact"].is-active').first();
    await expect(activeArtifactRow).toHaveClass(/is-active/);
    if (await sidebarToggle.isVisible()) {
      await expect(sidebarToggle).toHaveAttribute('aria-expanded', 'false');
    }
    await expect(page.frameLocator('iframe.artifact-frame').locator('body')).toContainText('artifact version A');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-target-count', '1');
    await expect(page.locator('#comment-target-map')).toContainText('Artifact title');
    await expect(page.locator('[data-comment-marker][data-comment-marker-count="1"]')).toBeVisible();
    await page.locator('[data-comment-marker][data-comment-marker-count="1"]').click();
    await expect(page.frameLocator('iframe.artifact-frame').locator('#artifact-title')).toHaveClass(/is-anchor-highlight/);

    artifactBody = '<!doctype html><html><body><main><h1 id="artifact-title">artifact version B</h1><button id="artifact-action">Inspect</button></main></body></html>';

    await expect(page.frameLocator('iframe.artifact-frame').locator('body')).toContainText('artifact version B', { timeout: 5_000 });
    await expect(page.locator('#sidebar-list .plan-row[data-kind="artifact"].is-active').first()).toBeVisible();
  });
});

test.describe('artifact styling', () => {
  test('shared artifact base css applies in dark iframe render', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });

    const artifactPath = '/tmp/vidux-artifact-base-css/a/very/long/local/artifact/path/that/should/wrap/in/the/pane/header/instead/of/forcing/mobile-horizontal-overflow/artifact.html';
    const artifactBody = `<!doctype html>
<html>
<head>
  <style>
    :root { --paper: #faf8f5; --ink: #2d231c; }
    body { margin: 0; background: var(--paper); color: var(--ink); }
  </style>
  <link rel="stylesheet" href="../static/artifact-base.css" data-vidux-artifact-base>
</head>
<body><main>shared artifact theme</main></body>
</html>`;

    await page.route('**/api/artifacts', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          artifacts: [{
            slug: 'shared-theme-artifact',
            title: 'Shared Theme Artifact',
            path: artifactPath,
            age_days: 0,
            size: artifactBody.length,
          }],
          artifacts_dir: '/tmp/vidux-artifact-base-css',
        }),
      });
    });

    await page.route('**/api/file**', async route => {
      const url = new URL(route.request().url());
      if (url.searchParams.get('path') === artifactPath) {
        await route.fulfill({ contentType: 'text/html', body: artifactBody });
        return;
      }
      await route.fallback();
    });

    await page.route('**/api/comments**', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ comments: [] }),
      });
    });

    await page.goto('/');
    await expandGroup(page, 'artifacts');
    await page.locator('#sidebar-list .plan-row[data-kind="artifact"]').click();
    const body = page.frameLocator('iframe.artifact-frame').locator('body');
    await expect(body).toContainText('shared artifact theme');
    await expect.poll(async () => (
      body.evaluate(el => getComputedStyle(el).backgroundColor)
    )).toBe('rgb(29, 25, 22)');
    const paneMetrics = await page.locator('#pane').evaluate(el => ({
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
    }));
    expect(paneMetrics.scrollWidth).toBeLessThanOrEqual(paneMetrics.clientWidth);
  });

  for (const width of [320, 375, 390, 414]) {
    test(`mobile shell stays one row at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto('/');
      const topbar = await page.locator('.topbar').boundingBox();
      expect(topbar).not.toBeNull();
      expect(topbar!.height).toBeLessThanOrEqual(64);
      await expect(page.locator('#mode-toggle')).toBeHidden();
      await expect(page.locator('#theme-toggle')).toBeHidden();
      await expect(page.locator('#sidebar-toggle')).toBeVisible();
      await expect(page.locator('#refresh')).toBeVisible();
    });
  }

  // Round-3 panel finding: the round-1 topbar-wrap fix above made .topbar
  // grow taller at <=540px (up to 3 wrapped rows), but .sidebar's mobile
  // drawer kept a hardcoded `top: 77px` sized for the old single-row height
  // -- so opening the drawer at these widths rendered its own search/sort/
  // filter controls completely hidden underneath the topbar. Fixed via a
  // ResizeObserver-synced --topbar-rendered-height custom property instead of
  // another hardcoded constant (a magic-number offset here has now broken
  // twice from unrelated topbar content changes). Covers widths where the
  // topbar wraps differently (3 rows, 2 rows, 1 row) to catch the offset
  // going stale at any of them, not just the narrowest.
  for (const width of [375, 414, 540, 768]) {
    test(`mobile drawer search input is not hidden under the topbar at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await page.goto('/');
      const toggle = page.locator('#sidebar-toggle');
      if (await toggle.isVisible()) {
        await toggle.click();
      }
      const topbarBox = await page.locator('.topbar').boundingBox();
      const searchBox = await page.locator('#filter').boundingBox();
      expect(topbarBox).not.toBeNull();
      expect(searchBox).not.toBeNull();
      if (topbarBox && searchBox) {
        expect(searchBox.y).toBeGreaterThanOrEqual(topbarBox.y + topbarBox.height);
      }
    });
  }

  test('mobile drawer is inert while closed and restores focus on Escape', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    const toggle = page.locator('#sidebar-toggle');
    const sidebar = page.locator('#sidebar');

    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(sidebar).toHaveAttribute('aria-hidden', 'true');
    await expect(sidebar).toHaveAttribute('inert', '');

    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(sidebar).toHaveAttribute('aria-hidden', 'false');
    await expect(page.locator('#filter')).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(sidebar).toHaveAttribute('inert', '');
    await expect(toggle).toBeFocused();
  });

  test('mobile selection closes the drawer and keeps mission proof first', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    const toggle = page.locator('#sidebar-toggle');
    await toggle.click();
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('#sidebar')).toHaveAttribute('inert', '');

    await page.goto('/');
    await expect(page.locator('.mission-control')).toBeVisible();
    await expect(page.locator('.mission-next')).toBeVisible();
    await expect(page.locator('.mission-scorecard')).toBeVisible();
    await expect(page.locator('.mission-details')).toBeVisible();
    const positions = await page.evaluate(() => {
      const top = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().top;
      return {
        next: top('.mission-next'),
        results: top('.mission-scorecard'),
        details: top('.mission-details'),
      };
    });
    expect(positions.next).toBeLessThan(positions.results);
    expect(positions.results).toBeLessThan(positions.details);
  });
});

test.describe('subplan row keyboard navigation', () => {
  // Rounds 8/9/10: tests/test_browser_server.py's
  // test_subplan_row_is_keyboard_and_screen_reader_accessible only greps
  // app.js source text for role="button"/tabindex="0"/aria-label/keydown --
  // it never opens a page, focuses a node, or dispatches a keypress, so it
  // would not catch a broken/misattached handler. Reuses this file's own
  // proven idioms: the page.route() mocking pattern from "auto-refresh
  // polling"/"artifact styling" (never touches the shared fixture root,
  // which several count/sort/filter tests elsewhere depend on staying flat
  // at exactly 3 plans) and the focus()+keyboard.press('Enter') pattern
  // from "collapse-group headers are keyboard-operable" above. Mocks one
  // parent plan with one child (mirrors real attach_children()/child_rels
  // wiring: the child is both a flat state.plans entry and named in the
  // parent's child_rels, which hydratePlanChildren() on the client resolves
  // into plan.children for renderPaneSubplans()).
  test('Enter on a focused .subplan-row navigates to the child plan', async ({ page }) => {
    const parentPath = '/tmp/vidux-subplan-nav/parent/PLAN.md';
    const childPath = '/tmp/vidux-subplan-nav/child/PLAN.md';
    const parentRel = 'fixture/subplan-parent/PLAN.md';
    const childRel = 'fixture/subplan-child/PLAN.md';

    const planFor = (over: Record<string, unknown>) => ({
      repo: 'fixture',
      status: 'active',
      age_days: 0,
      size: 256,
      siblings: [],
      investigations: [],
      evidence: [],
      child_rels: [],
      task_stats: { total: 1, counts: { completed: 0, pending: 1 } },
      aggregate_stats: { total: 1, descendants: 0, counts: { completed: 0, pending: 1 } },
      ...over,
    });

    await page.route('**/api/plans', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          plans: [
            planFor({
              slug: 'subplan-parent', rel: parentRel, path: parentPath,
              child_rels: [childRel],
            }),
            planFor({ slug: 'subplan-child', rel: childRel, path: childPath }),
          ],
        }),
      });
    });

    await page.route('**/api/artifacts', async route => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ artifacts: [], artifacts_dir: '/tmp/vidux-subplan-nav' }),
      });
    });

    await page.route('**/api/file**', async route => {
      const url = new URL(route.request().url());
      const target = url.searchParams.get('path');
      const label = target === childPath ? 'Child' : 'Parent';
      await route.fulfill({
        contentType: 'text/plain',
        body: `# ${label}\n\n## Tasks\n- [pending] Do: something\n`,
      });
    });

    await page.route('**/api/comments**', async route => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ comments: [] }) });
    });

    await page.goto(`/?plan=${encodeURIComponent(parentRel)}`);
    const row = page.locator('.subplan-row[data-subplan-rel="' + childRel + '"]');
    await expect(row).toHaveAttribute('role', 'button');
    await expect(row).toHaveAttribute('tabindex', '0');
    await row.focus();
    await page.keyboard.press('Enter');

    await expect(page).toHaveURL(new RegExp(`plan=${encodeURIComponent(childRel).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
    await expect(page.locator('.pane-header h2')).toHaveText('fixture · subplan-child');
    await expect(page.locator('#sidebar-list .plan-row[data-path="' + childPath + '"].is-active').first()).toBeVisible();
  });
});

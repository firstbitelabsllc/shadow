import { test, expect } from '@playwright/test';

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
    await expect(page.locator('.topbar h1')).toHaveText('vidux browser');
  });

  test('core app zones remain present without FAB/player chrome', async ({ page }) => {
    await page.goto('/');
    const sidebarToggle = page.locator('#sidebar-toggle');
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).toHaveClass(/is-open/);
    }
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().click();
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).not.toHaveClass(/is-open/);
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

  test('sidebar lists plans from fixture root', async ({ page }) => {
    await page.goto('/');
    const rows = page.locator('#sidebar-list .plan-row');
    await expect(rows.first()).toBeVisible({ timeout: 5_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(2);
  });

  test('filter narrows the sidebar', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row').first().waitFor();
    const before = await page.locator('#sidebar-list .plan-row').count();
    await page.locator('#filter').fill('alpha');
    // give the filter a beat to re-render
    await page.waitForTimeout(150);
    const after = await page.locator('#sidebar-list .plan-row').count();
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThanOrEqual(1);
  });

  test('sidebar sort menu orders by ETA and persists', async ({ page }) => {
    await page.goto('/');
    await page.locator('#sidebar-list .plan-row[data-kind="plan"]').first().waitFor();
    await expect(page.locator('#sort')).toHaveValue('mtime');
    await page.locator('#sort').selectOption('eta');
    await expect(page.locator('#sidebar-list .plan-row[data-kind="plan"]').first()).toHaveAttribute('title', /proj-beta/);
    await expect(page.locator('#sort')).toHaveValue('eta');
    await expect(page.locator('#sort option')).toHaveText(['mtime', 'ETA', 'status']);

    await page.reload();
    await expect(page.locator('#sort')).toHaveValue('eta');
    await expect(page.locator('#sidebar-list .plan-row[data-kind="plan"]').first()).toHaveAttribute('title', /proj-beta/);
    expect(await page.evaluate(() => localStorage.getItem('vidux:sidebar-sort'))).toBe('eta');
  });

  test('filter chips narrow by ETA and persist', async ({ page }) => {
    await page.goto('/');
    const sidebarToggle = page.locator('#sidebar-toggle');
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).toHaveClass(/is-open/);
    }
    const rows = page.locator('#sidebar-list .plan-row[data-kind="plan"]');
    await rows.first().waitFor();
    const before = await rows.count();
    expect(before).toBeGreaterThanOrEqual(3);

    const etaChip = page.locator('[data-filter-chip="eta"]');
    await etaChip.click();
    await expect(etaChip).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#sidebar-list .plan-row[title="proj-gamma"]')).toHaveCount(0);
    const after = await rows.count();
    expect(after).toBeLessThan(before);
    expect(after).toBeGreaterThanOrEqual(1);

    await page.reload();
    await expect(page.locator('[data-filter-chip="eta"]')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('#sidebar-list .plan-row[title="proj-gamma"]')).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('vidux:sidebar-filter-chips'))).toBe('["eta"]');
  });

  test('plan-row has WCAG attrs (tabindex, role, aria-label)', async ({ page }) => {
    await page.goto('/');
    const first = page.locator('#sidebar-list .plan-row').first();
    await first.waitFor();
    await expect(first).toHaveAttribute('tabindex', '0');
    await expect(first).toHaveAttribute('role', 'option');
    const aria = await first.getAttribute('aria-label');
    expect(aria).toBeTruthy();
    expect(aria!.length).toBeGreaterThan(5);
  });

  test('plan-rows use a roving tabindex (exactly one tab stop)', async ({ page }) => {
    // Round-3 readiness panel finding (accessibility lens): every sidebar
    // row carried tabindex="0", violating the ARIA APG single-tab-stop
    // listbox pattern (Tab should stop once for the whole list; arrow keys
    // move within it). Exactly one row may be a tab stop at a time.
    await page.goto('/');
    const rows = page.locator('#sidebar-list .plan-row');
    await rows.first().waitFor();
    const tabbable = page.locator('#sidebar-list .plan-row[tabindex="0"]');
    await expect(tabbable).toHaveCount(1);
  });

  test('collapse-group headers are keyboard-operable (WCAG 2.1.1)', async ({ page }) => {
    // Round-3 readiness panel finding (accessibility lens): the "repo-group"
    // collapse/expand headers were mouse-only -- no tabindex, no role, no
    // keydown handler -- despite toggling visible content.
    await page.goto('/');
    const header = page.locator('#sidebar-list .repo-group[data-collapse-key] h2').first();
    await header.waitFor();
    await expect(header).toHaveAttribute('tabindex', '0');
    await expect(header).toHaveAttribute('role', 'button');
    const expandedBefore = await header.getAttribute('aria-expanded');
    await header.focus();
    await page.keyboard.press('Enter');
    // renderSidebar() rebuilds the list on toggle, so re-query rather than
    // reuse the stale `header` locator handle.
    const headerAfter = page.locator('#sidebar-list .repo-group[data-collapse-key] h2').first();
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
    const btn = page.locator('#theme-toggle');
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
    await page.addInitScript(() => {
      (window as any).__VIDUX_AUTO_REFRESH_INTERVAL_MS = 200;
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
    await expect(page.locator('[data-comment-empty]')).toHaveText('No comments yet.');
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

    await expect(page.locator('.pane-progress .ratio')).toHaveText('1 of 2 tasks', { timeout: 3_000 });
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
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).toHaveClass(/is-open/);
    }
    const artifactRow = page.locator('#sidebar-list .plan-row[data-kind="artifact"]').first();
    await artifactRow.click();
    await expect(page.locator('#sidebar-list .plan-row[data-kind="artifact"].is-active').first()).toBeVisible();
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).not.toHaveClass(/is-open/);
    }
    await expect(page.frameLocator('iframe.artifact-frame').locator('body')).toContainText('artifact version A');
    await expect(page.locator('#comments-panel')).toHaveAttribute('data-comment-target-count', '1');
    await expect(page.locator('#comment-target-map')).toContainText('Artifact title');
    await expect(page.locator('[data-comment-marker][data-comment-marker-count="1"]')).toBeVisible();
    await page.locator('[data-comment-marker][data-comment-marker-count="1"]').click();
    await expect(page.frameLocator('iframe.artifact-frame').locator('#artifact-title')).toHaveClass(/is-anchor-highlight/);

    artifactBody = '<!doctype html><html><body><main><h1 id="artifact-title">artifact version B</h1><button id="artifact-action">Inspect</button></main></body></html>';

    await expect(page.frameLocator('iframe.artifact-frame').locator('body')).toContainText('artifact version B', { timeout: 3_000 });
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
    const sidebarToggle = page.locator('#sidebar-toggle');
    if (await sidebarToggle.isVisible()) {
      await sidebarToggle.click();
      await expect(page.locator('#sidebar')).toHaveClass(/is-open/);
    }
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
});

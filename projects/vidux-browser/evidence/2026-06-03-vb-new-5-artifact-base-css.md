# VB-NEW-5 Artifact Base CSS Proof

## Scope

- Shipped `browser/static/artifact-base.css` as the shared dark-mode token layer for local HTML artifacts.
- Updated the current local Snowcubes artifact shelf to link `../static/artifact-base.css` once per artifact and removed copied `prefers-color-scheme` blocks.
- Documented the shared-link contract in `README.md` and `docs/reference/browser.md`.
- Added host CSS wrapping for long artifact metadata paths after live mobile proof caught a narrow pane overflow.

## Changed Files

- `browser/static/artifact-base.css`
- `browser/static/style.css`
- `browser/tests/e2e/smoke.spec.ts`
- `tests/test_browser_server.py`
- `README.md`
- `docs/reference/browser.md`
- Local ignored runtime artifacts under `browser/artifacts/snowcubes-*.html`

## Local Artifact Audit

The Snowcubes artifact files are ignored local runtime files (`browser/artifacts/*`), so this audit is the durable proof for their migration.

Command:

```bash
rg -n "prefers-color-scheme" browser/artifacts/snowcubes-*.html || true
python3 - <<'PY'
from pathlib import Path
for path in sorted(Path('browser/artifacts').glob('snowcubes-*.html')):
    text = path.read_text()
    print(f"{path}: link_count={text.count('data-vidux-artifact-base')} old_dark={'prefers-color-scheme' in text}")
PY
```

Result:

- `rg` returned no matches.
- 9 current `snowcubes-*.html` files reported `link_count=1 old_dark=False`.

## Mechanical Proof

```bash
python3 -m unittest tests.test_browser_server
npm run test:js
npm run docs:build
npm run test:e2e -- --grep "artifact styling"
npm run test:e2e
```

Results:

- `tests.test_browser_server`: 59 tests passed.
- `npm run test:js`: 7 Vitest tests passed.
- `npm run docs:build`: VitePress build passed.
- Focused artifact styling Playwright: 3/3 passed across desktop, iPad, and iPhone.
- Full Playwright smoke: 39/39 passed.

## Live Browser Proof

Live target:

```text
http://127.0.0.1:7191/?artifact=snowcubes-tabling
```

Proof artifacts:

- `projects/vidux-browser/evidence/2026-06-03-vb-new-5-artifact-base-css-live-proof.json`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-5-artifact-base-css-desktop-dark.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-new-5-artifact-base-css-mobile-dark.png`

Live proof summary:

- `/static/artifact-base.css` fetched with HTTP 200 on desktop and mobile.
- Artifact iframe body background resolved to `rgb(29, 25, 22)` in dark mode.
- Artifact iframe text color resolved to `rgb(239, 231, 218)` in dark mode.
- Artifact iframe had exactly 1 `link[data-vidux-artifact-base]`.
- Artifact iframe had no copied `prefers-color-scheme` block.
- Desktop and mobile had 0 console errors, 0 page errors, and 0 `.error` boxes.
- Desktop page/pane/iframe horizontal overflow checks passed.
- Mobile page/pane/iframe horizontal overflow checks passed (`paneScrollWidth=390`, `paneClientWidth=390`; iframe `scrollWidth=356`, `clientWidth=356`).

## Non-Claims

- This does not regenerate artifacts automatically when source plans change; that remains `VB-NEW-6`.
- The fixed read-aloud footer still exists as a separate app-action-layer behavior; this slice only ensured the artifact styling proof and pane overflow checks are clean.
- The ignored local artifact shelf is migrated on this machine, but only tracked files plus this evidence travel in git by default.

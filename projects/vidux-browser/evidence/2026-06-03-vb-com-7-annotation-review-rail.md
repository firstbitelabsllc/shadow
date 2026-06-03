# VB-COM-7 Annotation Review Rail

Task: `VB-COM-7 Annotation drawer / review rail`.

## Changed

- Added `browser/static/comment-rail.js`, loaded before `app.js`, as the named renderer for comment count, empty state, comment rows, anchor target buttons, steering styling, and compact current-view labels.
- Reworked the existing comments readback surface into `comments-panel annotation-review-rail` with `data-comment-scope="current-view"`, `data-comment-state`, `data-comment-count`, and `data-active-filter="all"` state.
- Added a compact filter row with `All`, `Open`, and `Mine` slots. `All` is active now; `Open` and `Mine` are disabled placeholders for the future filter work without requiring plan/artifact source edits.
- Kept the composer independent: the inline popover still handles writing; the rail only reads and jumps to comment targets.
- Moved the old inline row rendering out of `app.js`, keeping `browser/static/app.js` under the prior 100k byte budget.

## Proof

- `node --check browser/static/app.js` PASS.
- `node --check browser/static/comment-rail.js` PASS.
- Focused annotation review rail static contract PASS.
- Focused auto-refresh/comment Playwright PASS, 3/3 across desktop, iPad, and iPhone profiles.
- `python3 -m unittest tests.test_browser_server` PASS, 62/62.
- `npm run test:js` PASS, 7/7.
- `npm run docs:build` PASS.
- `npx playwright test` PASS, 45/45.
- Publish scrutiny PASS, `ready=true`.
- Publish ledger: `evt_vidux_publish_70785e3ba64c` at `/Users/leokwan/.agent-ledger/activity.jsonl:6116`.
- Size check: `browser/static/app.js` is 99,720 bytes; `browser/static/comment-rail.js` is 2,406 bytes.

## Live 7191 Proof

Live target: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fvidux-browser%2FPLAN.md`.

Live proof JSON:
- `projects/vidux-browser/evidence/2026-06-03-vb-com-7-annotation-review-rail-live-proof.json`

Observed live rail state:
- Empty state: `data-comment-state=ready`, `data-comment-count=0`, count text `0 comments`, empty text `No comments yet.`, active filter `All`, disabled future filters `Open` and `Mine`.
- Loaded state: `data-comment-state=ready`, `data-comment-count=2`, `has-comments=true`, count text `2 comments`, two `Target` buttons, and target jump highlighted `.pane-header h2`.
- Mobile state: viewport `390/844`, document `scrollWidth=390`, rail width `358`, rail bottom `635`, read-aloud footer top `734`.
- Browser proof had `commentPosts=0`, console errors `[]`, page errors `[]`, and request failures `[]`.

Screenshots:
- `projects/vidux-browser/evidence/2026-06-03-vb-com-7-annotation-review-rail-empty.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-com-7-annotation-review-rail-desktop.png`
- `projects/vidux-browser/evidence/2026-06-03-vb-com-7-annotation-review-rail-mobile.png`

## Non-Claims

- No real comments, plans, artifacts, LaunchAgents, local-CI lanes, external services, stage, commit, push, PR, or release were mutated.
- No anchor markers/count badges, target map, reply/resolve lifecycle model, visual-state harness, or Storybook work shipped in this slice.

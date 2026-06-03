# C86 Action Locks And Run Control

Date: 2026-05-25

## Scope

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`

## What Changed

- Added a first-viewport `Action Locks` model for read-only refresh, foreground execute launches, local-CI cancel, and local-CI resume availability.
- Changed `Refresh all` into a read-only operator refresh with its own `operatorRefreshStatus`, so it does not claim the global foreground execution slot.
- Added a latest FirstBite `Run Control` panel that separates run terminal state, rerunnable lanes, report artifact, and resume-action availability.
- Tightened resume selection so pass, warning, and planned lanes stay untouched; only non-passing terminal states can be selected by resume.
- Added visible button titles/disabled reasons for `Resume Dry`, `Resume Run`, and primary control rows.

## Verification

- `npx tsc --noEmit --pretty false` passed in `/Users/leokwan/Development/moussey`.
- `node --test --import tsx app/api/coding/local-ci/cancel/route.test.ts app/api/coding/local-ci/resume/route.test.ts app/api/coding/local-ci/run/route.test.ts lib/local-ci-status.test.ts` passed 39/39 in `/Users/leokwan/Development/moussey`.
- `npm run build` passed in `/Users/leokwan/Development/moussey` with the known Turbopack/NFT warning for `app/api/coding/local-ci/artifact/route.ts`.
- Production standalone server proof ran at `http://127.0.0.1:4324/coding`.
- Playwright desktop proof found `Action Locks`, `Run Control`, enabled read-only `Refresh all`, disabled `Resume Dry` / `Resume Run` with the no-non-passing-lanes reason, and no horizontal overflow (`1440/1440`).
- Playwright mobile proof found the same control model and no horizontal overflow (`390/390`).
- Follow-up LaunchAgent proof on the durable local port returned `200 text/html; charset=utf-8` for `http://127.0.0.1:4321/coding?fresh=c86-action-locks`, and Playwright CLI desktop/mobile screenshots waited for `Action Locks` before capture.

## Artifacts

- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-first-viewport.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-run-control-element.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-run-control-viewport.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-mobile-first-viewport.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-mobile-run-control-viewport.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-action-locks-desktop.png`
- `projects/agentic-coding-workbench/evidence/2026-05-25-c86-action-locks-mobile.png`

## Remaining UX Debt

- The lower-page model/debug/tooling controls still need the same disabled-state explanation contract.
- Mobile is usable and overflow-free, but still feels like a tall operations wall. The next UI slice should tighten mobile section sequencing and left-rail behavior.
- The completed-run model still needs to unify terminal runs, active reservations, resumable reports, and replay-only proofs into one clearer pipeline view.

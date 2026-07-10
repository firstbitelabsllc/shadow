# Multi-Project Onboarding Receipt

Date: 2026-07-10
Status: SHIPPING
Plan row: 6.0.3

## Claim

Vidux now gives a first-time operator a concrete, path-safe route from a folder of Git projects to a useful cockpit:

- The browser inventories direct-child Git repositories and plan-connected projects without returning filesystem paths in the onboarding payload.
- `vidux init --here` creates a cockpit-ready PLAN.md in the current repository and refuses to overwrite an existing plan.
- A generated plan includes an Operator Brief, honest unproven scorecard, bounded first task, decision, and progress checkpoint.
- Current work is ranked by declared priority. Equal highest priorities are shown as an explicit conflict with the deterministic fallback, not silently presented as settled authority.

This receipt does not claim Vidux beats direct Claude or Codex. Verified net-win scenario classes remain 0, and benchmark v2 remains blocked on an independent fixture release.

## Product Changes

- `browser/server.py`: path-free project inventory, onboarding state, deterministic authority metadata, and accurate selection reasons.
- `browser/static/onboarding.js`: escaped first-run and authority-conflict rendering in a small independently tested module.
- `browser/static/app.js` and `browser/static/style.css`: cockpit integration, responsive setup/tie bands, and a mobile drawer event-bubbling fix found during real interaction proof.
- `scripts/vidux-init.sh` and `bin/vidux`: overwrite-safe `--here` initialization while preserving legacy slug initialization; an existing or dangling PLAN.md symlink is refused before redirection.
- `README.md` and public references: one recommended first-run command and scan-root fallback.

## Mechanical Proof

Focused red/green floor:

```text
python3 -m unittest tests.test_vidux_init tests.test_browser_server.BrowserPlanDiscoveryTests tests.test_browser_server.BrowserDashboardTests
PASS - 29 tests

npm run test:js
PASS - 2 files, 11 tests

npx playwright test browser/tests/e2e/smoke.spec.ts --grep "clean first run|tied current-work"
PASS - 6 tests across desktop, iPad, and iPhone
```

Full repository floor:

```text
npm run verify
PASS - 11 JavaScript tests; 825 Python tests, 5 skipped; 386 staged/tracked files scanned by the public-ready gate

npm run test:e2e
PASS - 120/120 Playwright journeys

npm run docs:build
PASS

npm audit --audit-level=high
PASS - 0 vulnerabilities

python3 -m py_compile browser/server.py scripts/vidux-config.py scripts/vidux-benchmark-v2.py browser/receipts/handler.py
bash -n scripts/vidux-init.sh
git diff --check
PASS
```

Remote and runtime proof:

- `git fetch origin main codex/vidux-mission-control-20260709` completed with the branch 0 commits behind `origin/main` and 0 commits behind its remote branch before this commit.
- The persistent 7192 service was restarted. `/api/health` returned `ok=true` with a server mtime matching this checkout.
- Live `/api/plans` reported onboarding `ready`, 49 discovered projects, selected authority for `vidux-main-active`, and no `/Users/` or `/private/` value in the onboarding payload.
- A fresh Chromium load of 7192 rendered one visible mission-control surface with no page errors and no horizontal overflow at 1440x900.
- Both active Vidux mounts resolve to this checkout; `SKILL.md` and `browser/server.py` compare byte-identical, and `validate-skill-sources.py` passed.

## Visual Proof

- `evidence/2026-07-10-multi-project-onboarding-clean.png` - clean 1440x900 light first run; SHA-256 `9fa347a0c2acb3656b9109748a5c7cbdc2ed4ff4b18f840dd5f8ae2392e2e01f`.
- `evidence/2026-07-10-multi-project-onboarding-conflict-mobile-dark.png` - 320x844 dark equal-priority conflict and working plan drawer; SHA-256 `0f4a5ac42a6bab1a6adb6dc0f8e40801cc35336a4d24e107f7ca0d2886bdd775`.

Both receipts were inspected after capture. Text fits, the setup command is legible, the conflict is explicit, and neither viewport overflows.

## Independent Review

- Fable: bounded 180-second read-only decision review exited 124 without a verdict. Recorded as unavailable.
- GLM: bounded 150-second read-only implementation review exited 124 without a verdict. Recorded as unavailable.
- Grok: bounded 150-second read-only adversarial review exited 124 after local plugin/tool bootstrap failures and without a verdict. Recorded as unavailable.
- Codex: adjudication found a dangling-PLAN.md symlink write escape in the initializer, added the refusal regression, and reran the staged full floor. No concrete unfixed blocker remains.

Unavailable sidecars are not passing evidence and do not override the mechanical floor.

## Verdict

Row 6.0.3 is SHIPPING. First-run setup, multi-project visibility, and current-work conflict handling are materially clearer and mechanically covered. Product superiority, token savings, and net value remain unproven until benchmark v2 produces paired native-control results.

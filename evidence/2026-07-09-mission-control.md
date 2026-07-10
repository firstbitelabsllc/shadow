# Mission Control and Focused UX Simplification Receipt

Date: 2026-07-09
Branch: `codex/vidux-mission-control-20260709`
Verdict: **SHIPPING as a product slice. Vidux superiority remains unproven.**

## What Shipped

- `PLAN.md` now carries a compact `Operator Brief` and `Outcome Scorecard` contract.
- The browser parser exposes those fields on each plan and selects mission authority deterministically by priority, modification time, then relative path.
- Simple mode leads with outcome, next move, why now, validation, cost posture, evidence, freshness, and explicit winning/losing states.
- `Open plan` navigates to the owning `PLAN.md` without requiring Advanced mode.
- Missing brief, malformed rows, stale dates, priority clamping, dynamic project counts, HTML escaping, desktop, mobile, light, and dark states have regression coverage.
- The public-ready gate gained a tested `--tracked-only` mode so release proof scans the exact tracked/staged package while its strict default still scans unignored worktree files.

No action endpoint, shell execution, secret access, model call, or remote dispatch path was added. The slice is read-mostly and adds no paid runtime dependency.

## Five-Agent Impeccable Pass

Five independent read-only reviewers audited the same live product from distinct angles: first-time clarity, multi-project resumption, accessibility/mobile, visual craft, and proof/cost trust. Their findings were deduplicated into exactly ten implemented improvements:

1. Derive the displayed verdict from evidence and keep it separate from workflow state.
2. Resolve proof paths safely and expose available, missing, needed, and invalid states as inspectable UI.
3. Replace internal language with plain labels and explicit current-project framing.
4. Give first-run and missing-brief states one contextual action instead of a dead pane or raw path.
5. Keep the phone header to one stable row with fixed-size controls.
6. Put goal, next step, results, and proof before secondary detail on mobile.
7. Make the project drawer inert while closed, focus search when opened, restore focus on Escape, and close after selection.
8. Bound the cross-project home to at most three Resume and three Needs attention items, one per project.
9. Use native navigation links and disclosure buttons, collapse non-current projects initially, and mark current work directly.
10. Remove model-routing/token-spending steering controls from the read-only cockpit; keep diagnostics, sort, sessions, and ledger behind Advanced.

Typography, spacing, honest ETA coverage, and color-state craft were folded through these ten changes rather than counted as extra rows.

## Mechanical Proof

| Command or check | Result |
|---|---|
| `python3 -m py_compile browser/server.py scripts/vidux-public-ready-grep-gate.py` | PASS |
| `node --check browser/static/app.js` | PASS |
| `npm run verify` | PASS: 8 JavaScript tests; 733 Python tests, 5 skipped; public-ready scan passed across 357 tracked files |
| `npm run test:e2e` | PASS: 102 Chromium journeys across desktop, iPad portrait, and iPhone portrait |
| focused auto-refresh selection proof with `--repeat-each=3` | PASS: 9/9 across desktop, iPad portrait, and iPhone portrait after replacing a stale visibility assertion with active-selection state proof |
| `PLAYWRIGHT_RUN_VISUAL=1 npm run test:visual:update` | PASS: 9 local Darwin baselines regenerated and reviewed |
| `PLAYWRIGHT_RUN_VISUAL=1 npx playwright test browser/tests/e2e/visual.spec.ts` | PASS: 9/9 baselines independently rechecked |
| live `/api/health` | PASS |
| live `/api/plans` | PASS: selected the priority-100 Vidux brief and returned three honest scorecard rows (2 losing, 1 unproven) |
| 320px overflow and interaction smoke | PASS: body width matched viewport; mission width remained bounded; `Open plan` remained visible |
| `git diff --check` | PASS |

Browser and visual proof found four concrete defects that source review alone missed: `currentWorkRel` was initialized after recents could render, causing a URL change with a frozen pane; comment markers sat above the phone header and intercepted project-menu clicks; a CSS cascade leaked Advanced quick filters into Simple mode; and the default Playwright worker count overloaded the shared fixture server. All four have regression coverage or a bounded harness configuration. The supported `npm run test:e2e` command now passes without a custom worker flag.

## Visual Receipts

- [Mobile 390px](2026-07-09-mission-control-mobile.png)
- [Missing brief](2026-07-09-mission-control-empty.png)

> Round-11 privacy fix: the desktop, dark-mode, proof-zoom, and
> project-navigator-zoom screenshots were captured against the maintainer's
> real multi-project dev root, so their sidebar/pane pixels exposed the full
> private project fleet (including a family member's personal project) and a
> home-directory-implying worktree name — invisible to the text grep-gate.
> Those four files were removed. The two kept here (mobile, empty state)
> contain no fleet sidebar or private data; the mission-control UI is also
> shown against a synthetic fixture in `2026-07-10-multi-project-onboarding-clean.png`.

## Independent Review

- **Fable advisor:** returned a concrete GO review and the architecture guidance used here (append-only kernel verdict, deterministic selection, freshness, and visible losing/unproven states). The bounded call then exited after reporting a final cost of $3.110748; the advice was complete, and the budget exit is recorded rather than hidden.
- **GLM worker:** two bounded read-only attempts timed out after 121 seconds with zero output. Recorded as sidecar unavailable, not a product failure; no GLM patch was accepted.
- **Grok critic:** `NO BLOCKER FOUND` after checking ranking, scorecard honesty, Simple mode, authority navigation, empty state, escaping, API selection, and screenshots.
- **Codex adjudication:** no concrete unfixed blocker after the source, runtime, accessibility, privacy, cross-browser, and visual gates above.
- **Mount and host routing:** skill mount doctor reported 113 installed skills and zero blockers; host-router doctor reported 16 lanes with source/runtime hash parity.

## Open-Source Boundary

The staged package contains only owned code, tests, public prompt/design guidance, this receipt, and screenshots. The intentionally untracked `evaluations/` copy and the two local July 7 final-verification artifacts were not staged, modified, deleted, archived, or normalized. (Round-11 correction: this section originally claimed "no private machine path or private routing-skill name," but four of the screenshots captured against the real dev root did expose the private fleet sidebar and a home-implying worktree name; those were removed — see the Visual Receipts note above.)

## Value Verdict

This slice proves that Vidux can make durable plan authority, cost posture, evidence, and the next action legible in the first viewport. It does **not** prove that using Vidux beats direct Claude or Codex:

- kernel resolution remains 59% versus 76% for the freeform control;
- cost per resolved task remains $1.78 for Fable freeform plus GLM versus $0.59 for GLM solo;
- verified net-win scenario classes remain 0.

The next blocking proof is benchmark v2: preregister interruption recovery, cross-project prioritization, and proof-inspection scenarios against native Claude/Codex baselines, then measure outcomes, wall time, tokens, dollars, operator touches, and resume loss.

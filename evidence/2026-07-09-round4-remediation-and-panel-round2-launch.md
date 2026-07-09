# Round-4 remediation + panel round-2 launch (2026-07-09)

Follow-on to `2026-07-08-20-agent-open-source-readiness-panel.md`, which explicitly
deferred a round-3 full panel until after the private/public repo-visibility decision.
This round ran anyway (repo stayed private throughout) because the standing directive
is to keep shipping every fixable finding regardless of that open question, and to
re-run the panel to check real progress rather than trust an aging backlog.

## What happened, in order

1. **Ran a fresh 21-lens GO/NO-GO panel** (independent isolated agents, no shared
   context, forced structured verdict). Result: 6/21 GO, 15/21 NO-GO.
2. **Investigated the two loudest P0 claims by direct verification, not by trusting
   the agent text:**
   - "Tests are red on main" — **stale/false**. A concurrent commit had transiently
     broken 8 tests moments before the panel ran; by the time this was checked, HEAD
     had moved on and the suite was fully green.
   - "A second Snap-confidential leak exists" — **true, and worse than scoped**. Broader
     than the two directories the panel named: also present in
     `projects/agentic-5x`, `projects/mom-flushing-home`, `projects/nicole-fpa-ai`,
     `projects/vidux-pilot-merge`, `projects/vidux-self-investigation`, plus scattered
     absolute-path/username/endpoint/private-repo-name strings outside `projects/`
     entirely. Purged via a 3-pass `git filter-repo` (path-purge + two text-replacement
     passes), force-pushed, and independently verified clean via two fresh mirror clones
     taken after GitHub ref propagation settled. Repo stayed **private** throughout —
     no public exposure window existed at any point.
3. **Fixed the real, verifiable P0s from the panel** (PR #1, `696e0b07`):
   three CLI crash bugs (`vidux config check --config <a-directory>`,
   `vidux http-smoke` against a URL with control characters,
   `vidux drift --add-task ""`) each with a regression test, plus ARCHITECTURE.md
   documentation gaps, a dead README reference, and a stale clone URL in
   SETUP_NEW_MACHINE.md.
4. **Fixed 3 more real bugs surfaced by direct code reading against the same panel
   backlog, each as its own PR:**
   - `bin/vidux doctor` resolved `VIDUX_ROOT` correctly but never exported it before
     exec'ing `vidux-doctor-cli.sh`, which falls back to a hardcoded
     `$HOME/Development/vidux` when the env var is absent — silently validating the
     wrong checkout from any non-canonical clone (worktree, differently-named clone,
     CI). (`4725d7a6`)
   - Every write route in `browser/server.py` parsed `Content-Length` with a bare
     `int()` call — a hand-crafted non-numeric header crashed the handler with an
     uncaught `ValueError` (raw connection reset, no HTTP response, traceback to
     server stderr) instead of a clean 400. Extracted a shared `_content_length()`
     helper used at all 8 call sites. (PR #2, `a64f1048`)
   - `ARTIFACTS_DIR` was the only server global with no CLI/env override
     (`HOST`/`PORT`/`DEV_ROOT`/`COMMENTS_FILE` all have one) — hardcoded to
     `<checkout>/browser/artifacts` regardless of `--root`. Found by hand while
     screenshotting the GUI for a design pass: the Artifacts panel leaked this dev
     machine's real personal/business artifact titles instead of the fixture's demo
     data, and this repo's own "hermetic" Playwright `webServer` config had the same
     leak. Added `VIDUX_BROWSER_ARTIFACTS_DIR`/`--artifacts-dir`, wired into
     `playwright.config.ts` against a new empty fixture dir. (PR #3, `69d3a2d1`)
5. **Caught and correctly did NOT ship a false-positive fix**: the inherited backlog
   flagged `"ai": "7.0.0-beta.178"` in `package.json` devDependencies as a dead/stale
   SDK pin (zero direct imports anywhere in source). Before removing it, checked
   `node_modules/eve/package.json` — `eve` (a real, actively-used dependency per
   `agent/agent.ts`) declares `"ai": "7.0.0-beta.178"` as an exact-matching optional
   peerDependency. The pin is deliberate, not orphaned. Reverted the removal before
   committing.
6. **Cross-checked a cached round-2/3-era panel finding** (`privacy-pii-leakage`,
   originally: grep-gate `SCAN_TARGETS` too narrow to see ~76 tracked files leaking
   the repo owner's private home-path and employer-linked path patterns across
   `PLAN.md`, `evidence/`, `prompts/`, `investigations/`, `tests/`) against current
   `main`. **Already fixed**: `python3 scripts/vidux-public-ready-grep-gate.py` now
   passes (205 files scanned, SCAN_TARGETS widened), the employer-linked pattern's
   count is 0, and the only 2 remaining private-home-path hits are benign
   self-references inside the grep-gate's own script comment and its test fixture
   strings — not real leaks.
7. **Verified an "8-widget dashboard" default-view claim from the inherited backlog is
   also stale**: took real Playwright screenshots (fresh incognito contexts, both
   desktop and mobile viewports, zero prior interaction) of the actual running GUI.
   The true default landing state on both viewports is the plain "Select a plan from
   the sidebar" empty state, not an Advanced-mode dashboard. An earlier screenshot
   that appeared to show a dashboard-by-default was an artifact of reusing the same
   browser page after manually clicking the Advanced toggle in the same script run —
   not real product behavior.
8. **Launched a fresh 20-lens panel** (`vidux-releasability-panel-round2`,
   `wf_5cd1ad8a-619`) covering secrets/credentials, PII, license/legal, docs accuracy,
   onboarding, CLI crash-resistance, browser security, Nicole-simplicity GUI
   (screenshot-based), dependency hygiene, test/CI coverage, positioning honesty,
   governance/sustainability, accessibility, naming/trademark, code quality,
   error-message UX, git-history hygiene, stranger-repro, second-order privacy, and
   open-source mechanics — to get a current, trustworthy GO/NO-GO count rather than
   continuing to work off an aging backlog with a proven-high false-positive rate.

## Standing tension, not yet resolved

Several NO-GO verdicts across both panel rounds are structurally about the repo being
unreachable by strangers (fresh-clone buildability, "experienced OSS contributor"
lens, live CI badge honesty) — these cannot resolve to GO while the repo stays
private, which is Leo's separate, explicit standing call. The repo remains **private**
throughout all of this work. A literal "20/20 GO" may be unreachable without either
(a) a visibility decision, or (b) reframing the bar as "would be releasable if
flipped." Not yet raised to Leo as an explicit framing question — deferred until the
round-2 panel count comes back, so the framing question can be asked with a concrete
number attached instead of in the abstract.

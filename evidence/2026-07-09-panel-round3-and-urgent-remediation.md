# Panel round-3 (7/20 GO) + urgent security remediation (2026-07-09)

Follow-on to `2026-07-09-round4-remediation-and-panel-round2-launch.md`, which closed
all 4 round-2 CLI bugs plus the SKILL.md cross-product citation leak. This file covers
the round-3 panel (`wf_c0794906-352`, 20 fresh lenses, run after that remediation) and
the urgent security fixes that followed immediately from its findings.

## Round-3 panel result: 7/20 GO, 13/20 NO-GO

Up from round-2's 6/20 GO, but the composition changed: round-3 used fresh lenses
(fresh-clone-buildability, experienced-oss-contributor, live-ci-badge-honesty,
code-quality-cli-scripts, code-quality-browser-js, security-secrets-leaks,
accessibility, test-suite-trust, dependency-health, docs-readme-accuracy,
contribution-readiness, naming-branding-collision, mobile-responsiveness,
first-run-ux, simplicity-niche-fit, nicole-readability, positioning-honesty,
github-repo-metadata, git-history-exposure, plan-first-doctrine-coherence) rather than
re-running round-2's exact set, so the two counts aren't directly comparable — this
was a genuinely broader sweep, not a re-check of the same 20 questions.

**GO (7):** live-ci-badge-honesty, code-quality-browser-js, test-suite-trust,
dependency-health, contribution-readiness, nicole-readability, positioning-honesty.

**NO-GO (13):** fresh-clone-buildability, experienced-oss-contributor,
code-quality-cli-scripts, security-secrets-leaks, accessibility, docs-readme-accuracy,
naming-branding-collision, mobile-responsiveness, first-run-ux, simplicity-niche-fit,
github-repo-metadata, git-history-exposure, plan-first-doctrine-coherence.

Full per-lens detail lives in the workflow journal (`wf_c0794906-352`); the two
findings below were urgent enough to act on immediately rather than queue.

## URGENT #1 (fixed): confidential job-search POC live on 11 pushed origin branches

`security-secrets-leaks` independently found `projects/leo-ios-nyc-jobhunt-poc/`
(2,411 files) sitting in the tip tree of 11 branches already pushed to
`origin` — `claude/capture-mode-enforce`, `claude/consensus-subtotal-agreement`,
`claude/contract-new-kinds`, `claude/cut-vidux-history-20260614`,
`claude/export-update-path`, `claude/extract-prompt-kinds`, `claude/grounding-veto`,
`claude/receipts-currency-truth`, `claude/receipts-tier2-invariants`,
`claude/receipts-tier3-arbitrate`, `claude/receipts-vision-swap`. Content includes a
real screenshot titled "Nicole Review Hub" (Leo's real spouse, named as a reviewer of
his confidential job-search leads across dozens of filenames) and `report.md` files
documenting live automated Browser-Use sessions against Leo's real, logged-in personal
LinkedIn account. Actual lead data itself was verified fixture/synthetic (gitignored,
never committed) — no third-party PII found — but the spouse's real name and the
scraping-tool evidence are real and would be world-readable the instant repo
visibility flips, no further push needed. `main`/`origin/main` itself was already
clean (`projects/*` blanket-gitignored there).

**Fix:** independently re-verified all 11 branches (`git ls-tree -r` confirmed 2,411
matching files each), spot-checked actual tree content, then deleted all 11 from
origin (`git push origin --delete <branch>`, one per branch). Independently confirmed
none of the repo's 7 live PR refs (`refs/pull/1..7/head`) also carry this content —
verified by fetching each PR ref directly and grepping its tree, zero matches. This
vector is now fully closed on origin.

## URGENT #2 (fixed): real Snap Inc. confidential engineering content in 6 local-only branches

`security-secrets-leaks` and `git-history-exposure` both independently found real
employer-internal content — internal source-control/build/dashboard hostnames,
named coworker handles, live internal PR/Jira ticket numbers, an internal dashboard
naming an in-progress unreleased feature rollout percentage, and Leo's own employer
corporate git identity (email + a corporate-tree absolute path) — sitting in 6
**local-only, never-pushed** branches on this dev machine: `codex/agjh-web-verified-20260625`,
`codex/worktree-gc-detached-pr-head`, `fix/p1-p2-round2-findings`,
`fix/round3-p0-critical`, `fix/round3-p1-backlog`,
`vidux-public-ready-delinear-20260617`.

Independently re-verified: scoped each branch's history against `origin/main`
(`git log <branch> --not origin/main`), found 1,200–2,410 real content-matching hits
per branch (not just author-line matches — spot-checked actual commit bodies, e.g.
`codex/agjh-web-verified-20260625` contains full internal engineering narrative about
Leo's own private automation-skill work, authored from within his employer's corporate
dev tree). Cross-checked `origin/main`'s own author list — clean, always the personal
`leojkwan@gmail.com` identity — confirming this content is anomalous to these 6
branches only, not a repo-wide identity leak. Six other local branches with 1–8
incidental hits were checked and are false positives (matching only the corporate
*author* line on commits that otherwise contain nothing employer-internal — not
remediated, not a real leak).

This is a real employer-confidentiality risk given Leo's day job, made materially
worse by this session's own demonstrated finding (see the companion evidence file's
"concurrent-write discovery" section) that an autonomous `vidux-loop.sh` process can
commit *and push* whatever it finds in this shared checkout without a human in the
loop. Leaving employer-confidential commits sitting as named local branches was a
live, not hypothetical, one-push-away risk.

**Fix:** bundled all 6 branches to `~/Desktop/vidux-snap-confidential-quarantine/*.bundle`
(outside any active git checkout, so nothing is lost), then deleted the local branch
refs (`git branch -D`). **Leo should review the quarantine folder and decide whether
this content belongs in one of his private automation repos (matching the corporate
dev-tree paths found in the commits) or should simply be discarded — not yet asked,
flagging here.** Also strengthened `scripts/vidux-public-ready-grep-gate.py`, whose
existing "employer source path" rule had been over-redacted to a literal placeholder
string that could never match real content (a silent no-op) — it just caught this
exact class of leak live, in this very file, while it was being written.

## Also fixed: a 5th round of the SHA-fingerprint leak, still not fully caught

`git-history-exposure` independently found commit `6cb7c1f6` ("docs: record the git
history purge closure (P0 done) (#205)", from an earlier session) still had the
abbreviated leaked SHA `51c4dbe` in cleartext in its commit body — despite an earlier
same-day pass (`4ca58e0`) claiming to have redacted every SHA fingerprint. That pass
only touched the evidence `.md` file; it missed this separate commit message. Swept
all of `origin/main`'s commit history for the pattern (`\b(51c4dbe[0-9a-f]{0,33}|
fb673ed[0-9a-f]{0,33})\b`) — found exactly this one remaining instance, no others.

**Fix:** same `git filter-repo --message-callback` pattern as the earlier round-4
rewrite, run on a fresh isolated clone (cloned directly from
`git@github.com:firstbitelabsllc/vidux.git`, not the working checkout — matching
`6cb7c1f6`'s own documented practice of isolating rewrites from lanes that might be
concurrently committing). Verified zero remaining matches post-rewrite, ran the full
699-test suite on the rewritten history (green, 5 skips — one more skip than usual,
attributable to the scratch clone lacking a local file some tests conditionally
check, not a regression), force-pushed to `origin/main`, then independently
re-verified via a *second*, separate fresh clone (not the rewrite clone) — zero
matches. Local `main` synced via `git fetch` + `git reset --hard origin/main`.

**Pattern worth naming:** this is the fifth distinct round where a redaction pass
believed itself complete and missed something the next round's fresh eyes caught.
Each round has swept a different surface (blob content, then commit-message text on
one file, then commit-message text repo-wide, then dangling objects, now this). No
single pass should be trusted as final; the round-3 panel's independent
git-history-exposure lens re-litigating "is this actually fixed" rather than trusting
prior evidence-file claims is exactly why it caught this — that pattern (independent
re-verification over trusting a prior write-up) should continue for any future round.

## Remaining round-3 findings, not yet acted on (prioritized for next pass)

**Real functional bugs (user-facing, not just leak-hygiene):**
- `vidux init <slug>` silently writes into the vidux tool's own checkout
  (`~/Development/vidux/projects/<slug>/PLAN.md`) instead of the user's project
  directory, regardless of CWD — contradicts README's stated `inline`/repo-local
  default. `scripts/vidux-init.sh` line 9.
- Mobile nav drawer regression (self-inflicted by the round-2 mobile-header fix):
  `.sidebar { position: fixed; top: 77px; }` is now stale against the round-2 fix's
  taller wrapped `.topbar` (~145.5px at ≤540px), so the drawer's search/sort/filter
  controls render 100% hidden underneath the topbar on iPhone SE/12/13/14 widths.
  `browser/static/style.css` ~line 2133.
- `vidux-worktree-gc.py --apply --yes` silently deletes gitignored, uncommitted files
  with zero warning — `git status --porcelain` and `git worktree remove` both have
  the same gitignore blind spot, so a worktree with e.g. an uncommitted `.env` under a
  gitignored dir is classified `merged_clean` and permanently destroyed. Real data-loss
  footgun in a tool marketed as guarded/safe automation.
- Browser empty-state shows a hardcoded false stat ("40+ PLAN.md files indexed") for
  every genuinely new user (real scan returns 0). `browser/static/app.js`
  `renderEmptyPane()`, `index.html` line 86.
- README Quick Start's `ln -sf .../usr/local/bin/vidux` fails Permission Denied on
  stock macOS (root-owned by default); working PATH-append fallback exists but only
  appears in a later section, not inline.

**Mission-fit gap (closest to Leo's actual stated goal for this whole effort):**
- `simplicity-niche-fit`: plan/task content renders as raw AI-agent-protocol markdown
  verbatim (status FSM tags, Evidence/ETA/Findable annotations) with zero
  task-specific simplification — the "simple enough for someone like Nicole" goal is
  only half-delivered (the completion-bar rollup works, the actual task list doesn't).
  Zero mention of "Nicole" or "non-technical" anywhere in shipped docs; README's own
  comparison framing (LangGraph/CrewAI/Hermes/pgvector) is calibrated for a developer
  evaluating orchestration frameworks. This is flagged again from round-1 — still open.

**Repo hygiene / positioning:**
- Repo root reads as operator scratch space, not a curated OSS repo: `ASK-LEO.md`,
  root `PLAN.md` (Leo's own dense internal roadmap, contradicts README's "one simple
  file" pitch), `SETUP_NEW_MACHINE.md` (orphaned, not linked from any doc). Flagged
  already in round-1 (2026-07-08), still unfixed.
- `vidux` collides with a live commercial product (vidux.ai, 10M+ creators,
  same broad AI-tooling category), the bare npm name is very likely permanently
  blocked (registered-then-unpublished 2022–2023, outside npm's grace window), and
  the GitHub `vidux` handle/several repo names are already taken. This is a strategic
  naming/branding decision, not something to unilaterally act on — flagging for Leo.
- README self-contradicts: claims `/vidux` is the sole entry point while
  `docs/reference/commands.md`, `SKILL.md`, and `commands/vidux-status.md` all
  document a live second command, `/vidux-status`.
- Version badge will render `v2.7.0` (last tag, 2026-04-08) next to a same-day "last
  commit" badge — reads as an abandoned release process. No new tag cut since despite
  ~2.5 months of continued work.
- SKILL.md: hardcoded `origin/master` (line 716) contradicts its own Trunk-First Rule
  a few hundred lines earlier; two unreconciled task-status FSMs in the PLAN.md
  Template section; more unverifiable private-incident citations beyond the two
  already fixed (`music-semantic-backend-mvp.html`, several unlinked numeric claims);
  undefined entity "Fable" cited alongside Claude/GLM/Grok/Codex with no explanation.
- SECURITY.md's "audited clean as of 2026-05-13" claim is now stale — contradicted by
  every remediation round since, including this one.
- Accessibility: `receipts.html`'s corpus filter chips are keyboard-unreachable
  (WCAG 2.1.1 Level A failure) — plain `<span>` with click-only handlers.
- `.github/skills/impeccable/` (2.3MB, active postToolUse git hook) is undocumented
  in any stranger-facing doc — but this was an intentional install per Leo's own
  request earlier this session ("pull down and install impeccable... build out the
  tooling with taste"), so the fix is a doc mention, not removal.

Full detail (including several P2 polish items — broken SUPPORT.md template links,
CODE_OF_CONDUCT's non-existent "confidential report" channel, undeclared Pillow
dependency, unpinned marked.js CDN script, dead annotation-toggle code, a sidebar
race condition on rapid navigation, 3 dev-only npm audit CVEs via vitepress) lives in
the `wf_c0794906-352` workflow journal.

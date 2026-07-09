# Panel round 4: 5/20 GO — independent re-verification of round-3 fixes

Purpose: round 4 was launched specifically to independently re-verify round-3's
remediation claims rather than trust them. Verdict: most round-3 fixes hold up
under adversarial re-check, but two new/escalated findings are P0-severe, and
2 of the 20 lens agents degenerated (did not produce real findings) rather than
genuinely voting NO-GO.

**Result: 5/20 GO, 15/20 NO-GO.** Prior rounds: round 1 (baseline sweep),
round 3 (7/20 GO). This is a lower GO count than round 3, but it reflects a
harder, more skeptical brief ("independently re-verify, don't trust prior
claims") landing more real hits — not regression.

## P0 — highest priority, unresolved

### 1. `refs/pull/*/head` now confirmed to leak a real, named Snap-internal hostname (escalated from round 3's abstract framing)

Two independent lenses (`experienced-oss-contributor`, `git-history-exposure`)
each did a fresh `git clone --bare` (not the working checkout) and confirmed:

- `refs/pull/1/head` through `refs/pull/5/head` are live, GitHub-owned refs on
  `firstbitelabsllc/vidux`. All 7 PRs on this repo are MERGED.
- Commit `baeb3ce7b4d3c054e5093e4871c82ab309db1610` (reachable via PRs #1-#5)
  has a commit message containing, in cleartext, a real internal Snap-hosted
  endpoint hostname (same class as the `redacted-internal-endpoint` finding
  below) — not an abstract "SHA fingerprint."
- `51c4dbe`/`fb673ed` (the file content itself) are confirmed genuinely purged
  from every live ref, local and remote — the round-3 content purge was real.
- But 3 *other* commits still carry the leaked-SHA text in commit-message
  bodies across the PR refs: `6cb7c1f` (pr/6, pr/7), `9b44e4e` (pr/1-5),
  `baeb3ce7` (pr/1-5, same commit as the P0 above).
- Root cause: round 3's redaction sweep was explicitly scoped to
  `origin/main`'s history (per `evidence/2026-07-09-panel-round3-and-urgent-remediation.md:104`)
  and never touched `refs/pull/*/head`, which GitHub creates and retains
  permanently, independent of base-branch history rewrites. Force-pushing
  `main` cannot fix this.
- This is reachable two ways with zero special access: `git fetch origin
  refs/pull/N/head`, and GitHub's own web "Commits" tab on any of the 5
  merged PRs — the second path needs no git CLI at all, and activates the
  instant repo visibility flips to public.

**This is a repeat of the same "redaction pass believed itself complete" miss
that has now recurred 6 times per the round-3 evidence file's own count.**

**Decision needed from Leo, not delegable:** whether to close this
permanently via a full repo recreation (fresh history, no PR refs to carry
forward) vs. attempt further surgical redaction that has already failed
5-6 times running. I am not making this call. Flagging it here with the
concrete, now-named severity because the abstract framing in earlier evidence
files undersold it.

### 2. `scripts/vidux-worktree-gc.py` — data-loss bug in the NEW ignored-file guard itself

`worktree-gc-correctness` lens, reproduced live in an isolated scratch repo:

- `non_regenerable_ignored_paths()` only ever sees the single collapsed
  top-level line git's `--ignored` (traditional mode) emits for a wholly
  ignored directory — it can't see inside it. So any hand-authored file
  living inside a gitignored dir that happens to share a name with a
  common build-tool convention (`build/`, `dist/`, `target/`, `vendor/`,
  `node_modules/`, `.venv/`, etc. — all ~13 in `REGENERABLE_IGNORED_DIR_NAMES`)
  is treated as fully safe regardless of actual contents. Reproduced: created
  `build/client-handoff-notes.txt` with irreplaceable text in a merged
  worktree, ran the real script with `--apply --yes`, it deleted the whole
  worktree with zero warning. This is exactly the blind spot the module's own
  header comment says it exists to close — it doesn't close it for this case.
- Separately: `.DS_Store` in `REGENERABLE_IGNORED_FILE_SUFFIXES` is dead code
  — `Path('.DS_Store').suffix == ''`, not `.DS_Store` — so it can never match.
  Net effect is the opposite direction (over-blocks, not data-loss): every
  worktree ever opened in macOS Finder is permanently misclassified `dirty`
  and blocked from legitimate auto-cleanup.
- `tests/test_worktree_gc.py`'s existing coverage exercises neither gap.

### 3. `playwright.config.ts`'s `webServer.reuseExistingServer` (test-suite-trust lens, carried from round-4 read before this checkpoint)

Silently attaches to any already-listening process on the configured port
with zero identity verification — can leak real private local dev-tree data
into "hermetic" fixture test runs. Contradicts the suite's own documented
hermeticity claim. Not yet remediated.

## P1 — concrete, fixable, not yet done

1. **`scripts/vidux-public-ready-grep-gate.py`'s `SCAN_TARGETS` is a
   hand-maintained allowlist, not "everything tracked minus a documented
   denylist."** Same bug class already fixed twice before (ASK-LEO.md,
   `projects/`), recurred again:
   - `AGENTS.md` (top-level, tracked, not gitignored) is outside
     `SCAN_TARGETS` entirely and currently leaks the private routing-lane
     name and private skills-repo path (same two strings PRIVACY_PATTERNS
     already has rules for) in cleartext at line 4.
   - `CHANGELOG.md` is excluded outright (grouped with true historical
     records) and currently leaks the private routing-lane name (line 11)
     and the private overlay-repo name (lines 82, 320) — contradicts the
     gate's own stated invariant that PRIVACY_PATTERNS apply "everywhere
     scanned, regardless of tense."
   - `.gitignore` (unscanned) leaks the maintainer's bare private username
     at line 151.
   - The regexes themselves are fine (independently verified, all 17
     patterns fire correctly on real test strings) — the scan surface is the
     bug, and it will keep recurring under an allowlist design.

2. **SKILL.md:172 still deanonymizes the maintainer** — "a real example: the
   maintainer's own FirstBite repos" — same cross-product-citation pattern
   that got purged from paragraphs immediately around it (Moussey, Resplit,
   strongyes, sy-*) in commit `57b037ea`, just missed at this one spot.

3. **CODE_OF_CONDUCT.md:40** tells harassment/CoC reporters to file "a
   confidential report through GitHub Issues" — Issues are public
   (`blank_issues_enabled: false` doesn't gate visibility), and no actual
   private contact channel exists anywhere in the repo. Already flagged in
   round-3 evidence (`2026-07-09-panel-round3-and-urgent-remediation.md:191`)
   and still unfixed.

4. **SUPPORT.md:4,7** links to `template=bug.yml` / `template=feature.yml`,
   both deleted by commit `f455f62a` ("dedupe issue templates") in favor of
   `bug-report.yml` / `feature-request.yml`. Both of SUPPORT.md's two primary
   help links currently 404 the named template. Already flagged in round-3
   evidence (`:190`) and still unfixed. Two-line fix.

5. **SECURITY.md's reworded credential-leak claim is still misleading** given
   the now-concrete `refs/pull/*` finding above — `experienced-oss-contributor`
   found the "dated audit trail" pointer undersells what's actually still
   open. Needs another pass once (or if) item P0-1 is resolved, not before —
   no point re-wording a claim about a leak that isn't fixed yet.

6. **README.md Quick Start's `git clone ... ~/vidux` doesn't match the
   hardcoded `DEV_ROOT = ~/Development` scan root** used by
   `browser/server.py:34`, `bin/vidux-browse:29`, `scripts/vidux-status.py:30`
   — the "shows up automatically" promise is false for anyone following the
   literal instructions (checkout must nest inside `~/Development`, not sit
   as a sibling). Also: "Status & Config" section still has a literal
   unedited placeholder `~/path/to/projects`. Also: the "one entry point"
   claim is false (`/vidux-status` is a real second shipped command). Also:
   version badge will render stale.

7. **`scripts/vidux-worktree-gc.py`, `vidux-init.sh` code-quality gaps**
   (non-blocking per the lens, but real): C-style git path-quoting (spaces in
   filenames) defeats the exact-suffix-match allowlist — false positives
   only (over-cautious direction, not exploitable); raw unhandled tracebacks
   when `gh` is missing/repo path invalid, unlike every other `run()` call
   site in the file; pre-delete re-check in `remove_worktrees()` only
   re-verifies ignored-file risk, not tracked-file dirtiness.

## P2 — non-blocking, worth a pass

- `receipts.html` filter buttons don't set `aria-pressed`, unlike the
  existing pattern in `browser/static/sidebar-filters.js`'s `syncButtons()`
  for the identical widget type elsewhere in the same codebase.
- Several CSS custom properties used as small text fail WCAG 1.4.3 AA
  (4.5:1) contrast in the light (default) theme — never checked by any
  prior round.
- 60 stale branches on `origin` beyond `main`, unvetted beyond the two known
  leak classes already swept. Not blocking on its own.

## Confirmed holding up under independent re-check (no action needed)

- `scripts/vidux-plan-gc.py` fence fix — not specifically re-tested this
  round but no lens flagged it.
- `scripts/vidux-init.sh` absolute-path success/error messages — genuinely
  work regardless of caller's cwd (verified via symlink traversal).
- `browser/static/app.js` ResizeObserver mobile-drawer fix — holds,
  including a dynamic-resize-without-reload scenario the committed tests
  don't cover.
- `browser/static/receipts.html` button conversion — holds (re-verified via
  git-stash-and-restore + fresh Playwright checks); only gap is the
  `aria-pressed` P2 above.
- SKILL.md `origin/master`→`origin/<trunk>` fix, Fable definition fix,
  artifacts/hardlink de-identified citation — all three hold up; SKILL.md's
  only remaining issue is the FirstBite citation (P1 #2 above).
- 11 job-hunt-POC branches confirmed deleted from origin and absent from all
  60 remaining branches and all 7 PR refs. The purged file content
  (`51c4dbe`/`fb673ed`) is confirmed genuinely gone from every live ref
  (only the commit-*message* text survives on PR refs — P0-1 above).
- `gitleaks detect` across the full 1932-commit history: clean.
- `scripts/vidux-public-ready-grep-gate.py`'s regex patterns themselves
  (as opposed to `SCAN_TARGETS` scope): all 17 fire correctly, no silent
  no-ops remain.
- CONTRIBUTING.md, LICENSE, issue-template YAMLs: solid, no placeholder text.
- Python suite: 707 tests green (4 legitimate env-conditional skips).

## Process notes

- **3 of 20 lens agents degenerated or cross-contaminated rather than
  producing real findings about this repo.** `naming-branding-collision`
  explicitly errored (`StructuredOutput retry cap (5) exceeded`).
  `positioning-honesty` returned a real JSON envelope but with placeholder
  content (`title`/`detail`/`summary` all literally `"test"`) — almost
  certainly a truncated/malfunctioning run, not a genuine finding.
  `simplicity-niche-fit` is **confirmed cross-contaminated**: independently
  verified against the actual vidux repo (2026-07-09) — `nicole-readiness-
  packet.mjs` does not exist anywhere in vidux, `/coder-nicole` appears
  nowhere except this evidence file's own citation of the finding, vidux has
  362 markdown files (not the claimed 1,350), and `.claude-plugin/` contains
  only a bare `plugin.json` (no `marketplace.json`, no README with the
  claimed "Dormant by decision 2026-07-02" note). All 5 of that lens's
  blockers describe a different repo entirely (almost certainly the
  maintainer's other e-commerce-site repo, which does have all of those
  exact files/paths/counts) mapped onto vidux by mistake. **None of these 3
  should be counted as
  trustworthy NO-GO votes.** Effective round-4 signal is closer to 5 GO /
  12 real NO-GO / 3 degenerate-or-contaminated-needs-rerun.
- A prior round's own `test-suite-trust` lens said GO while `smoke.spec.ts:123`
  (stale sort-label assertion, unrelated to any of this session's changes)
  was already failing — confirmed via `git stash` to predate this session's
  work. Fixed in the round-4 P1 remediation batch (see below).
- All 3 degenerate/contaminated lenses (`naming-branding-collision`,
  `positioning-honesty`, `simplicity-niche-fit`) were re-run standalone
  after this checkpoint — results below.

## Standalone re-runs of the 3 degenerate/contaminated lenses (2026-07-09)

**`naming-branding-collision` — real, informational, not blocking.**
`vidux.ai` is a live, active AI video-generation product ("Vidux AI",
self-claimed 50M+ users, text-to-video/upscaling) in the adjacent AI-tooling
space — the strongest confusion vector, since someone hearing "vidux" in an
AI-dev context is likely to hit that product first. "Vidux Kft" is also a
real, unrelated Hungarian software company (~21 employees). npm package name
`vidux` is actually available (a 2023 publish was later removed) — moot
either way since `package.json` has `"private": true` and no publish script.
GitHub bare handle `github.com/vidux` is taken by an unrelated personal
account, but irrelevant since the repo lives at its own org path
(`firstbitelabsllc/vidux`), unaffected. Net: real brand-confusion risk in
the AI-tooling space specifically, weak/moot namespace risk. Rename is the
maintainer's call, not something this session is deciding or acting on.

**`simplicity-niche-fit` — clean re-run, partial-delivery verdict, not the
contaminated NO-GO.** Confirmed only real vidux-repo facts this time (362
markdown files, 61 scripts/ files, 347 tracked files total — nothing like
the fabricated 1,350/nicole-readiness-packet.mjs from the contaminated run).
Zero hardcoded personal paths ship in tracked, live-facing files (the only
maintainer-home-path hits are inside the grep-gate script and its own test
fixtures — the leak-detector itself, not a leak). Genuine MIT LICENSE, clean
repo root, no checked-in venvs or loose screenshots. The browser GUI was
actually launched and exercised: real Simple/Advanced mode toggle
(Simple by default), real progress bars/status/filter chips reading live
`PLAN.md` data. This genuinely delivers the "see a GUI, see progress" half
of the maintainer's stated goal for a non-technical operator. The gap: the
GUI is deliberately read/comment-only (README and code are explicit —
"never mutate PLAN.md"); authoring or editing a plan still requires
terminal + hand-edited markdown (`vidux init`, then edit by hand). So
"Nicole can watch and comment on the work" is real today; "Nicole can plan
the work" through the GUI is not yet. This is a real, named product-scope
gap worth tracking, not a release blocker on its own — the repo itself is
clean, honest, and licensed. Minor unrelated note from the same re-run:
`browser/static/index.html` loads the `marked` markdown library from a CDN
(with a documented offline fallback), which slightly dents the "runs
anywhere Python runs, no external deps" framing if that claim exists
verbatim anywhere — worth a grep before the next round.

**`positioning-honesty` — third attempt (after a direct follow-up ask)
produced a real, confirmed finding.** README.md's original wording pointed
readers to `CHANGELOG.md` to verify "GitHub Actions CI is intentionally
manual-only" — independently verified this citation is broken: `CHANGELOG.md`
says nothing about the policy and actually shows the opposite impression
(CI jobs being added across 2.26.x). The real evidence lives in
`.github/workflows/{ci,lint,test}.yml`'s `DISABLED / MANUAL-ONLY POLICY
2026-06-22` header comments — confirmed directly. One precision gap also
confirmed: `secret-scan.yml` still runs automatically on every push/PR, so
"CI is manual-only" was slightly over-broad. Fixed 2026-07-09: README now
cites the workflow headers directly instead of CHANGELOG.md, and calls out
the secret-scan exception. Everything else this lens checked (the `npm run
verify` claim, the Hermes Agent comparison table, the kernel-cut eval
numbers, the LangGraph/CrewAI characterizations) was independently verified
accurate and fairly framed — no other positioning-honesty issues found.

All 3 originally-degenerate/contaminated round-4 lenses are now resolved:
2 GO-worthy re-runs (naming-branding-collision: real but informational,
not blocking; simplicity-niche-fit: partial-delivery, not blocking) and
1 real fixable defect found and shipped (positioning-honesty).

## Next actions (in order)

1. Fix the concrete P1 items (2-4, 6) — small, low-risk, well-scoped. DONE
   2026-07-09 (commit `b5323825`), plus SUPPORT.md/CODE_OF_CONDUCT.md/
   README.md fixes and a stale-label test fix bundled into the same batch.
2. Fix the `SCAN_TARGETS` allowlist gap properly this time: switch to
   "everything tracked minus a documented denylist" instead of adding
   `AGENTS.md`/`CHANGELOG.md`/`.gitignore` as three more allowlist entries
   (which just reproduces the same bug class a fourth time). DONE 2026-07-09.
3. Fix `worktree-gc.py`'s two new bugs (P0-2): recurse into ignored
   directories instead of trusting the collapsed top-level line; drop the
   dead `.DS_Store` suffix check in favor of a basename check. DONE
   2026-07-09 — used `-z --untracked-files=all` (not `--ignored=matching`,
   which was tried first and empirically confirmed NOT to force recursion
   for a directory-pattern ignore rule) plus a HUMAN_AUTHORED_SUFFIXES
   override that beats the directory-name fast path.
4. Fix `playwright.config.ts` hermeticity (P0-3). DONE 2026-07-09 —
   `reuseExistingServer: false` unconditionally; Playwright's webServer API
   has no content-verification hook for the reuse path, so never-reuse is
   the only actual fix.
5. Re-run `naming-branding-collision`, `positioning-honesty`, and
   `simplicity-niche-fit` standalone (not a full 20-lens round) to get real
   signal before folding them into round 5's count. IN PROGRESS 2026-07-09.
6. Raise P0-1 (`refs/pull/*` leak) to Leo directly in chat with the
   escalated, concrete framing — not just left in this file.
7. Round 5 once 1-4 are shipped.

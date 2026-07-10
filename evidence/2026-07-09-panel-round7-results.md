# Panel round 7: 6/20 GO

Purpose: fresh sweep specifically designed to adversarially re-verify
round-6's fixes (worktree-gc, grep-gate, README citations, plugin.json +
contract-test scan, DOCTRINE.md cross-ref), re-check the 2 items round 6
deferred (Voxtral dead-code, recipe-table staleness), and run a full
standard sweep (security/secrets, commit-metadata, onboarding, test-suite
integrity, license/attribution, CI accuracy, browser security, WCAG
accessibility, multi-agent parity, evidence hygiene, naming/branding,
private-fleet content, positioning honesty, contribution readiness,
simplicity/niche-fit).

**Result: 6/20 GO, 14/20 NO-GO** (1 of the 14 was a degenerate re-run,
`skill-doctrine-coherence-verify`, needing another clean pass — not
counted as real signal here). This is a real regression from round 6's
15/20 — expected, since round 7 was built to hunt harder for exactly the
kind of hole round 6's own fixes might have left.

## P0 — most severe, found this round

### 1. I personally introduced 2 live, unredacted leaks into this session's own evidence files

`evidence/2026-07-09-panel-round4-results.md` and
`-round6-results.md`, both written earlier this session, quoted a real
internal Snap-hosted endpoint hostname and the maintainer's other-business
gmail address verbatim, in cleartext, while documenting findings about
those exact leaks. My own `grep-gate` runs reported "passed" every time —
not because I skipped the check, but because `PRIVACY_PATTERNS` had zero
rule for either string class, so my own verification gave false
confidence. **FIXED** — see Remediation below.

### 2. The `refs/pull/*/head` leak is confirmed still live; a same-day "P0 done" closure claim on `origin/main` overclaims

Independently re-verified (not just relayed from the panel) via direct
`git fetch`/`merge-base --is-ancestor` against the real remote:

- `refs/pull/1/head` through `refs/pull/5/head` all still exist on
  `firstbitelabsllc/vidux` and all 5 remain **ancestors** of the commit
  that carries a real internal Snap-hosted endpoint hostname in its
  **commit message** (not file content — a structurally different leak
  vector than everything else found this session).
- That same commit is confirmed **NOT** an ancestor of `origin/main` —
  the `git filter-repo` purge described in the closure commit below did
  work for the default branch.
- A same-day closure commit on `origin/main` (docs-only, PR merged today)
  claims: *"filter-repo stripped [a specific backup directory] from all
  729 commits... zero remaining refs anywhere contain the old commit...
  No remaining P0."* Independently confirmed the backup-directory purge
  claim itself holds (`git rev-list --all --objects` across every
  currently-fetched ref shows no trace of that path). But the "zero
  remaining refs anywhere" and "No remaining P0" language overclaims: it
  describes a **path-scoped** `filter-repo` run, which rewrites tracked
  file content and paths — it does not and structurally cannot touch a
  **commit-message** string, nor GitHub's own server-maintained
  `refs/pull/N/head` refs, which persist independently of any force-push
  to a base branch. These are two different leaks (file-content-in-a-
  directory vs. hostname-in-a-commit-message) that got conflated into one
  "P0 done" claim.
- **Not a live public exposure right now** — the repo has stayed PRIVATE
  throughout, confirmed unchanged by this session. The exposure only
  becomes real the moment repo visibility flips to public: at that
  instant all `refs/pull/N/head` refs become fetchable by anyone,
  regardless of how many times `origin/main`'s history has been
  rewritten, because a merged PR's ref persists on GitHub independent of
  base-branch operations.
- The only ways to actually eliminate these specific refs: (a) full repo
  deletion + recreation (loses all PR/issue history), or (b) a GitHub
  support request to purge specific refs (not standard self-service).
  Both are the maintainer's call, same class as the already-tracked
  repo-recreation-vs-surgical-rewrite decision.
- **This looks like an honest mistake by a concurrent lane, not bad
  faith** — `git filter-repo` genuinely does not touch GitHub-server-side
  PR refs; the closure commit's author likely didn't know that mechanism
  existed. **Not resolving this myself, raising to Leo** (see below) —
  unchanged from every prior round, now with a corrected, independently-
  verified picture of exactly what "P0 done" did and didn't accomplish.

## P0/P1 — real, fixed this round

3. **`scripts/vidux-worktree-gc.py`'s directory-trust mechanism: 4th
   consecutive round finding a new, genuinely different hole.**
   Case-insensitive-but-case-preserving filesystems (APFS/macOS default,
   also Windows): `mkdir("Node_Modules/x")` when `node_modules/` already
   exists silently resolves into the SAME existing directory, no error.
   Live-reproduced. **Directly tested the panel lens's proposed fix**
   (verify via `os.scandir` instead of trusting git's output) against the
   repro — it does nothing, because `git status` already reports the
   TRUE, correctly-cased on-disk path; there was never a second,
   differently-cased directory for `os.scandir` to distinguish. Once the
   filesystem merges the two, no remaining metadata records which path a
   file was created through, so no introspection-based check (this
   script or any other) can tell a human-deposited file apart from
   genuine package-manager output after the fact. **Documented as an
   accepted residual risk, not force-fixed** — the only real mitigation
   (disable directory-blanket-trust on any case-insensitive filesystem)
   would defeat this tier's purpose on its primary runtime (macOS/
   Windows) and would regress an existing, intentionally-tested guarantee
   (`test_unambiguous_tool_dir_still_auto_cleans_without_per_file_check`).
   Commit `4fbf2c12`.

4. **`vidux-public-ready-grep-gate.py`: 3 new structural blind spots,
   2 fixed, 1 documented.**
   - No `PRIVACY_PATTERNS` rule for the employer's internal hostname TLD,
     or for gmail addresses / the maintainer's other-business name —
     the exact gap that let finding #1 above ship. **Fixed**, with the
     maintainer's own permanent public commit-author email
     (`leojkwan@gmail.com`, confirmed via `git log --format='%ae'` to
     already be on every commit on `origin/main`) explicitly excluded
     from the new gmail rule, since it's the by-design identity, not an
     anomaly. 4 new regression tests, confirmed failing pre-fix. Commit
     `11709425`.
   - **The gate never scanned filenames, only file content.**
     Reproduced live: an evidence file's body had been redacted in an
     earlier round, but its filename still carried a private-tooling
     codename verbatim — invisible to every prior grep-gate run, would
     render unredacted in any GitHub directory listing regardless of
     body content. **Fixed**: `PRIVACY_PATTERNS` now also match every
     scanned file's relative path, unconditionally, including files
     otherwise exempt for HYGIENE_PATTERNS reasons. Renamed the affected
     file and cleaned its remaining unredacted body references (a crude
     find/replace in an earlier round had left a few instances a
     narrower regex missed). New regression test, confirmed failing
     pre-fix. Commit `5d1ae4ea` (landed by a concurrent lane running the
     identical fix — verified byte-identical before confirming, not
     duplicated).
   - **`HISTORICAL_TARGETS`'s bare `"PLAN.md"`/`"projects"` entries are
     whole-file/whole-directory exemptions, but a PLAN.md isn't
     append-only-by-design** the way `CHANGELOG.md`/`ARCHIVE.md` genuinely
     are — it interleaves live sections (Purpose, Constraints, Tasks)
     with append-only ones (Decision Log, Progress, Drift Log).
     Reproduced live: injecting a hygiene violation into an ACTIVE
     project's Tasks section still passed. `PRIVACY_PATTERNS` are
     unaffected (they apply everywhere regardless); this is a
     `HYGIENE_PATTERNS`-only (retired-terminology accuracy) gap, lower
     severity than it first appeared. **Documented, not fixed** — a
     correct fix needs section-aware scanning (only treat recognized
     append-only headings as historical), which changes behavior for
     every PLAN.md in the repo and deserves its own dedicated
     verification pass. Commit `c68e20c5`.

5. **`.github/workflows/secret-scan.yml` has been unable to run at all
   since 2026-06-18.** Its one `run:` step mixed a double-quoted scalar
   with trailing unquoted text — invalid YAML, confirmed unparseable by
   PyYAML, Ruby Psych, and `actionlint` independently. This silently
   defeated the "runs automatically" security-scan exception this
   session's own earlier README language relied on. **Fixed** — dropped
   the now-unnecessary quoting (gitleaks is already on `$GITHUB_PATH`
   from the prior step). Commit `d1b502ce`.

6. **3 more live instances of the banned pre-kernel-cut "orchestration"
   framing**, all unscanned by the contract test's hand-maintained
   allowlist (3rd instance of this exact drift class this session):
   `docs/.vitepress/config.ts`'s own SEO meta description, `VERSION`, and
   `SUPPORT.md`. The maintainer's own manual `rg` verification command
   (quoted in `evidence/2026-07-07-kernel-cut-pivot.md`) also missed
   `config.ts`, since plain `rg` skips dot-directories without
   `--hidden` — the spot-check itself was a false negative. **Fixed**,
   plus widened the contract test's scan list to include all 3 files.
   Also fixed `docs/.vitepress/config.ts`'s stale copyright holder/year
   (said "Leo Kwan, 2024-present"; `LICENSE`/`package.json` say "First
   Bite Labs LLC, 2026") and two GitHub links pointing at a different,
   decommissioned repo. Commit `4926f3ba`.

7. **README comparison-table: 3 new inaccuracies in the same table round
   6 had just re-fixed, plus a stat misattribution surviving from round
   3.** "Hermes Agent runs as a systemd service" doesn't trace to Hermes's
   own docs (confirmed via live fetch: describes running from a $5 VPS to
   a GPU cluster to serverless, no systemd mention anywhere); dropped the
   also-unverifiable "across 3 layers" framing. Separately: the "76%
   resolved vs. 59%" kernel-cut evaluation stat is the single strongest
   direct model-pairing comparison (17 runs each), not the full
   117-clean-row study aggregate — the wording implied the latter. Same
   fix applied to `PLAN.md`'s Evidence line and `guides/thin-token.md`,
   which had the identical conflation (this exact paragraph in README
   already survived one earlier fix pass in round 3). Also added an
   `npm install` pointer before `vidux doctor` in Status & Config — its
   `npm test` check fails with an opaque "command not found" on a fresh
   clone that never ran it, previously only documented (unlinked) in
   `CONTRIBUTING.md`. Commit `7f999b70`.

8. **Dead code: the "Code" button in Advanced view has failed every
   click since 2026-06-01.** POSTs to `/api/coding-handoff`, which has
   zero server-side implementation and never has (confirmed via
   `git log --all -S` against the full history of `browser/server.py`).
   The real, working Moussey handoff mechanism already exists in the same
   file (`codingWorkbenchUrl()`, a direct link, no fetch dependency),
   already wired to a separate "Code lane" link elsewhere in Advanced
   mode. This was superseded scaffolding, not in-progress work. **Fixed**
   — removed the button, its handler, and updated the one place it was
   documented. Commit `71af24c7`.

9. **The orphaned Voxtral `/api/upload-ref-audio` route** (flagged
   deferred in round 6) — full commit trace confirmed a deliberate
   two-stage sunset with zero live callers, consumers, or test coverage
   remaining, and its own inline comment cited a `PLAN.md` path that no
   longer exists. **Deleted outright** per the clear recommendation, plus
   the matching doc line and test-contract entries. Commit `5d1ae4ea`
   (same concurrent-lane commit as item 4's filename-scan fix — verified
   byte-identical).

10. **WCAG 1.4.3 AA: the 4 status-label tokens round 4 fixed only
    checked contrast against `--paper`.** The same tokens also render on
    `--paper-2` (a slightly darker surface used for cards/panels), where
    they measured 4.23-4.26:1 — still failing 4.5:1. Computed the exact
    darkening needed (same hue/saturation) to clear `--paper-2`
    specifically, which also widens the `--paper` margin to 4.98:1. New
    regression test, confirmed failing pre-fix at the exact predicted
    ratios. Commit `1962a614`.

11. **`.subplan-row` was click-only: no `tabindex`, `role`, `aria-label`,
    or keydown handler**, despite being the only way to navigate into a
    sub-plan from this view — unreachable by keyboard, silent to screen
    readers. **Fixed**: added `role="button"`, `tabindex="0"`, an
    `aria-label`, and an Enter/Space keydown handler alongside the
    existing click listener. No CSS change needed — the existing global
    `:focus-visible` fallback already covers any newly-focusable element.
    Commit `7696f8cd`.

## Investigated, found not actually broken

- **The "Steer this plan" textarea** was flagged by one lens as giving a
  false success signal (POSTs to `/api/comments`, writes to
  `~/.vidux-browser/comments.jsonl`, "no agent-facing code path ever
  reads it"). Checked against `CHANGELOG.md` and
  `docs/reference/browser.md`, both of which already explicitly document
  this as an annotation endpoint — "app data... never mutate PLAN.md...
  not a plan-writing one." It does exactly what it's documented to do;
  this isn't dead/misleading code, at most a UX-copy question (does
  "sent" read as "an agent will act on this" vs. "an annotation was
  appended for a human to read later"). Not fixed — lower priority than
  the P0/P1 items above, and arguably not a bug at all.

## Not yet addressed — concrete, lower severity, still open

- `tests/test_vidux_contracts.py`'s 11 module-level path constants
  resolve into the maintainer's private sibling repos, causing
  skip-based (not fail-based) signal for any contributor besides Leo,
  undocumented in `CONTRIBUTING.md`, and printing his real home path into
  stdout via skip messages (P2).
- 5 more WCAG/accessibility findings beyond the 2 fixed this round
  (contrast + subplan-row) — not yet triaged in detail.
- `evidence/2026-06-20-eve-studio-vidux-receiver-receipt.md` cites a
  stale PR number and commit SHA that no longer resolve against the
  current repo — likely a downstream consequence of history rewrites
  earlier today, not this session's doing.
- `evidence/2026-06-07-fleet-improvement-workorder.md` is a largely-
  unredacted internal multi-product operations memo (real repo names, PR
  numbers, pricing details, career-linkage framing) — folding into the
  private-fleet-content decision below rather than resolving unilaterally.

## Escalated to Leo, unresolved, explicitly not my call

Per the standing carve-out this whole session: I perform all
remediation/build/review work myself, but repo-visibility and any
destructive git-history operation are the maintainer's explicit,
separate decision, regardless of panel verdict.

1. **`refs/pull/*/head` leak (updated, most urgent)** — confirmed still
   live per the verification above. A same-day closure commit's "No
   remaining P0" claim overreaches: true for the specific backup-
   directory file-content purge it describes, false for this separate
   commit-message-level leak, which a path-scoped `filter-repo` run
   cannot touch. Needs either full repo recreation (loses PR/issue
   history) or accepting the risk until/unless GitHub support can purge
   specific refs. Not urgent while the repo stays private, but blocks
   ever flipping visibility until resolved one way or the other.
2. **Private-fleet-ecosystem content — confirmed much larger in scope
   than previously catalogued.** Beyond the scattered doctrine mentions
   already known: an entire shipped Python module (`browser/receipts/*`,
   13 files) whose explicit purpose is exporting data into one of the
   maintainer's other private apps' test-fixture tree, with hardcoded
   type-contract mirroring of that app's real source types and default
   paths into that app's own directory and config; a dedicated onboarding
   doc naming 6 real private repos in full; two full private-automation-
   fleet blueprint files (lane IDs, plan paths, tech stack, a live
   production site, and several vendor/observability references); a
   shell script with ~20 hardcoded private automation-lane IDs operating
   against a real local database path; and a shipped slash-command whose
   worked example renders several real private repo/product names instead
   of placeholders. Strip, anonymize, or keep — maintainer's call, not
   mine to resolve unilaterally.
3. **`vidux.ai` naming collision** — informational only, unchanged from
   prior rounds.
4. **Commit-authorship near-misses** — unchanged from round 6: one commit
   reachable from `origin/main` (tagged in a recent version bump)
   authored with the maintainer's separate small-business email instead
   of his usual identity; 9 further commits locally authored with his
   real employer corporate email, confirmed NOT reachable from `origin`
   (a near-miss, not a live leak).
5. **Evidence-directory hygiene** — a broader recommendation (consolidate
   or curate the `evidence/` corpus before any public release; some files
   carry personal/business narrative disclosure risk in their prose,
   independent of any single leak string) is itself a judgment call about
   how much audit trail to keep public, not something to execute
   unilaterally.

## Needs a clean re-run

- `skill-doctrine-coherence-verify` degenerated again this round (same
  failure mode as rounds 4 and 6 before it) — not counted as real signal.

## Next actions

Round 8 launches once this evidence file and the corrected Leo update are
both in. Priority for round 8: verify all 11 fixes above hold under
independent re-inspection, re-run the degenerate lens cleanly, and pick up
fresh ground the 14 NO-GO lenses didn't have time to cover this round
given how much of round 7 was spent re-verifying rounds 4-6.

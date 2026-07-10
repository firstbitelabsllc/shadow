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
     `projects/agentic-5x`, `projects/mom-flushing-home`, `projects/family-member-fpa-ai`,
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
   onboarding, CLI crash-resistance, browser security, non-technical-simplicity GUI
   (screenshot-based), dependency hygiene, test/CI coverage, positioning honesty,
   governance/sustainability, accessibility, naming/trademark, code quality,
   error-message UX, git-history hygiene, stranger-repro, second-order privacy, and
   open-source mechanics — to get a current, trustworthy GO/NO-GO count rather than
   continuing to work off an aging backlog with a proven-high false-positive rate.

## Panel round-2 results: 6 GO / 14 NO-GO (`wf_5cd1ad8a-619`)

The fresh 20-lens panel came back materially different from a rubber stamp — real,
newly-verified findings, most severe among them a git-history exposure class none of
the prior purge rounds (this session's or earlier ones) had addressed:

**Git-history exposure — three distinct vectors, not one:**

1. **Dangling objects fetchable by full 40-char SHA.** `git filter-repo` +
   force-push only rewrites *ref-reachable* history; a commit that already went
   dangling before a given rewrite is invisible to that rewrite and remains
   physically present in GitHub's object storage, fetchable via plain
   `git fetch origin <full-sha>` indefinitely (confirmed live, twice, for two
   specific dangling commits this session). Abbreviated/short SHAs do **not**
   work as a fetch target (confirmed via both raw git and the GitHub API), so
   this vector requires an attacker to already hold the exact full SHA from
   before any purge — not exploitable by a stranger today, but a standing
   pre-condition for any future visibility flip. **Mitigated, not closed:**
   redacted every SHA fingerprint this repo's own tracked docs printed (see the
   companion redaction PR); the underlying dangling objects still exist
   server-side and only GitHub-side garbage collection, a GitHub Support purge
   request, or a full repo recreation actually clears them.
2. **Two commit messages reachable from current `main`** (both squash-merge
   commits from this repo's pre-this-session remediation rounds) quoted, in
   plaintext, real named coworkers, internal VCS/dashboard hostnames, internal
   project codenames, and a real internal service endpoint — as "evidence of
   what was found and fixed." Classic self-referential leak: the fix commit's
   own description re-embedded the exact content it removed from files.
   **Fixed**: rewrote just these two commit messages via
   `git filter-repo --message-callback` (confirmed via a full-history blob
   sweep that file content was already 100% clean — this was messages only),
   force-pushed `main`, independently re-verified via a fresh mirror clone
   that the old commit SHAs are no longer ancestors and the terms are gone
   from every commit message across all 71 branches + 5 tags.
3. **Three pushed-but-unmerged branches** carried complete unredacted internal
   PLAN.md/handoff files (not just messages — full file content: named
   coworkers, an internal auth-integration reference, AB-test rollout
   percentages). A default `git clone` fetches every branch even though only
   `main` gets checked out, so this was one `git checkout` away from full
   exposure the moment the repo goes public. **Fixed**: backed up locally
   (`/tmp/vidux-deleted-branches-backup/*.bundle`, not committed anywhere) and
   deleted all three branches from origin. None were merged into `main` and no
   open PR referenced them.

**A fourth vector was found and is *not* fixable via any git push**: GitHub
auto-creates a permanent `refs/pull/N/head` ref for every PR ever opened,
independent of the PR's branch. These are fetchable
(`git fetch origin refs/pull/N/head`) by anyone with repo read access and
cannot be deleted or rewritten by a normal `git push --force` — GitHub, not
the pusher, owns this ref namespace. Checked the actual scope: this repo has
had exactly 5 PRs total (this session's own #1-#5), so the two now-redacted
commit messages are still permanently anchored via those 5 PR refs regardless
of the `main`-branch rewrite above. **Not fixed — structurally can't be, short
of GitHub Support intervention or a full repo recreation.** This is the
strongest argument yet for treating "recreate the repo one more time, now that
history is otherwise clean, before opening any further PRs against it" as the
real terminal fix, rather than continuing to patch main after the fact — see
the standing-tension note below, this is now folded into that same
Leo-owned decision.

**Other real findings from the panel** (full detail in the workflow journal,
`wf_5cd1ad8a-619`), not yet acted on:
- `bin/vidux-browse` invoked directly (exactly as README/docs instruct) crashes
  with a raw Python traceback for any checkout not physically at
  `~/Development/vidux` — only the `bin/vidux dev`/`browse` wrapper commands
  self-locate correctly.
- `vidux dev`'s restart loop has no backoff/give-up condition on an
  unrecoverable child failure (e.g. port already in use) — spins forever with
  no guidance, and this is the literal first command the README Quick Start
  tells a new user to run.
- Mobile header (`.topbar h1` + the Advanced-view toggle button) overlaps at
  iPhone SE/12/13/14 widths — "vidux browser" renders as "vidux brows" with
  the button drawn on top.
- `scripts/vidux-plan-gc.py` has zero fenced-code-block awareness and is LIVE
  by default (wired into an unattended cron): a PLAN.md documenting its own
  checkbox convention inside a ```` ``` ```` example gets that example parsed
  as real completed tasks and silently rewritten out of the file (recoverable
  via ARCHIVE.md/git, not data loss, but a public "plan-first" tool silently
  mangling a user's first PLAN.md is a bad first impression).
- SKILL.md's own doctrine cites unverifiable operational data from two other
  *separate* private products (specific worktree/branch counts, a GC timing
  incident) as its evidentiary backing — a stranger can't check the citation,
  and it re-introduces the class of cross-product leak the purge rounds exist
  to remove (no confidential content in the citations themselves, just an
  unverifiable-by-strangers sourcing pattern).

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

## Panel round-2 remediation: all 4 concrete CLI bugs now fixed

Since the section above was written, all four concrete (non-git-history) panel
round-2 findings have been fixed, tested, and shipped:

1. `bin/vidux-browse` self-location crash — fixed via the same `BASH_SOURCE`
   resolution pattern `bin/vidux` already uses. Regression test:
   `test_vidux_browse_self_locates_when_invoked_via_symlink_outside_checkout`.
2. `vidux dev` restart-loop-forever — fixed via `FAST_FAIL_SECONDS`/
   `MAX_FAST_FAILURES` backoff-and-give-up in `scripts/vidux-dev.py`.
   Regression tests: `tests/test_vidux_dev.py` (new file).
3. Mobile header overlap — fixed via `flex-wrap` on both `.topbar` and
   `.topbar-meta` (the inner element whose own children were overflowing).
   Regression: 3 Playwright width checks appended to
   `browser/tests/e2e/smoke.spec.ts`.
4. `scripts/vidux-plan-gc.py` fenced-code-block blindness — fixed, but with a
   correction worth recording. The first fix attempt (adding an `in_fence`
   guard to the group-*start* condition only) was insufficient: the later
   `completed_groups` filter re-derived "is this a real completed task" by
   re-matching regex text against each group's first line, with no memory of
   whether that group had been created inside a fence. A fenced
   `- [completed] Example ...` line still built its own standalone group and
   still text-matched the completed-task regex downstream, so the original
   "fix" would have still archived the fenced example (proven empirically
   with a manual trace before writing the test, not assumed). The working fix
   tags each group `is_task: True/False` **at creation time** (mirroring the
   pattern `trim_inbox()` already used correctly via its `prunable` flag) so
   the downstream filter checks the tag, not re-derived text. Regression test:
   `test_fenced_example_completed_lines_are_never_archived` — proven to fail
   against the pre-fix source via `git stash` (falsely counted 75 completed
   instead of 35, tripped the hard-cap warning) before being proven to pass.

**Process note — concurrent-write discovery.** This fix (`83e0370a`) reached
`origin/main` directly, not through this session's usual branch → PR → merge
flow. While iterating in the shared `~/Development/vidux` checkout (on `main`,
not a worktree), a separately-running `scripts/vidux-loop.sh` invocation
(pid 31516, pointed at an ephemeral tempfile plan, exited and self-cleaned by
the time this was noticed) picked up the working-tree edits and committed +
pushed them autonomously before this session ran `git add`/`git commit`
itself. Content was verified byte-identical to what was authored here (full
`git show` diff inspected), and the full suite (699 Python + 8 JS tests) was
green on the resulting `main` tip both locally and on `origin`, so no
correctness issue resulted. But it's a live instance of the exact
"multi-agent main contention" pattern documented for this fleet elsewhere:
editing directly on `main` in a shared checkout — instead of an isolated
worktree — leaves a window where a concurrent autonomous process can commit
(and here, push) uncommitted edits under its own commit message before the
authoring session gets to. No action needed on this specific commit; noted
here so future edits in this checkout default to a worktree when any
`vidux-loop.sh`/cron-style process might be concurrently active, rather than
editing `main` directly.

All four round-2 CLI bugs are now closed. Remaining round-2 items: the
SKILL.md unverifiable cross-product citation finding (not yet touched), and
the standing repo-recreation decision above (still Leo's call, unchanged).

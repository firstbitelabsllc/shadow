# Panel round 10: 14/20 GO

Purpose: re-verify round-9's fixes, push on the remaining P2 backlog instead of
re-documenting it, reassess the structural blockers net of the two
maintainer-gated git-history items, and run fresh security/secrets/onboarding
sweeps. Best GO result across all ten rounds so far (rounds ran 12/20, 5/20,
12/20, 15/20, 6/20, 10/18, 12/20 before this).

**Result: 14/20 GO, 6/20 NO-GO.** All 20 lenses returned real signal — 0
errors, 0 empty/degenerate results. Lens count verified before launch
(`grep -c "key: '"`, the round-8 miscount lesson) at exactly 20.

Every finding below was fixed this round, each with a regression test verified
failing pre-fix (via `git stash`) and passing post-fix, then the full suite,
JS tests, and grep-gate green before commit. Six commits landed
(`c2fb4a4d` → `576d265b`) and pushed to `origin/main`.

## P0 — most severe, found this round, fixed

### 1. receipts.html buttons render near-invisible in OS dark mode

`.local` / `.local:hover` / `.primary:hover` in receipts.html's inline `<style>`
hardcode their background colour but inherited `color: var(--paper)` from the
base button rules. `--paper` flips to near-black in dark mode, so the text
landed near-black on a background that never lightens — measured contrast
collapsed to 1.49–2.20:1, far below WCAG 1.4.3 AA. Not an exotic trigger: pure
OS/browser dark preference, no JS required. **Fixed**: fixed light text colour
(`#f8f5ee`, `--paper`'s literal light value) on these fixed-background buttons,
so light mode is visually unchanged and dark mode now clears 7.2–8.7:1. A
sibling hardcoded instance (`.ext .prov.local`, fixed text on a background that
*does* flip) was switched to the already-vetted theme-relative
`--task-in-review` token. Commit `73f1c0fb`.

## P1 — real, fixed this round

### 2. GET /api/receipts/list leaked private-flagged rows to any LAN caller

`handle_list()` returned every corpus row unconditionally — including
`private: true` rows with their name and all annotations — to any caller that
merely passed the Host-header LAN allowlist, bypassing the same `private` guard
every sibling route respects (`handle_image()` 404s for private rows;
`handle_upload()` never writes their image bytes to disk). Empirically proven
exploitable via a live curl PoC against a LAN-bind server. **Fixed**:
`include_private` defaults to `False`; `server.py` passes `True` only for a
loopback-verified caller, matching the loopback-only bar every write route
already enforces. Regression tests for both the omit-by-default and
include-for-loopback paths. Commit `c2fb4a4d`.

### 3. Dashboard status-label text dropped below AA on hover/focus

`--task-in-progress` / `--task-blocked` render on `--select` whenever the
keyboard-focusable `.dashboard-item` is `:hover`/`:focus-visible` — a harder
surface than `--paper`/`--paper-2`, never checked by the existing contrast
tests (4.11:1 light, 4.07:1 dark, below AA). **Fixed**: darkened/lightened the
tokens (same hue/saturation) to also clear 4.5:1 against `--select` in both
themes. Widened the test suite generally rather than patching the instance:
added dark-theme `TEXT_TOKENS` checks (there were none — only light-theme was
ever tested), a `--select`-specific check, and a full custom-property parity
test between `:root.theme-dark` and the bare `@media(dark)` fallback. Commit
`73f1c0fb`.

### 4. `vidux status` ignored `VIDUX_DEV_ROOT` despite README documenting it

README documents `VIDUX_DEV_ROOT` as an alternative to `--root` for the status
scan root and recommends it for a non-standard clone location, but
`scripts/vidux-status.py` hardcoded `~/Development` and never read the env var;
only `browser/server.py` honoured it. A contributor following the README got a
status board silently scanning the wrong tree — no error, no warning.
**Fixed**: `DEFAULT_ROOT` now reads `VIDUX_DEV_ROOT` the same way
`browser/server.py` does; explicit `--root` still wins. Regression test
reproduced the silent-wrong-tree behaviour pre-fix. Commit `50d448b9`.

### 5. SKILL.md platform-guard gap (`CronCreate`/`CronDelete`)

Same defect class round 9 fixed for `WebFetch`/`SessionStart`: SKILL.md named
the Claude-Code-specific deferred tools `CronCreate`/`CronDelete` completely
bare inside the harness-agnostic Persistent Loop Mode section, while every
other file in the repo qualifies that exact tool pair. **Fixed**: applied the
"e.g. X in Claude Code, or the equivalent in other harnesses" pattern; swept
SKILL.md/README/DOCTRINE for any remaining bare instance (none). Commit
`979c82d1`.

## P2 — fixed this round (backlog closed, not re-deferred)

### 6. `--shadow-*` missing from the bare dark `@media` fallback

Same reachable-fallback bug class round 9 fixed for `--error`/`--warning`:
`:root.theme-dark` carried dark-tuned shadow values but the bare
`@media(prefers-color-scheme: dark)` block still had the light-theme ones.
**Fixed** + generalized the round-9 regression test from a fixed token tuple to
full-block parity, so a future addition can't go missing again. Commit
`73f1c0fb`.

### 7. Plugin dual-name collision resolved outright

Round 9 only *documented* that root `SKILL.md` and `commands/vidux.md` both
declared `name: vidux`. This round resolved it empirically: a clean scratch-
plugin black-box test (Claude Code CLI 2.1.206) showed `commands/vidux.md`
deterministically wins the collision, so a plugin-path install's Skill-tool
call silently got the thin orchestrator instead of the full doctrine.
**Fixed**: renamed `commands/vidux.md`'s frontmatter name to `vidux-orchestrate`
(the `/vidux` slash trigger comes from the filename, unaffected); `plugin
validate` clean; README's stale "not resolved empirically" line updated to the
actual resolution. Commit `cc01f672`.

### 8. Shallow keyboard-a11y test finally replaced (open 3 rounds)

`test_subplan_row_is_keyboard_and_screen_reader_accessible` only grepped
`app.js` source text — never opened a page or dispatched a keypress. Flagged
rounds 8, 9, and 10 (three round-10 lenses independently recommended closing
it). **Fixed**: a real Playwright test that mocks a parent+child plan pair,
focuses a `.subplan-row`, presses Enter, and asserts real navigation. Verified
it has teeth by temporarily disabling the keydown handler and confirming the
test fails. Reused the file's own proven `page.route()` mocking + focus/keypress
idioms without touching the shared fixture root. Commit `576d265b`.

### 9. Genuine e2e flake fixed while in the file

A 200ms injected auto-refresh interval raced a comment-marker click's
synchronous class add under the full 3-project parallel run (reproduced 2/2).
**Fixed**: interval to 1000ms (verified 9/9 across three repeat full-parallel
runs), propagation timeouts to 5s. Commit `576d265b`.

## Standing, unresolved (unchanged from round 9)

The two confirmed structural hard blockers remain, both requiring a
maintainer-authorized git-history rewrite (explicitly outside any lens's
authority):

1. **`refs/pull/*/head` leak** — permanent GitHub-server-maintained PR refs
   carry a commit whose message contains a real internal endpoint. Re-verified
   this round: unchanged and still reachable (now 5 of 8 PR refs, since three
   more PRs opened since round 9).
2. **Commit-message employer-PII** — exactly 4 commits reachable from
   `origin/main` carry employer-machine identity in their messages, invisible
   to grep-gate/gitleaks by design. Re-verified: still exactly 4, same SHAs, no
   new instance in commits added this round.

Neither is a re-litigation of repo-visibility or the history-rewrite decision —
they are factual re-verifications that the leaks remain live, pending the
maintainer's call.

## Concurrent-lane note

While this round's fixes were landing, a separate Codex lane was running a
parallel releasability effort in the same repo, merging PR #8 (mission-control)
and PR #9 (public-authority-hygiene) — a ~18k-line pass adding browser security
hardening, a benchmark v2/v3/v4 harness, and reproducible release packaging.
All six round-10 commits were confirmed ancestors of the post-merge tip
(`2597cc93`) with every round-10 fix semantically intact. The two lanes'
readiness reads differ by *layer*: the Codex lane concludes package-level
"SHIPPING" (the npm tarball is clean, reproducible, excludes evidence/tests/
secrets), while this panel's two blockers gate the GitHub *visibility* flip
(git history + PR refs). Both are true; reconciling them is a round-11 council
lens and a maintainer Human-Gate decision.

## Verification

- Full Python suite green pre-Codex-merge (751 tests); JS 8/8; e2e 90/90 across
  three device projects; grep-gate passed (350 files); `plugin validate` clean.
- Each fix's regression test verified failing pre-fix and passing post-fix.
- All six commits confirmed ancestors of the current `origin/main` tip after the
  concurrent Codex merges.

## Next

Round 11 runs a fresh council against the post-merge tip: re-verify BOTH lanes'
work holds, adversarially audit the large new Codex surface (benchmark harness,
release packaging, browser security changes), reconcile the package-SHIPPING vs
git-history-blockers layer mismatch, and re-verify the two hard blockers.

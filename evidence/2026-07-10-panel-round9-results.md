# Panel round 9: 12/20 GO

Purpose: adversarially re-verify round 8's 7 fixes, precisely re-scope the two
big escalated findings (`refs/pull/*/head`, commit-message employer-PII), run
a dedicated structural-blocker-impact-assessment to separate true hard
blockers from risk-tolerable judgment calls, and open fresh P2 ground.

**Result: 12/20 GO, 8/20 NO-GO.** All 20 lenses returned real signal — 0
errors, 0 empty/degenerate results, the first round with zero failed lenses
(rounds 4/6/7/8 each lost at least one lens to a `StructuredOutput` retry cap
or placeholder-content degeneration). Lens count was verified precisely
before launch (`grep -n "^\s*key: '"`, not a loose `grep -c "key:"`, after
round 8's miscount taught that lesson) at exactly 20.

## P0 — most severe, found this round, fixed

### 1. Round-8's spouse-name fix was itself incomplete — case-sensitivity gap

`PRIVACY_PATTERNS`' new rule (`re.compile(r"\bNicole\b")`) had no
`re.IGNORECASE`, so it only matched the exact capitalized prose form a human
had spotted — not the lowercase/kebab-case form this repo's own project-naming
convention actually produces everywhere. A case-insensitive grep found the
name live and unredacted in 7 tracked files the round-8 fix never touched,
including two JSONL audit logs with real personal-project paths and tmp-file
names. **Fixed**: added `re.IGNORECASE`, redacted all 7 files, added a
case-insensitivity regression test. Commit `04f1b565`.

### 2. Tracked evidence PNG screenshots leak real home/family PII, invisible to text-based scanners

3 screenshots (`2026-06-03-vidux-browser-truth-{desktop,memory-band,signpost-chain}.png`)
render the browser UI's real local sidebar, showing plaintext artifact titles
naming a family member's private decision-brief topics and home-logistics
detail ("Amazon Delivery Cadence — Leo's Home — Exact Times, Last 365 Days").
A 4th (`2026-07-07-browser-verdict-dashboard-after-css.png`) separately showed
a live cross-repo task naming exposed-secret categories from a sibling private
repo. None of this is catchable by grep-gate or gitleaks — both read files as
UTF-8 text and silently skip binary PNGs on decode failure. **Fixed**: blanked
the sidebar region only (pixel-located via background-color-transition scan)
in the first 3, preserving the actual evidentiary content; removed the 4th
entirely (no clean crop possible), updating its accompanying doc to point at
a sibling clean screenshot as remaining proof of the same fix. Commit
`87c1b239`.

### 3. Grep-gate's own privacy-scanning tool hardcoded real corporate/coworker PII

`scripts/vidux-public-ready-grep-gate.py` reproduced the maintainer's real
corporate email verbatim in a comment; `tests/test_public_ready_grep_gate.py`
used a real, specific, named Snap coworker's email plus real internal
hostnames as literal test-fixture text — none of which the domain/TLD-based
regexes actually require to be real. **Fixed**: genericized the comment,
swapped in synthetic equivalents that exercise the identical regexes. Commit
`04f1b565`.

## P1 — real, fixed this round

### 4. DNS-rebinding Host-header bypass defeats round-8's write-route hardening

`is_allowed_request_host()` unconditionally returned `True` for the
`0.0.0.0`/`::` LAN-bind opt-in mode, letting a DNS-rebinding attacker's Host
header (agreeing with its own spoofed Origin) satisfy round-8's
`require_origin=True` check — `is_loopback_host()` doesn't catch it either,
since the rebound request's TCP connection genuinely originates from the same
machine. **Empirically proven exploitable**, not just theorized: the lens
started the server on `0.0.0.0`, sent a raw curl POST with `Host`/`Origin`
both set to an attacker domain, and got HTTP 200 with a real artifact file
written and a plan-note injected into a real `INBOX.md`; the identical
request against the default `127.0.0.1` bind correctly 403'd. Directly
contradicted `SECURITY.md`'s own written claim that the Host allowlist in
that mode "never" accepts an arbitrary domain. **Fixed**: applies the same
private-LAN-IP-literal check `_require_comment_write()` already used for its
own LAN-mode write path. New regression test. Commit `c4bbb319`.

### 5. `--cold` token fails WCAG 1.4.3 AA as receipts-pill text; `--error`/`--hot` untested at the same razor-thin margin; dark-mode `@media` fallback silently omits `--error`/`--warning`

Full-repo WCAG token sweep (not just `style.css`'s `:root` block, which is all
`test_style_contrast.py` previously read) found `--cold` (`#7d7466`) failing
at 3.907:1 as `receipts.html`'s "exportable" pill color — missed because that
usage lives in `receipts.html`'s own inline `<style>`, invisible to the test's
parsing. **Fixed**: darkened to `#71685c` (4.646:1), widened `TEXT_TOKENS` to
also assert `--error`/`--hot` (already passing, but at the identical
untested razor-thin margin that took 3 prior rounds to close for sibling
tokens). Separately, the bare `@media (prefers-color-scheme: dark)` fallback
block — a real, reachable path when a browser's `localStorage` throws and
`index.html`'s own FOUC-guard falls through to it — omitted `--error`/
`--warning` entirely, next to a comment that incorrectly asserted they were
"already handled" by the `:root.theme-dark` class block (which never applies
without that class). Computed the resulting failure at 2.86:1/2.84:1, far
below AA. **Fixed**: added the same values `:root.theme-dark` already uses
(no new colors invented), plus a regression test asserting the two blocks
stay in sync. Commits `c3f50428`, `ce5c338c`.

### 6. Claude Code plugin manifest fails Anthropic's own `claude plugin validate` — 5 schema errors across 3 files

Ran `claude plugin validate .` (2.1.206, matching the panel's own tool
version) and got 5 concrete errors: `plugin.json`'s `author` is a bare string
where the schema requires an object; `commands`/`hooks` keys are invalid when
declared explicitly (both directories are auto-scanned by convention);
`commands/vidux.md`'s frontmatter `description:` has an unquoted colon-space
that silently breaks YAML parsing (all frontmatter fields drop at runtime);
`hooks/hooks.json`'s array-of-objects shape doesn't match the record-keyed-
by-event-name shape the plugin hook loader requires, and its 5 declared event
names are cross-tool documentation concepts this repo invented, not real
Claude Code hook lifecycle events — no reshape would make it functionally
real. Per Anthropic's own docs, this exact validator gates plugin-marketplace
submission review, so this was a live, concrete blocker, not cosmetic.
**Fixed**: `author` → object, invalid keys removed, frontmatter quoted,
`hooks/hooks.json` renamed to `hooks/hooks-reference.json` (out of the
reserved auto-scan path), all doc/test references updated. Verified via a
clean `claude plugin validate .` → `✔ Validation passed`. Commit `03610a16`.

### 7. Round-8's doctrine/cross-reference fix only closed 1 of ~17 occurrences of the same bug

Round 8 fixed exactly one `SKILL.md` paragraph presenting `ledger-emit.sh
--event publish` as a directly-runnable command on the bundled, sourced-only
`scripts/lib/ledger-emit.sh` library — the identical incorrect claim still
appeared ~16 more times across `SKILL.md` (2 more spots), `LOOP.md`,
`docs/guide/installation.md` (a fenced example a brand-new user would
copy-paste and watch fail), `docs/reference/hooks.md`,
`docs/reference/prompt-template.md`, `guides/fleet-ops.md`,
`guides/draft-pr-flow.md`, `guides/recipes.md`,
`guides/recipes/lane-prompt-patterns.md`, and
`guides/recipes/claude-md-rules.md` — plus ~15 test assertions in
`tests/test_vidux_contracts.py` that actively pinned the incorrect literal as
required text. Also found in the same sweep: `SKILL.md`'s own `## The Cycle`
section names a 6th `COMPLETE` stage that `README`/`DOCTRINE.md`/
`ARCHITECTURE.md` all disagree with (5 stages); `SKILL.md:1092` still said
"12-principle" after `DOCTRINE.md` was fixed to 13; the superpowers-routing
table cited a `guides/automation.md` section that doesn't exist;
`docs/fleet/codex-setup.md` linked to a heading anchor that doesn't match its
real GitHub-generated slug; and `ARCHITECTURE.md`'s own diagram said "5
principles" 25 lines above an already-fixed "13 principles" line in the same
file. Renumbering also revealed that `guides/fleet-ops.md`/`guides/harness.md`/
`PLAN.md`'s private "Doctrine 13-16" citations (an April 2026 numbering
extension, never real in `DOCTRINE.md`) now collide with the corrected
numbering. **Fixed**: all of the above, across 2 commits (`fix(docs): remove
stale Doctrine-N citations...` `86d39b15`, `fix(docs): stop presenting
ledger-emit.sh as a directly-runnable CLI` `301b114c`), plus ~11 test methods
repointed to the corrected doc text and 3 new plugin-manifest regression
tests added in the same pass.

## Precisely re-scoped: commit-message employer-PII (round 8's "~20" estimate)

Round 8 escalated "~20 commits reachable from `origin/main`'s tip contain real
employer-machine linkage in their commit MESSAGES" based on only 3 hand-
verified samples. This round ran a full word-boundary sweep of all 750
commits reachable from `origin/main`'s current tip, manually verified every
candidate against a strict test (identifying detail + explicit employer tie
in the same message), and confirmed the **exact count is 4, not ~20**:

- `554121ee` — body names the maintainer's employer-machine home-directory
  path and a LaunchAgent plist naming convention tied directly to his
  employer-issued laptop.
- `7effa7ba` — body re-quotes the same employer-tied home path while
  describing its own (unrelated) redaction.
- `3a15fbb0` — body names a GitHub handle tied to the maintainer's employer
  identity.
- `d6a28c4d` — body quotes a real internal employer ML-infra project
  path/codename verbatim while describing its own removal.

14 other broad-pattern hits were checked and excluded as a different, lower-
severity class (generic "Snap Inc./Snap-confidential" business narrative with
no reproduced identifying string, already-bracketed placeholder text, or bare
personal-automation LaunchAgent labels with no employer context). This is a
confirmation/precise recount of the already-escalated finding, not a new leak
class — structurally invisible to grep-gate/gitleaks/secret-scan.yml since
none scan commit-message text. **Not mine to fix** — same class of decision
as `refs/pull/*/head`: rewriting reachable commit-message history is the
maintainer's call.

## Structural-blocker-impact-assessment: which escalations are TRUE hard blockers

A dedicated lens re-verified all 5 items previously escalated across rounds
7-9 independently against live git state (not by trusting prior prose) and
separated them:

**True hard blockers (2) — cap public release on their own merits, regardless
of any other fix:**

1. **`refs/pull/*/head` leak.** `git ls-remote`/`git merge-base
   --is-ancestor` confirm 5 permanent GitHub-server-maintained PR refs
   (`pr/1-5`) are ancestors of a commit whose message contains a live
   internal Snap endpoint hostname, and that commit is NOT an ancestor of
   `origin/main` — meaning a path-scoped history rewrite of the default
   branch does nothing for it. The instant repo visibility flips to public,
   anyone can `git fetch origin refs/pull/1/head` and read it.
2. **Commit-message employer-PII** (the 4 commits above), sitting in the
   default branch's own history, visible via plain `git log`, no PR-ref
   archaeology required.

**Risk-tolerable judgment calls (3) — real, worth resolving, but don't
independently block:**

3. Private-fleet-ecosystem content — large and real, but current file
   content, editable by ordinary redaction going forward, not an
   unpatchable leak. A strip/anonymize/keep disclosure-preference call.
4. `vidux.ai` naming collision — informational only.
5. Commit-authorship near-misses — the one `origin/main`-reachable instance
   uses the maintainer's own already-public business email (not accidental);
   the 9 employer-email-authored commits are confirmed unreachable from
   `origin` (dead local branches).

## New this round, real, not yet fixed — flagged for Leo/next round

- **Positioning concern (most philosophically significant new finding):**
  `SKILL.md` opens — before First-Time Setup, before the Five Principles —
  with a "Goal Navigation Plans" section naming multiple named model/harness
  workers, a "host's private router," and a three-way ownership-boundary
  split. This is exactly the Agent/Task/Crew/Gateway-style vocabulary the
  README's own comparison table cites as what orchestration frameworks
  require and vidux exists to avoid. A skeptical first-time reader evaluating
  "is this actually simple" by reading `SKILL.md` top-to-bottom hits
  fleet-orchestration complexity first, not last. This is a genuine tension
  with the session's own stated goal ("prove vidux as a simple middle
  ground") and a documentation-ordering/positioning call, not a mechanical
  bug — deliberately **not** unilaterally restructured this round; flagging
  for Leo's judgment rather than reordering SKILL.md's information
  architecture on my own read of "simple."
- `.claude-plugin/plugin.json`'s install path still has no cross-reference
  from README/ARCHITECTURE/DOCTRINE/SKILL.md, which only document the two
  manual-symlink paths (P2, correctly triaged non-blocking in rounds 8-9).
- Root `SKILL.md` and `commands/vidux.md` both declare `name: vidux` with
  substantively different content under the plugin loader's auto-discovery;
  which one "wins" when installed as a plugin was not empirically resolved
  (P2).
- `SKILL.md` names a couple of Claude-Code-specific tool/hook terms
  (`WebFetch`, `SessionStart`) without a platform guard, in an otherwise
  scrupulously multi-harness-neutral doc (P2).
- Evidence corpus: rounds 1-2 break the `panel-roundN` naming convention
  rounds 3-9 use, and no index maps round number to filename (P2, deferred
  since round 8; smallest fix would be one `evidence/INDEX.md`).
- `test_subplan_row_is_keyboard_and_screen_reader_accessible` only greps
  source strings, never drives a real keypress, despite the repo already
  having a proven Playwright pattern for exactly this in
  `browser/tests/e2e/smoke.spec.ts` (P2 — the item this round's own
  `p2-backlog-verify` lens most encouraged picking up next).
- `browser/static/receipts.html`'s page `<title>`/`<h1>` brands itself
  "moussey corpus lab," not vidux — a live, documented route
  (`docs/reference/browser.md`) in the shipped app with zero vidux branding
  (P2). Reviewed for a11y bugs across 3 prior rounds; branding itself never
  flagged until now.
- Click-to-annotate capture mode has no keyboard path to pick a target
  element once capture mode is active — same bug class as 2 already-fixed
  a11y findings, scoped to a secondary opt-in power feature; the always-
  present Plan-steering textarea already gives keyboard users a working
  comment path, so this doesn't block core functionality (P2).
- A commit message earlier this session claimed "4 new regression tests"
  when the diff added 3 — remedy is itself a commit-message history-rewrite
  decision, out of scope for unilateral action (P2, cosmetic).
- `.claude/settings.json`'s guarded `TaskCompleted` hook uses `A && B || C`,
  which also swallows a genuine nonzero exit from `gate-check.sh` itself, not
  just a missing file — real latent logic bug, but `gate-check.sh` is the
  maintainer's personal, never-shipped script, so no external cloner's shell
  state can ever reach the branch where this matters (informational only,
  not counted toward any verdict).

## Confirmed GO, no new findings

`security-full-sweep-round9` (fresh path-traversal/injection/Host-header
sweep, only a P2 informational `/api/health` LAN-mode leak, already a
documented tradeoff), `onboarding-fresh-clone-simulation-round9` (full fresh-
clone Quick Start + CONTRIBUTING walkthrough, zero genuine blockers),
`first-external-pr-stranger-resweep-round9` (hardcoded-sibling-repo-path
audit, only a P2 doc-completeness gap), `private-fleet-content-inventory-
round9` (broad re-sweep, one incremental addendum — a 7th sibling-repo path,
`~/Development/ai` — folding into the already-escalated bucket, no new
independent blocker), `evidence-directory-hygiene-recheck` (confirms round-8's
already-logged non-chronological-naming gap, no new finding),
`test-suite-integrity-round9` (spot-checked 4 round-8 regression tests via
revert/restore — all genuine, non-tautological), `license-attribution-round9`
(clean MIT chain, vendored `dompurify.min.js` hash-verified byte-identical to
upstream), `naming-branding-round9` (core "vidux" naming fully consistent
everywhere except the `receipts.html` finding above).

## Verification before commit

`python3 -m unittest tests.test_vidux_contracts` (229 tests) green; full
project-wide `python3 -m unittest discover -s tests -p 'test_*.py'` (739
tests, then 742 after this round's additional dark-mode-fallback test) green;
`npm run test:js` (8 tests) green; `npm run public-ready:grep` (348-349 files)
green — all re-verified after every commit in this round's batch.

## Next actions

Communicate this round's results to Leo: 7 fix categories shipped and pushed
(6 initial commits + 1 follow-up dark-mode fix), the commit-message-PII count
precisely re-scoped from "~20" to exactly 4, and the structural-blocker
assessment's conclusion that only 2 of the 5 standing escalations are true
hard blockers on repo visibility — the other 3 are judgment calls. Surface the
new positioning finding (Goal Navigation Plans ahead of Five Principles in
`SKILL.md`) as a design decision for Leo, not something to fix unilaterally.
Update the standing task tracker. Decide whether round 10 should focus on the
accumulated P2 backlog (7+ items now catalogued across rounds 8-9, none
individually blocking) or open entirely fresh ground, given that literal
20/20 GO is structurally capped until Leo resolves the 2 confirmed hard
blockers (`refs/pull/*/head`, commit-message PII) and the positioning
question.

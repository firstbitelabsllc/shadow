# Panel round 8: 10/18 GO

Purpose: adversarially re-verify round 7's 11 fixes (grep-gate patterns,
worktree-gc documentation, README/PLAN.md/config.ts kernel-cut scan,
WCAG contrast, subplan-row a11y, dead-code removal, secret-scan.yml
YAML) plus fresh ground round 7 didn't have time for given how much of
it was spent re-verifying rounds 4-6.

**Result: 10/18 GO, 8/18 NO-GO.** The script constructed only 19 lens
entries instead of the intended 20 (root cause not found — an earlier
`grep -c "key:"` count of 20 was apparently a miscount); of those 19,
one (`security-pass-round8`) failed outright with a `StructuredOutput`
retry-cap exceeded (5 failed calls, zero signal — not re-run standalone
this round, since its one concrete finding was directly actionable and
got fixed anyway, see below) and one (`first-external-pr-stranger-
resweep`) degenerated to literal placeholder "test" content (same
failure mode seen in rounds 4, 6, and 7 for other lenses — not re-run
standalone; lower priority since a prior round already has real signal
on this exact topic, the 11 module-level path constants issue). 18 real
verdicts resulted.

## P0 — most severe, found this round

### 1. The maintainer's real spouse's first name appeared in 5 tracked files

4 `evidence/*.md` files plus `.gitignore`. One instance was genuinely
sensitive — a confidential job-search-leads screenshot title, describing
content already purged from the branches that carried it. The rest were
a recurring "simple enough for X" persona shorthand or a machine-nickname
code comment. **Fixed**: genericized every instance (a non-technical
family member / person / every machine in the fleet) without losing the
substance of any finding they were documenting. Added a `PRIVACY_PATTERNS`
rule for the name with a regression test, which immediately surfaced one
more instance in `.gitignore` also fixed in the same pass. Commit
`c3f1e13c`.

### 2. NEW, not previously known: ~20 commits reachable from `origin/main`'s current tip contain real employer-machine linkage in their commit MESSAGES, not file content

Independently verified (not just relayed from the panel) via direct
`git show -s --format=%B` on 3 sample commits, all confirmed ancestors of
`origin/main`'s current tip:

- One commit's message names the maintainer's employer-machine home
  directory path and a LaunchAgent plist naming convention that ties
  directly to his employer-issued laptop.
- A second commit's message quotes, verbatim, a private-project-name list
  while describing its own (unrelated) redaction — i.e., the act of
  documenting a fix re-introduced the leak into the commit message itself.
- A third commit's message uses a GitHub handle that is itself tied to the
  maintainer's employer identity.

This is a structurally distinct leak vector from everything else found
across all 8 rounds: file-content grep-gate, gitleaks, and
`secret-scan.yml` scan tracked file content, never `git log` commit
message text. None of the existing scanning infrastructure can see this
class of leak, by design of what those tools scan. **Not mine to fix** —
same class of decision as the `refs/pull/*/head` finding from round 7:
rewriting reachable commit-message history is exactly the kind of
destructive/irreversible git-history operation reserved for the
maintainer under the standing carve-out. Escalated below.

## P0/P1 — real, fixed this round

3. **Doctrine/cross-reference accuracy, 5 separate drifts in core doc
   files, all independently verified against actual code/content:**
   - `DOCTRINE.md` claimed "12 principles" in its intro but numbered 1-12
     then jumped to a stray, unrenumbered `### 14. Hungry by default`
     (wrong number and wrong heading level) — a leftover from an earlier
     renumbering that missed this one entry. Fixed to `## 13.`, updated
     the doc's own intro and `ARCHITECTURE.md`'s cross-reference to "13
     principles", widened the pinning contract test.
   - `LOOP.md` cited "SKILL.md § Failure Protocol" — that section doesn't
     exist anywhere in SKILL.md. Repointed at the real section, "Stuck
     detection (adaptive)".
   - `guides/harness.md` attributed a quote ("Every agent finds work AND
     does work") to "(SKILL.md)" — it actually lives verbatim in
     DOCTRINE.md. Fixed the attribution.
   - SKILL.md's core Push-authorization doctrine described `ledger-emit.sh
     --event publish` as if it were a CLI flag on the bundled, sourced-only
     `scripts/lib/ledger-emit.sh` library (confirmed via reading the file:
     pure bash function definitions, no `--event` flag parsing anywhere).
     The real `--event`/`--summary`/`--eid` interface is a separate,
     optional, pluggable executable contract (`vidux-release.sh
     --ledger-emit <path>`, which no-ops by design if unset). Clarified the
     doctrine text to match reality; fixed the one regression test whose
     exact-substring check broke as a result.
   - README's "3x stuck rule" was described twice as "= auto-exit" —
     `vidux-loop.sh`'s own code comment says default mode only *reports*
     the stuck state; auto-blocking the task in PLAN.md requires the
     `VIDUX_LOOP_AUTO_BLOCK=1` opt-in. Corrected both mentions, plus a
     dangling "(see `guides/`)" pointer for Persistent Loop/Nursing/
     Coordination Mode that pointed nowhere (those 3 modes are documented
     only inline in SKILL.md, confirmed via grep that `guides/*.md` has
     zero hits for the mode names). Commit `7a41b112`.

4. **Cross-tool/harness parity: `.claude/settings.json`'s `TaskCompleted`
   hook pointed unconditionally at `$HOME/.claude/hooks/gate-check.sh`** —
   the maintainer's personal global script, not shipped with this repo.
   Any other Claude Code user cloning vidux would silently dangle on that
   missing path. **Fixed**: guarded the command to test for existence and
   no-op cleanly otherwise. New contract test asserting the guard is
   present. Commit `31a09e23`.

5. **WCAG 1.4.3 AA: `--warning` (`#8a7a3e`) failed contrast as the `color:`
   on `.ops-chip.is-warn`'s 11px text** (3.91:1 vs `--paper`, 3.61:1 vs
   `--paper-2`, both below the 4.5:1 floor) — the same bug class already
   fixed once for 4 sibling status tokens in round 4/7, this one was
   missed. **Fixed**: darkened to `#776936` (4.98:1 / 4.62:1), same
   hue/saturation-preserving method as prior rounds. Also added
   `--task-blocked` to the regression test's token set — it already passed
   (4.97:1/4.59:1) but had never actually been asserted. Commit `31a09e23`.

6. **The 3 per-card annotation inputs on `/receipts`** (tags, known
   issues, note) had placeholder text only, no `<label>`/`aria-label` —
   invisible to screen readers despite being the primary way to annotate a
   receipt. **Fixed**: added `aria-label` to all 3, scoped per receipt id.
   New regression test. Commit `31a09e23`.

7. **Security: write routes fell back to "allow" when both `Origin` and
   `Referer` were absent.** `_require_json_write()` (gating `/api/artifact`,
   `/api/local-plan-note`, and all `/api/receipts/*` routes) called
   `_require_browser_json()` with the default `require_origin=False`,
   unlike `/api/comments`'s `_require_comment_write()`, which already
   passed `require_origin=True`. The lens itself characterized this as
   "hardening, not a shippable blocker" — not exploitable from a real
   browser (a JSON POST is preflighted, and every real cross/same-origin
   browser POST attaches `Origin`), but a process that can already reach
   loopback directly (curl, a local binary) shouldn't get a free pass
   either. **Fixed**: flipped the default to `require_origin=True`,
   matching `/api/comments`. New regression test
   (`test_plan_note_post_requires_origin_or_referer`), confirmed failing
   pre-fix (200, not 403) via `git stash`, passing post-fix; full suite
   (734 tests) + JS tests + grep-gate all green before commit. Commit
   `43a3667e`.

## Escalated to Leo, unresolved, explicitly not my call

Per the standing carve-out this whole session: I perform all
remediation/build/review work myself, but repo-visibility and any
destructive git-history operation are the maintainer's explicit, separate
decision, regardless of panel verdict.

1. **NEW this round, most severe: ~20 commits reachable from
   `origin/main`'s current tip carry real employer-machine linkage in
   their commit MESSAGES.** Structurally invisible to grep-gate, gitleaks,
   and `secret-scan.yml` (none scan commit-message content). Same remedy
   class as item 2 below: a maintainer decision on rewriting reachable
   history (`git filter-repo --message-callback` or equivalent) vs.
   accepting the risk while the repo stays private.
2. **`refs/pull/*/head` leak** — unchanged from round 7's corrected
   understanding: still live via 5 permanent GitHub-server-maintained PR
   refs, independent of any `origin/main` history rewrite. Not urgent
   while the repo stays private; blocks ever flipping visibility until
   resolved (full repo recreation, or a GitHub support request to purge
   specific refs).
3. **Private-fleet-ecosystem content — confirmed even larger in scope than
   round 7's catalogue.** Round 7 already flagged: a shipped Python module
   whose purpose is exporting data into one of the maintainer's other
   private apps' test-fixture tree; a dedicated onboarding doc naming 6
   real private repos; two full private-automation-fleet blueprint files;
   a script with ~20 hardcoded private lane IDs; a slash-command with real
   repo names in its example output. Round 8 found 7 more: full cross-repo
   audit data from 2 sibling private repos baked into an evidence file;
   GitHub-org-split/business-rebrand history narrated in `CHANGELOG.md`; a
   real legacy-repo-alias mapping hardcoded as literal test-fixture data in
   `tests/test_browser_server.py`; a paid-tooling rollout strategy document
   naming two of the maintainer's other real products by name; cross-
   machine work-routing rules naming real repos in an evidence file; a
   meta-doc whose own "already scrubbed" inventory lists real project/lane
   names; and historical automation-lane names for two other real products
   in `ARCHIVE.md`. Strip, anonymize, or keep — maintainer's call, not mine
   to resolve unilaterally.
4. **`vidux.ai` naming collision** — informational only, unchanged from
   prior rounds.
5. **Commit-authorship near-misses** — unchanged from round 7: one commit
   reachable from `origin/main` (tagged in a recent version bump)
   authored with the maintainer's separate small-business email instead of
   his usual identity; 9 further commits, confirmed NOT reachable from
   `origin`, locally authored with his real employer corporate email (a
   near-miss, not a live leak).

## Not yet addressed — concrete, lower severity, deferred

- `.claude-plugin/plugin.json`'s install path diverges from README's
  manual-symlink instructions, undocumented.
- SKILL.md names Claude-Code-specific tool calls in a few spots without a
  platform guard for other harnesses.
- The evidence corpus is non-chronologically named with no index, making
  it hard for a fresh reader to reconstruct the audit trail.
- A commit message earlier this session miscounted "4 new regression
  tests" when the actual diff added 3.
- `test_subplan_row_is_keyboard_and_screen_reader_accessible` only greps
  source for the right attributes/strings rather than driving real
  keyboard behavior end-to-end.

All lower severity than the P0/P1 items above; reasonable to defer to a
future round rather than fix now.

## Next actions

Communicate this round's results and the two escalated items (commit-
message PII being the new, most severe one) to Leo. Update the standing
task tracker. Before launching round 9: fix the 19-vs-20-lens script
discrepancy if reusing a similarly-scoped panel script, and decide
whether to spend a round specifically re-verifying this round's 7 fixes
or to open fresh ground given how much signal has now accumulated in the
"escalated to Leo" bucket versus fixable-by-me findings.

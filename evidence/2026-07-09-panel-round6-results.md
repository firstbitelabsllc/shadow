# Panel round 6: 15/20 GO

Purpose: fresh sweep verifying round-5 fixes, with lens prompts specifically
targeting what changed. All 20 lenses ran; 1 degenerated (placeholder
content, same failure mode as round 4's `positioning-honesty`).

**Result: 15/20 GO, 5/20 NO-GO** (1 of the 5 is degenerate, not real signal
— effectively 15 GO / 4 real NO-GO / 1 needs-rerun).

## P0 — highest priority, unresolved

### 1. NEW, not previously found in any round: a commit on `origin/main` is authored with the maintainer's OTHER private-business email

`experienced-oss-contributor` checked git commit *metadata*, not just file
content — something no prior round did. Finding:

- Commit `686a4686` (message: "vidux: put Rising Tide Doctrine on trunk...")
  is reachable from `origin/main` (`git merge-base --is-ancestor` confirms)
  and is tagged in `v2.23.0` (confirmed via `git ls-remote --tags origin`)
  — the exact tag this session cut earlier today to match `package.json`.
- Its author email is `trysnowcubes@gmail.com` — the maintainer's separate
  small consumer-goods business, entirely unrelated to First Bite Labs or
  vidux.
- **No tool in this repo could ever catch this.** `vidux-public-ready-
  grep-gate.py`'s `PRIVACY_PATTERNS` only scan tracked *file content*;
  `.gitleaks.toml`'s detectors target credential *patterns*, not personal
  email addresses in commit *authorship*. This is a structurally different
  leak vector than everything found and fixed across rounds 1-5.
- Per round 3's own count, "the redaction pass believed itself complete"
  has now recurred 6 times before this session even started finding new
  instances; this is the 7th, at a layer nobody thought to check.
- **Same remediation class as the already-tracked `refs/pull/*` decision**
  (surgical rewrite vs. full repo recreation) — if a repo recreation
  happens for that item, it would very likely fix this one too, for free.
  **Not deciding this myself — raising to Leo alongside the existing
  refs/pull/* decision**, since they may share one resolution.

### 2. `scripts/vidux-worktree-gc.py`'s two-tier redesign (shipped this session, TODAY) still has a real, reproduced data-loss gap

Third round in a row finding a new hole in the same mechanism. This round's
`worktree-gc-two-tier-verify` lens reproduced, via the real `--apply --yes`
CLI in a scratch repo, confirmed via `git fsck`/blob-grep afterward:

- **Nested-ancestor bypass**: `non_regenerable_ignored_paths()` checks
  `any(part in UNAMBIGUOUS_REGENERABLE_DIR_NAMES for part in
  rel_path.parts[:-1])` — this matches ANY ancestor path segment, not just
  the actual ignored boundary. A file at `stuff/node_modules/IMPORTANT.txt`,
  where `stuff/` is itself gitignored and NOT an unambiguous name, is fully
  trusted purely because "node_modules" appears somewhere in its ancestry
  — permanently deleted in the repro. This directly contradicts this
  session's own redesign comment ("everything else... gets zero
  directory-based trust") and is inherited, unfixed, from round 4's
  original logic.
- **`.log` suffix coincidence** (P1, separate root cause): a hand-authored
  `cache/diary.log` (a very plausible real filename — a diary, a notes
  file) inside a correctly-untrusted ambiguous directory is silently
  trusted purely by extension match against `REGENERABLE_IGNORED_FILE_
  SUFFIXES = {'.pyc', '.pyo', '.log'}` and was permanently deleted.

## P1 — concrete, fixable, not yet done

1. **`vidux-public-ready-grep-gate.py`'s `docs/.vitepress` entry is the
   same bare-directory-exemption bug just fixed for `tests/`, one entry
   over, in the same file.** `EXCLUDED_RELATIVE_PATHS` has
   `Path("docs/.vitepress")` with no comment and no regression test —
   exempts the entire tree, not just the one file (`config.ts`) that lives
   there today. Reproduced live: a new file under that tree carrying real
   leak strings produces zero matches. Nothing is leaking through it
   *today*, but it's the identical structural blind spot. Fix: narrow to
   `Path("docs/.vitepress/config.ts")`, same pattern as the `tests/` fix.

2. **This session's own README fixes from round 5 introduced NEW,
   independently-unverifiable claims** (`readme-positioning-verify`):
   - The Hermes Agent provider-count fix shipped "20+" in the actual diff,
     while the commit message and round-5 evidence file both claimed "24+"
     was verified — internally inconsistent, and NEITHER number is
     demonstrably sourced from Hermes's own docs (ambiguous phrasing
     implying >26 total; a dedicated providers page lists 37 named
     providers; the "24+" figure traces to a third-party blog that
     explicitly disclaims Nous Research affiliation).
   - The OpenCode fix swapped "LiteLLM" (wrong) for "OpenRouter" (also not
     what OpenCode's own docs cite — they say "the AI SDK and Models.dev").
     The upper bound of the shared "75-100+" range also doesn't clearly
     trace to either product's own documented count (OpenCode: 75+;
     LiteLLM, which Aider actually uses: 140+ per LiteLLM's own docs).
   - Root cause both times: fixing a wrong citation by substituting a
     plausible-sounding replacement instead of pinning down the primary
     source's exact current language before shipping.

## Needs a clean re-run (degenerate this round)

- `skill-doctrine-coherence-verify` returned a real JSON envelope but with
  placeholder content (`summary`/`title`/`detail` all literally `"test"`)
  — same failure mode as round 4's `positioning-honesty` first attempt.
  Not counted as a trustworthy NO-GO.

## Confirmed holding up / non-blocking findings

- The round-5 worktree-gc fix for extensionless files and case-variant
  extensions (`build/CLIENT-HANDOFF-NOTES`, `vendor/deep/nested/AUTHORS`,
  `dist/Client-Deal-Terms.PDF`) is genuinely fixed — all three repro
  strings from round 5 now correctly block removal.
- The accepted trade-off (a genuine `dist/`/`build/` full of real output
  now requires manual review instead of auto-cleanup) works exactly as
  documented.
- Round-5's grep-gate `tests/` narrowing genuinely works — verified with 5
  different real leak strings across 5 different test files, all now
  caught; the 2 legitimately-exempt files correctly stay exempt.
- Both crash-hardening fixes (grep-gate OSError, worktree-gc missing-`gh`)
  hold up under independent re-verification.
- ASK-LEO.md's scrub, GitHub topics, SUPPORT.md/CODE_OF_CONDUCT.md fixes,
  the WCAG contrast fix, and the SKILL.md automation-entrypoints table fix
  (path + deprecation tags) all confirmed holding.
- `refs-pull-tracking-accuracy`, `naming-and-simplicity-tracking`,
  `private-fleet-scope-tracking`: all three maintainer-owned-decision
  tracking notes confirmed still accurate, correctly not re-litigated.
- Full test suite green, `security-secrets-leaks` GO (file-content layer
  clean — see P0-1 above for the metadata-layer exception this lens
  doesn't check).
- P2, non-blocking, documented but not fixed: a literal top-level
  `node_modules/` with one hand-patched file (the common `patch-package`
  workflow) is deleted exactly as the two-tier design intends — the
  module comment's "no human ever hand-populates" framing isn't literally
  true for this common pattern and deserves a one-line caveat, not a
  behavior change. A symlink nested inside a trusted directory is
  classified removable without inspection; survives today only because
  `git worktree remove` doesn't dereference symlinks — an unstated
  reliance on git's own behavior, not verified by this script itself.

## Also found, not from this repo's file-content history: 9 commits locally authored with the maintainer's real Snap Inc. corporate email

Confirmed via `git ls-remote origin` / `git branch -r --contains` that
none of the local-only branches/tags carrying these 9 commits currently
exist on `origin` (origin's same-named branches are at different,
already-rewritten SHAs). Zero public exposure today — a near-miss, not a
live leak. Flagging as a reminder: inventory and delete/rewrite these
local-only refs before any future operation that could push them
(cleanup, backup restore, accidental `git push --all`), separate from the
origin-side audits rounds 1-6 have run.

## Next actions (in order)

1. **DONE 2026-07-09** — Fixed `worktree-gc`'s nested-ancestor bypass
   (P0-2): directory trust now checks `rel_path.parts[0]` only, not any
   ancestor segment. Removed `.log` from the global suffix allowlist (P1).
   3 new regression tests added, all confirmed fail pre-fix via
   `git stash`. Commit `a0240a2c` (landed by a concurrent lane running the
   identical fix; verified byte-identical via `git diff HEAD` before
   confirming, not duplicated).
2. **DONE 2026-07-09** — Fixed the `docs/.vitepress` grep-gate exemption
   (P1-1): the bare directory entry is removed outright (not narrowed —
   the only tracked file there, `config.ts`, needed no exemption at all;
   `dist/` is already git-ignored and dropped separately). Regression test
   added, confirmed fails pre-fix. Commit `845c632b`.
3. **DONE 2026-07-09** — Redid the README Hermes/OpenCode citations against
   verified primary sources fetched live: `hermes-agent.nousresearch.com/
   docs` (install is a single script, no separate Python/Node.js step;
   Nous Portal states "300+ frontier agentic models" via one OAuth login —
   no clean single "N providers" count exists to cite, so the cell now
   quotes the actual setup flow instead); `opencode.ai/docs/providers`
   (AI SDK + Models.dev, 75+ providers — confirmed, kept); Aider uses
   LiteLLM, a distinct mechanism from OpenCode's — split into two clauses
   instead of one merged imprecise number. Commit `3e1cc38d`.
4. **DONE 2026-07-09** — Added the node_modules-hand-patched-content doc
   caveat (P2): documents that the `patch-package` workflow hand-edits
   files inside `node_modules/`, without changing behavior (still correctly
   regenerable from the committed `.patch` + `package.json`). Commit
   `6b91725f`.
5. Raise the NEW commit-authorship leak (P0-1) and the Snap-email
   local-only near-miss to Leo directly, alongside the existing refs/pull/*
   decision — not resolving either myself. **Not yet done as of this
   update** — surfacing next.
6. Re-run `skill-doctrine-coherence-verify` standalone before folding into
   round 7's count. **Not yet done as of this update** — next.
7. Round 7 once 1-6 are shipped/resolved.

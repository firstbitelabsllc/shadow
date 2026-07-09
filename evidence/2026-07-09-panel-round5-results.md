# Panel round 5: 12/20 GO — all 20 lenses produced real signal (no degenerate/contaminated runs this time)

Purpose: fresh 20-lens sweep re-verifying every round-4 fix plus new angles.
Unlike round 4, all 20 lens agents completed with real, usable output — no
retry-cap errors, no placeholder content, no cross-contamination.

**Result: 12/20 GO, 8/20 NO-GO.**

## P0 — highest priority, unresolved

### 1. `worktree-gc-edge-cases`: the round-4 HUMAN_AUTHORED_SUFFIXES fix has two live gaps, both reproduced causing real permanent data loss

Round 4 fixed the directory-name-trust data-loss bug by adding a
`HUMAN_AUTHORED_SUFFIXES` override. Round 5 adversarially tested that exact
fix and found it incomplete in two ways, both reproduced via the real CLI
(`--apply --yes`, not theorized):

- **Extensionless files** (`Path(name).suffix == ''`) never match
  `HUMAN_AUTHORED_SUFFIXES` and fall straight through to directory-name
  trust. Reproduced 3x: `build/CLIENT-HANDOFF-NOTES` (top-level),
  `vendor/deep/nested/AUTHORS` (3 levels deep), `build/客户备忘录` (unicode
  filename) — all classified `merged_clean`/`removable`, all permanently
  deleted by `--apply --yes`, confirmed gone from the object store via
  `git fsck`/blob grep (not just untracked — genuinely unrecoverable).
- **Case-sensitive suffix matching**: `HUMAN_AUTHORED_SUFFIXES` only has
  lowercase entries, and the membership check is a plain set lookup with no
  normalization. `dist/Client-Deal-Terms.PDF` (uppercase extension) falls
  through the same way — reproduced, permanently deleted.
- The `-z --untracked-files=all` part of the round-4 fix genuinely works
  (unicode/space filenames correctly enumerated, nested dirs correctly
  recursed) — the gap is entirely in the suffix-allowlist logic downstream,
  not the git-status parsing.
- Confirmed as a non-finding: a symlink inside an ignored dir pointing
  outside the worktree does NOT endanger the target — `git worktree remove`
  doesn't follow symlinks destructively.

**Action: fix immediately** (see remediation below) — this is a real,
reproducible data-loss bug in code this session shipped as a fix for a
data-loss bug.

### 2. `experienced-oss-contributor`: vidux ships hardcoded infrastructure and business context from the maintainer's other private commercial products

Not a credential leak (independently grepped clean of api-key/token/secret
patterns) but a real, repeated business-scope leak the grep-gate
structurally cannot catch (no PRIVACY_PATTERNS rule exists for these
product names as bare strings):

- `scripts/vidux-fleet-rebuild.sh` hardcodes `$HOME/.codex/sqlite/codex-dev.db`
  and a literal array of the maintainer's private automation lane IDs
  across his other two commercial products.
- `investigations/draft-pr-flow.md` is a full audit table of 37 of the
  maintainer's private automation lanes across those products plus vidux
  itself, sourced from grepping his personal `~/.claude/automations` and
  `~/.codex/automations` directories.
- An entire `agent/` tree (added via a merged PR, "Eve local cockpit")
  ships an onboarding doc naming 4 more private repos plus a private skills
  overlay — in cleartext, despite the doc's own prose calling it private.
- `package.json` wires this in live via two npm scripts.
- The same pattern recurs in currently-live doctrine: `guides/
  figma-net-new-project.md`, `guides/recipes/lane-prompt-mirror.md`,
  `guides/recipes/the-rip-pattern.md`, `prompts/goal-navigation-control-
  plane.prompt.md`, `commands/vidux-status.md` (a worked example literally
  showing the other products' progress bars), `scripts/vidux-fleet-quality.sh`.

**This is a scope decision, not a mechanical bug fix** — these aren't
generic vidux features with an accidental private-string leak (the pattern
this session has fixed repeatedly elsewhere); they're the maintainer's
personal multi-product fleet-ops tooling that happens to live in this repo.
Anonymizing the strings would leave dead, non-functional, single-user
automation — not a generic feature other users could use. The real
question is whether this content ships at all (heavily anonymized) or gets
stripped out as out-of-scope private tooling entirely. **Not deciding this
myself — flagging to Leo**, same category as the `refs/pull/*` and naming
decisions already tracked.

## P1 — concrete, fixable, not yet done

1. **`grep-gate` `tests/` exclusion is too broad** (confirmed independently
   by both `grep-gate-scan-completeness` and `code-quality-cli-scripts`
   lenses): `EXCLUDED_RELATIVE_PATHS` denylists the entire `tests/`
   directory (36 files) via `Path("tests")`, when the script's own comment
   only justifies exempting 2 specific files (`test_public_ready_grep_gate.py`
   for self-reference, `test_vidux_contracts.py` for pinned fixtures). Both
   lenses reproduced live: a scratch file dropped into `tests/` containing
   the same employer-source-path/email leak-class strings this gate's
   patterns exist to catch passes with zero matches. Same failure mode
   round 4 fixed for top-level files, recurred one directory level down.
   Fix: exempt only the 2 named files.

2. **`ASK-LEO.md` ships real, unscrubbed internal content at repo root**
   (flagged in round 1 and round 3, still unaddressed): contains Leo's
   actual name, a reference to "the maintainer's private overlay skill,"
   and a Q&A entry naming the repo `leojkwan/vidux` (not the real
   `firstbitelabsllc/vidux`) — proving this is carried-over real history,
   not a template. Fix: replace with an empty/example file, matching the
   `vidux.config.example.json` vs real-gitignored-config pattern already
   used elsewhere in the repo.

3. **GitHub repo topics are unset** (`gh api repos/firstbitelabsllc/vidux
   --jq .topics` → `[]`). Description is good; zero topics means no
   topic-based discovery when flipped public. Mechanical fix via `gh repo
   edit --add-topic`.

4. **`SKILL.md`'s Automation Entrypoints table points to the wrong path and
   hides deprecation status**: says "reference the automation recipes from
   `guides/recipes/`" (a directory with an unrelated catalog) when the real
   8-recipe content lives in the sibling file `guides/recipes.md`. Worse,
   that real source file marks 2 of the 8 rows (Fleet Watcher, Observer
   Pair) DEPRECATED ("orchestration smell," "do not build new X lanes") —
   SKILL.md's table presents both normally with zero deprecation flag,
   right before telling the agent to "start with the smallest recipe."
   Fix: repoint the path, add `[DEPRECATED]` tags, fix row 3's title
   (SKILL.md says "Draft-PR Lifecycle," real title is "PR Lifecycle Manager").

5. **README comparison-table inaccuracies** (`positioning-honesty-verify`):
   - LangGraph's production path is documented (by LangGraph itself) as
     needing Docker + Postgres + **Redis**, not pgvector as README claims.
   - Hermes Agent "17+ model providers" is stale — Hermes's own docs
     currently say "24+ providers."
   - OpenCode is attributed to LiteLLM in the same row as Aider; OpenCode's
     actual provider layer is Vercel AI SDK + Models.dev, not LiteLLM.

6. **`receipts.html`'s file-upload input has no accessible label**
   (`accessibility-full-sweep`, P1): the only input on the page missing a
   label, and — because the neighboring dropzone div isn't in the tab
   order at all — it's the sole keyboard/screen-reader-reachable upload
   path. One-line fix: add `aria-label`.

7. **Two crash-hardening gaps** (`code-quality-cli-scripts`, non-blocking
   but real): grep-gate dies with an unhandled `PermissionError`/
   `FileNotFoundError` traceback (not a clean JSON failure) on an unreadable
   or mid-scan-deleted file — indistinguishable from a real leak by exit
   code alone; `vidux-worktree-gc.py` crashes with an unhandled
   `FileNotFoundError` when `gh` isn't on PATH, with zero preflight or
   documentation that `gh` is a hard dependency.

## P2 — non-blocking, worth a pass

- `SETUP_NEW_MACHINE.md` content is actually fine (genuinely genericized)
  but orphaned — not linked from README or any onboarding doc.
- Sidebar listbox container (`index.html`) keeps a static `tabindex="0"`
  after rows populate, producing a dead/duplicate Tab stop.
- Selecting a plan never moves focus into the content pane despite a
  `tabindex="-1"` clearly placed there for exactly that purpose — dead code,
  WCAG 2.4.3-adjacent gap.
- Comment-marker/target-chip hover-preview has no keyboard-focus equivalent
  (WCAG 1.4.13-flavored gap).
- Three per-row annotation inputs in `receipts.html` rely on placeholder-only
  labels (SC 3.3.2 best-practice gap, likely not an outright SC 4.1.2 fail).
- `marked.js` loaded from a CDN rather than vendored (inconsistent with
  `dompurify.min.js` being vendored locally); degrades gracefully via a
  documented fallback, so non-blocking.
- Worktree-gc's porcelain parser never reads the "locked" key, so a locked
  worktree can show `removable: true` in read-only output even though git
  will refuse to actually remove it — misleading, not destructive.

## Confirmed holding up under independent re-check (no action needed)

- `fresh-clone-buildability`: full Quick Start flow genuinely works
  end-to-end with the round-4 clone-path fix, including a live plan created
  from an unrelated cwd correctly appearing in `/api/plans`.
- `refs-pull-tracking-accuracy`: independently re-verified via a fresh
  `git clone --bare` covering ALL 133 live refs (not just the 5 round 4
  sampled) — the P0-1 tracking note is still fully accurate, nothing has
  gotten worse or spread further. Correctly not re-litigated as a fix target.
- `naming-branding-tracking` / `simplicity-niche-fit`: both re-confirmed
  accurately tracked as informational/non-blocking, maintainer-decides items.
- `security-secrets-leaks`: GO, full history + all branches + all PR refs
  clean of credentials.
- `dependency-health`, `test-suite-trust`, `playwright-hermeticity-verify`,
  `code-quality-browser-js`, `contribution-readiness`, `first-run-ux`: all GO.
- **Round-4's WCAG contrast P2 claim is downgraded, not confirmed**: this
  round independently recomputed contrast ratios for the fixed tokens
  (`--task-shipped`, `--task-in-review`, `--task-completed`, `--task-blocked`,
  `--accent`, `--ink-2`) — all land between ~4.58:1 and ~8.6:1, clearing the
  4.5:1 AA bar (some by a thin ~0.08-0.16 margin). The fix shipped earlier
  this session is confirmed correct and sufficient.

## Next actions (in order)

1. Fix the P0 worktree-gc extensionless/case-sensitivity gap immediately —
   real, reproduced, ongoing data-loss risk in currently-shipped code.
2. Fix the grep-gate `tests/` over-exclusion (P1-1) — narrow scope, high
   confidence.
3. Fix the small, unambiguous P1s: ASK-LEO.md scrub, GitHub topics,
   SKILL.md automation-entrypoints table, README comparison-table
   corrections, receipts.html upload-input label.
4. Raise the private-fleet-ecosystem finding (P0-2) to Leo directly —
   this is a scope decision (strip vs. anonymize vs. keep), not something
   to unilaterally resolve.
5. Time permitting: the two crash-hardening P2s and the P2 accessibility
   items.
6. Round 6 once 1-3 are shipped.

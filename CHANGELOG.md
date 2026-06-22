# Changelog

All notable changes to vidux are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/) — minor bumps may
tighten doctrine; major bumps change the cycle or `PLAN.md` shape.

## [Unreleased]

### Added
- `scripts/vidux-step-journal.sh` — append-only JSONL step journal for crash-safe intra-row resume (idempotency key = row+step; record/is-done/resume-point/status/clear). STEP-level replay on top of the row-level cycle checkpoint, for crons/lanes lacking top-level idempotency. ShellCheck-clean, jq-only.
- Snowcubes imagegen Wave 022-033 resume pointers in `PLAN.md`, plus a shorter root `SKILL.md` description for Captain/frontmatter routing.
- **Harness Contract block 8 — the done-state contract (vidux-amp-10x).** CONVERGENCE & FINDABILITY block in `## Harness Contract` (`SKILL.md`) defining `done = merged + findable`. Status ladder `branch_pushed < pr_open < merged < findable` ("done"/"complete" deleted from the vocabulary); a row is `[completed]` only with a trunk merge SHA AND a typed `[Findable: …]` locator (a green draft PR is `pr_open`); shipped/done/live reserved for merged-to-trunk; convergence-pass trap (>3 stranded branches blocks new fan-out, default 3); stacking discipline (own the base's merge or integrate before handoff). Added a `[merged]` rung to the FSM diagram. Motivated by the 2026-06-13 stranded-work failure.
- Convergence-ladder unit test `test_handoff_status_convergence_ladder`.

### Changed
- `scripts/lib/ledger-emit.sh` `_vidux_handoff_status` now emits the convergence ladder. Ladder rungs pass through; legacy `done`/`completed` map to `merged` only when `VIDUX_MERGE_SHA` proves the merge, otherwise demote to `pr_open`.

---

## [2.26.13] - 2026-05-25

Fixed `scripts/vidux-asc-bridge.py` silent skip of bare, paren-wrapped, and uppercase-space ASC ID formats now in active use on resplit-ios PR titles. Replaced the single bracket-bound `ASC_ID_RE` with two case-bounded regexes used in order by `parse_asc_id`:

- `_DASH_RE = re.compile(r"(?<![A-Za-z0-9])asc-([A-Za-z0-9_-]{3,})", re.IGNORECASE)` — covers `[asc-XXX]`, bare `asc-XXX`, `(asc-XXX)`, trailing text. Literal `-` separator + 3-char min eliminates fuzzy collisions.
- `_SPACE_RE = re.compile(r"(?<![A-Za-z0-9])ASC[\s]+([A-Za-z0-9_-]{3,})")` — covers manually-typed `ASC <id>`. **No `IGNORECASE`** — the uppercase `ASC` literal blocks lowercase prose from false-matching.

Both share a `(?<![A-Za-z0-9])` lookbehind so mid-word sequences can't match. Captured ID is lowercased (matches LI-15 convention). Added 8 unit tests in `tests/test_asc_bridge.py::TestParseAscId`. Fifth instance of the silent-loss class (after LI-12/14/15/16). Code-only ship per the LI-12 claim+ship-in-separate-cycles discipline; backfill handled separately to stay under the Hard NEVER #2 ≤5 cap.

---

## [2.26.12] - 2026-05-24

Fixed `scripts/vidux-linear-audit.py` silent false-green when fleet repos span multiple GitHub orgs. A metadata change flipped `DEFAULT_GH_OWNER` to `firstbitelabsllc`, but three of five `DEFAULT_REPOS` still live under `leojkwan`, so their PR fetches 404'd silently and false-greened. Replaced the single default with a per-repo `REPO_OWNERS` mapping; resolution order `VIDUX_GH_OWNER` env → `REPO_OWNERS` → `DEFAULT_GH_OWNER`. Added 4 unit tests. Fourth instance of the silent-loss class.

---

## [2.26.11] - 2026-05-14

Added `apple_asc` adapter — generic read-only feedback-tracker adapter that parses ASC-style YAML and returns `ExternalItem` markers for the standard `vidux-inbox-sync.py` PULL → auto-promote pipeline. Closes T-4 of the `asc-eve-autobridge` goal.

Parses the `## Open` section of a repo-local tracker file, one `ExternalItem` per row with `external_id = "asc:<id>"`. Read-only: `pull_status`→`None`, `pull_fields`→`{}`, all push methods raise `NotImplementedError` (Apple has no feedback-handling API). Paired with the `linear` adapter's `push_only_for_plans`, every ASC feedback row flows tracker file → PLAN.md → Linear EVE with zero manual bridging.

### Added
- **`adapters/apple_asc.py`** — `AppleAscAdapter` (`name = "apple_asc"`). Config: `tracker_file` (required) + `status_filter` (optional, default `["new","triaged","claimed"]`). Terminal states (`fixed`/`verified`/`archived`) always dropped.
- **`tests/test_apple_asc.py`** — 22 unit tests.
- **`adapters/__init__.py`** side-effect import; **`adapters/README.md`** + **`SKILL.md`** adapter docs.

### Deprecated
- `scripts/vidux-asc-bridge.py` — kept during migration; removal scheduled for 2.27.0 after one cron cycle of adapter overlap.

---

## [2.26.10] - 2026-05-14

### Security
- Untracked + gitignored `vidux.config.json` (local-config-not-source); added `gitleaks` config + GitHub Actions workflow; `.gitignore` patterns for `*.token`, `*-state.json`, `.netrc`.

### Changed
- Parameterized hardcoded paths via `VIDUX_ROOT` / `VIDUX_DEV_ROOT` and GitHub owner via `VIDUX_GH_OWNER`/`--owner` (open-source readiness). README gains `## Security posture` + `## Multi-platform notes`.

### Removed
- `scripts/strip-linear-codec-markers.py` (completed one-off migration; kept locally under `/vidux-leo`).

---

## [2.26.9] - 2026-05-09

Parser fix for `vidux-asc-bridge.py`. The original `\[asc-([A-Za-z0-9]+)\]` silently rejected hyphenated IDs (`[asc-ANPm-HS30l]`) and IDs with trailing annotations (`[asc-AOgQxkJ7 Leo P0]`); both merged 2026-05-09 and fell out of the linear-health-watch sweep. Same silent-loss class as LI-12/14.

### Changed
- `ASC_ID_RE` widened to `\[asc-([A-Za-z0-9-]+)(?:\s[^\]]*)?\]` — captured ID allows hyphens; one optional whitespace-prefixed trailing segment tolerated and discarded. `parse_asc_id` still lowercases.

### Verified
- 3 new cases in `tests/test_asc_bridge.py::TestParseAscId`; 31 asc-bridge tests pass.

---

## [2.26.8] - 2026-05-09

Safety fix to `vidux-asc-bridge.py`. In dry-run, a missing `--token-file` silently fell back to `find_existing_eve → None`, making every ASC PR appear as `would_create` even though matching Linear issues existed. Same false-positive class as LI-12.

### Changed
- JSON envelope now always carries `warnings: []`. Dry-run + missing token populates `warnings` and notes `would_create` reflects no-lookup state. Live mode still exits 2 on missing token. Consumers can gate on `len(warnings) == 0`.

### Verified
- 3 new cases in `tests/test_asc_bridge.py` (28 helper tests total).

---

## [2.26.7] - 2026-05-08

Standalone bridge script lifts resplit-ios `[asc-XXX]` PR titles into Linear EVE issues. ASC fixes routinely shipped without a Linear card, so `/resplit-watch` went silent ~10 days. Section 4 of `/linear-health-watch` detects the gap; this release remediates it.

### Added
- **`scripts/vidux-asc-bridge.py`** — enumerates merged PRs (`gh pr list --state merged`), matches the ASC title regex, queries Linear `searchableContent` for an existing mention, and if none creates an issue (title=PR title, description=ASC ID + PR URL + merged-at, project=`resplit-ios`, state=Done, label=`pr-merged`). Idempotent on re-run. CLI: `--repo`, `--since-hours`, `--dry-run`, `--token-file`, `--project-name`, `--label-name`, `--no-network`. JSON envelope output. Pure stdlib.
- **`tests/test_asc_bridge.py`** — 25 unit tests; **CI** `asc-bridge-tests` job.

**Notes:** Hard NEVER #6 (no Linear MCP cold-path calls from the cron lane) preserved — this script is invoked by Leo or a separate bridge cron, never inline by `linear-health-watch`.

---

## [2.26.6] - 2026-05-07

Standalone closeout helper codifies the three gates a lane must satisfy before retirement: every PLAN.md task terminal (modulo the closeout task), `vidux-linear-audit.py` not `red`, and Linear sync dry-runs report zero drift per repo. Closes the LI-7 gap.

### Added
- **`scripts/vidux-lane-closeout.py`** — runs `tasks_terminal` / `audit_overall` / `sync_drift` gates, emits a JSON envelope (`status: CLOSED|OPEN` + per-gate detail). Pure check functions take injected fetchers (unit-testable); live runners shell out to the audit + inbox-sync scripts. CLI: `--plan` (required), `--self <task-id>`, `--repo`, `--no-network`, `--audit-script`, `--inbox-sync`. Exit 0/1/2.
- **`tests/test_lane_closeout.py`** — 32 unit tests; **CI** `lane-closeout-tests` job.

**Notes:** Read-only — never edits PLAN.md, closes Linear issues, or pauses LaunchAgents. Closeout decisions stay operational, gated on exit 0. Shells out to `vidux-linear-audit.py` rather than calling Linear GraphQL directly.

---

## [2.26.5] - 2026-05-07

Standalone audit script reports Linear coverage health across the fleet in one JSON envelope. Closes the LI-6 gap.

### Added
- **`scripts/vidux-linear-audit.py`** — 7 checks (`repo_config`, `no_project_issues`, `label_taxonomy`, `pr_linear_links`, `draft_age`, `description_format`, `sync_deltas`). Each is a pure function with injected fetchers returning a `CheckResult`. Worst-of overall (red > yellow > green; skipped neutral). Exit 0 on green/yellow, 1 on red. CLI: `--check`, `--repo`, `--no-network`. On-demand/CI use only — not invoked by `linear-health-watch` (Hard NEVER #6).
- **`tests/test_linear_audit.py`** — 37 unit tests; CI `linear-audit-tests` job.

---

## [2.26.4] - 2026-05-07

Launchd cron wrappers can guard against parallel-cycle races with a single-instance lock. Closes the LI-8 collision-guard gap (two cycles opened PRs #81 and #94 within ~5s).

### Added
- **`scripts/launchd-helpers/acquire-cycle-lock.sh`** — atomic file-claim helper (`--acquire`/`--release`). Lock format `PID|ISO|EPOCH`; fresh while PID alive AND age < `--max-age-seconds` (default 1500). Stale locks swept on next acquire. Acquire exit 0 (claimed) / 1 (held, `LOCKED` on stderr) / 2 (bad args). Release idempotent. Caller pattern: acquire-or-exit-0, release on EXIT trap.
- **`tests/test_acquire_cycle_lock.py`** — 14 integration tests; CI `cycle-lock-tests` job.

---

## [2.26.3] - 2026-05-07

Automation lanes can replace `gh pr merge --auto` with a poll-loop helper that verifies Graphite, Seer, and CI are green on the *latest* commit SHA before merging. Closes the LI-9 latest-SHA review-gate gap.

### Added
- **`scripts/vidux-gh-merge-when-ready.py`** — polls `gh pr view --json headRefOid,statusCheckRollup,reviews` until every required check on the latest commit is green and every required bot (default `graphite-app`) acked that exact SHA, then `gh pr merge --squash --delete-branch`. Caps the wait (default 15 min), exits `ACK-PENDING` for the next cycle.
- **Silent-pass CheckRun fallback** — Graphite acks via the `Graphite / AI Reviews` CheckRun (`SUCCESS`) when it has nothing to flag; treated as a stand-in for a missing review, `FAILURE` as a hard blocker. Mapping in `CHECKRUN_FALLBACK_FOR_BOT`.
- **`tests/test_gh_merge_when_ready.py`** — 16 tests (pure `assess()` parsing incl. silent-pass fallback + poll loop with injected fetch/sleep/clock).

## [2.26.2] - 2026-05-07

One canonical PR body builder so automation lanes consistently expose lane, plan task, resume point, and optional Linear issue id before opening ready-for-review PRs.

### Added
- **`scripts/vidux-pr-body.py`** — reusable PR body shape for `gh pr create --body-file`, incl. optional `Linear: EVE-N`. **`tests/test_pr_body.py`** in `npm test` + a CI job.

### Changed
- Ready-PR flow, prompt template reference, lane prompt guide, fleet ops handoff rule, scripts reference, and Linear extension docs all point at the canonical builder.

---

## [2.26.1] - 2026-05-01

Patch on the same-day 2.26.0 left-panel rework: walk the full parent chain instead of stopping one level, then bulk-connect orphan plans so the traversal has something to walk.

### Changed
- **Pane header shows the full ancestor breadcrumb** (root → … → leaf), walking `state.plans` cycle-safe, capped at 8 levels. Closes the deep-chain navigation gap.

### Added
- **Bulk parent-link pass** — one-shot audit against `/api/plans` found orphans whose structural parent was also indexed; 51 of 100 got a `> Parent: ../PLAN.md` backlink prepended after the H1. Idempotent. Landed across 6 repos.

---

## [2.26.0] - 2026-05-01

Browser left-panel rework: recently-viewed at top, recency-based ordering, persistent collapse state, parent backlinks. Plus recursive sub-plan rollup as a first-class second nesting mode.

### Added
- **Recursive sub-plan rollup.** vidux-browse parses `> Parent:` / `**Parent:**` backlinks, builds a parent→children tree, computes `aggregate_stats` recursively. Sidebar indents children; parent rows render own + rolled-up progress bars; pane gets a Sub-plans section. Cycle-safe via visited-set. (#86)
- **"← Parent" backlink** in pane header for child plans (cmd-clickable).
- **Recently-viewed section** (up to 5, localStorage, deduped, survives reloads).
- **Persisted collapse state** per group header via localStorage `vidux:ui-state`.
- **Two nesting modes documented in SKILL.md** — investigation files (1-level) and sub-plan rollup (N-level).

### Changed
- **Sidebar sort alphabetical → recency.** Repos sort by freshest plan mtime; plans within a repo by mtime desc. Active work rises, cold tail sinks.
- **Repo-root plan labels** render as `<repo>/PLAN.md`; pane header shows just `<repo>`.
- Grammar fix: "modified today ago" → "modified today".

---

## [2.25.0] - 2026-04-29

Named annotations for vidux-browse. LAN viewers can leave comments on a plan tab or artifact without turning comments into plan writes.

### Added
- **Named comments on plan tabs and artifacts** — compact comments panel with saved name field + append form.
- **Append-only comment store.** `GET`/`POST /api/comments` read/write `${VIDUX_BROWSER_COMMENTS_FILE:-~/.vidux-browser/comments.jsonl}`. Comments are app data; never mutate `PLAN.md`, `INBOX.md`, source, task claims, or artifact HTML.
- **LAN-safe annotation guard** — comment POSTs require JSON + same-origin `Origin`/`Referer`. Artifact + local plan-note writes stay loopback-only.
- Docs/skill guidance for comments vs `INBOX.md`.

---

## [2.24.1] - 2026-04-27

Auto-promoted external cards now round-trip status without reopening the duplicate-card hole `auto_promote_target` closed.

### Fixed
- **`auto_promote_target` still pushes status for linked tasks.** A completed imported task (carrying a `[Source: <adapter>:<id>]` marker) now reconciles terminal status back to the external board instead of leaving it stuck in Backlog.
- **Local-only PLAN rows stay protected** — auto-promote still refuses to create brand-new external issues from unrelated local tasks.

---

## [2.24.0] - 2026-04-27

Linear codebase-project guardrails. Repo lanes can require their Linear project binding to be named after the codebase it feeds.

### Added
- **`linear.project_name` config validation** — when set beside `project_id`, the adapter looks up the remote project and fails closed unless names match, preventing copied configs from routing a codebase plan into a product bucket.
- **Docs + example config** for codebase-owned Linear projects.
- **Local policy overlay guidance** — keep concrete board ids, repo/project maps, review-tool gates, and fleet cadence in an overlay skill/runbook loaded after `/vidux`.
- **Auto-promote batch safety** — `auto_promote_max_new: 25` default, fails closed before oversized batches, recovers missing sidecar mappings from unique title matches.

### Removed
- Dogfood fleet audit pages from public docs nav (operator-specific ledgers belong in local overlays).

---

## [2.23.0] - 2026-04-27

Canonical-plan dedupe for the local Vidux browser. Legacy copied checkouts no longer hide or mis-group the active plan when the same `PLAN.md` exists under both old and current repo names.

### Fixed
- **`mobiledevcombine-web` no longer wins over `strongyes-web`** — `discover_plans()` maps known legacy repo aliases to canonical and keeps the canonical checkout on duplicate paths.
- Regression coverage for duplicate plan discovery.

---

## [2.22.0] - 2026-04-27

Fail-closed auto-promote routing for external board/project tasks. Linear and other sources preserve lane ownership when new external cards are added.

### Fixed
- **`auto_promote_target` misconfiguration no longer falls back to INBOX.** Missing target plan path → config error `2` for that source; refuses to append to the first plan's `INBOX.md`.
- **Import-only sources stay import-only on target failure** — suppresses PLAN-to-board pushes, avoiding accidental mass issue creation on a typoed/deleted target.

### Added
- Main-path regression tests for successful auto-promotion + missing-target fail-closed.

---

## [2.21.0] - 2026-04-27

Read-only Linear/GitHub Projects port audit, saved durably.

### Added
- **`docs/fleet/linear-port-audit.md`** records the non-mutating audit across `vidux`, `strongyes-web`, `resplit-web`, `resplit-ios`: dry-run adapter health, Linear coverage, drift, stale mappings, repo-specific next actions. Docs sidebar link under Fleet.

**Findings:** StrongYes mostly wired but not fully ported (22 unmapped tasks, 44 stale-text issues); resplit-web Linear import works but local plan coverage doesn't (65 unmapped) and its `gh_projects` config is stale; resplit-ios not ported to repo-level sync (no config, non-canonical task syntax → 0 tasks parsed); no Linear HTML-comment codec leak found.

---

## [2.20.0] - 2026-04-27

Worktree lifecycle GC lands in core — a safe, read-only-by-default classifier for local automation worktrees so fleets can clean up after PR handoff.

### Added
- **`scripts/vidux-worktree-gc.py`** classifies worktrees into `primary`, `open_pr`, `merged_clean`, `dirty`, `closed_unmerged`, `unmerged_no_pr`, `unknown`.
- **Safe cleanup** via `--apply --yes` — removes only `merged_clean` (clean, non-protected, branch in base or PR merged).
- **`--json`** output; regression coverage in `tests/test_worktree_gc.py`.

### Changed
- **Worktree doctrine is now PR-first.** `guides/fleet-ops.md` no longer tells lanes to merge worktree commits directly to default; lanes push branch + PR, record the resume point there, treat the worktree as disposable after classification.
- **Plan GC and worktree GC are separate tools with separate safety rules** (`SKILL.md`).
- **Invocation checkout is protected** — both the primary Git worktree and the invocation checkout are guarded from removal.

---

## [2.19.0] - 2026-04-26

Ready-PR-first replaces draft-first as the core push policy. Operational PRs open ready-for-review by default so review bots and preview checks run immediately; draft is reserved for true WIP or a missing gate.

### Changed
- **Core push authorization: ready PRs by default.** `SKILL.md`, `docs/concepts/cycle.md`, prompt templates, recipes, and automation references all align on: push the branch, open a ready PR, use draft only when not ready for review, never push directly to `main`.
- `guides/draft-pr-flow.md` keeps its path but documents Ready-PR Flow.
- Lifecycle recipes track all automation PRs, not only drafts; drafts are the exception to flip ready once gates pass.

**Why:** Draft-first solved direct-to-main safety but fights modern review automation (Graphite, Seer, preview comments, deploy gates skip/delay drafts), made agents look idle, and hid feedback. Ready-first keeps the PRs-not-main boundary while letting the pipeline run.

---

## [2.18.0] - 2026-04-25

ETA tags go back to optional. 2.12.0's "mandatory on every pending + in_progress task" rule is reversed: completion (X/Y tasks done) is the headline metric; `[ETA: Xh]` is supplementary and only meaningful when tasks in a plan are similar-sized. Leo: *"tasks are way fucking harder than each other, ETA is fiction."*

### Changed
- **`[ETA: Xh]` is OPTIONAL** on `[pending]` + `[in_progress]` tasks. The 2.12.0 "plan defect — fill it in before checkpoint" rule is gone. Tag when tasks are similar-sized and the sum is a meaningful "AI-hours remaining" read; skip when they vary and the sum becomes fiction. `/vidux-status` still sums present ETAs, informationally.

**Why:** The 2.12.0 mandate assumed task uniformity that doesn't hold. Summing across a 15-min test fix and a 6-hour migration produces noise. Headline completion carries the signal; ETAs return to a per-task tool for when calibration is meaningful.

**Unchanged:** 2.12.0's `[FREEFORM]` + `[METER]` cycle-end format stays (the 20-cell meter doesn't sum ETAs).

---

## [2.17.0] - 2026-04-22

Core docs cleanup: dead-weight kill + personal-reference scrub, keeping the `/vidux` ↔ `/vidux-leo` boundary clean so OSS readers see discipline, not one fleet's taste.

### Changed
- **Coordinator cadence harmonized to every hour** across `references/automation.md` (rule + slot-map example now match the §11 60-min table).
- **Personal refs scrubbed from core** across 7 recipes + `references/automation.md` + `guides/automation.md`: `~/.claude-automations/` → `<lane-dir>/`, Leo lane names → generic `<project>-*`, direct attributions dropped, examples generalized.
- **Stale breadcrumbs scrubbed** — Routines mention, dated Opus-version heading, deprecated cross-tool-delegation bullet, historical `--no-verify` violations example.

### Removed
- `references/automation.md` Section 8 (Observer Pairs tombstone — deprecation already lives in Section 3; 8.5 Cross-Fleet Coordination promoted up).
- Sections 17 (Agent Config Rules) + 18 (Insights Triage) — both pointer stubs; cross-refs survive inline.

---

## [2.16.0] - 2026-04-18

Audit cleanup catching stale "Mode A / Mode B" terminology 2.15.0 missed in tier-3 docs.

### Changed
- **`Mode A / Mode B` → `research dispatch / implementation dispatch`** across 4 files (`references/automation.md`, `docs/fleet/codex-lifecycle.md`, `docs/fleet/codex-setup.md`, `commands/vidux-auto.md`) — the remainder of 2.15.0's core rename. `grep` returns 0 post-rename.
- **`commands/vidux-auto.md` breadcrumb fix** — now accurately describes the current structure (single entry `/vidux`, Part 1 in SKILL.md, Part 2 in `guides/automation.md`, deep doctrine in `references/automation.md`).

**Moved:** `PLAN-docs-simplify.md` → `projects/docs-simplify/PLAN.md` via `git mv` (all 8 tasks completed; Decision Log retained for reference value).

---

## [2.15.0] - 2026-04-18

Doctrine cleanup: plain-English rename of L1/L2 plan nesting, cross-tool delegation removed (not deprecated — removed), vidux.config.json surfaced in core, "markers" jargon dropped. Leo: *"what are markers? … let's kill delegation cross tool concept entirely, 0 deprecation warnings i am sole user."*

### Changed
- **L1/L2 nesting terminology retired** — now "parent plan + child investigation" in plain English (concept unchanged: one parent PLAN.md, one child `investigations/<slug>.md`, no deeper nesting).
- **Cross-tool delegation removed, not deprecated.** All Mode A / Mode B / cross-tool / Claude-primary-Codex-secondary refs scrubbed. Subagent-dispatch (already same-tool by 2.10.0) renamed to plain "research dispatch" + "implementation dispatch." No deprecation shims — single-user project.
- **`[FREEFORM]` / `[METER]` "markers" jargon dropped** — `commands/vidux.md` now calls them "the freeform line" and "the meter bar." Rule unchanged from 2.13.0.

### Added
- **`vidux.config.json` surfaced in core doctrine** (`SKILL.md` + README) — the three plan-store modes (`inline`/`local`/`external`). Previously only in `commands/vidux.md`.
- **README "Status & Config" section** — `scripts/vidux-status.py` usage + `vidux.config.json` minimal schema.

---

## [2.14.0] - 2026-04-18

Concrete script for `/vidux-status` — deterministic, <5s, callable from cron/bash/agents/CI.

### Added
- **`scripts/vidux-status.py`** (~230 lines, stdlib-only) — read-only scan of every `PLAN.md` under `~/Development/` (or `--root`). Renders the two-bucket board (🎯 Tied to this chat + 📋 Other tracked plans), sorts by `%` desc then mtime desc, filters empty + shipped by default (`--all`). Flags `--json`, `--focus <repo...>`. Skips `*-worktrees/`, `.claude/worktrees/`, `**/ai/skills/vidux/`.

---

## [2.13.0] - 2026-04-18

Durable question queue + tightened marker doctrine. `[DEFER]` (a passive name for an active state) replaced with `[ASK-LEO]` pointing at a new `ASK-LEO.md` queue. Also tightened 2.12.0's "every response ends with meter+freeform" — markers are for mission-status moments, not casual chat. Leo: *"why are u [METER] [FREEForm] everything?"*

### Added
- **`ASK-LEO.md`** at repo root — durable queue of open questions (title + opened-ts + status + context + inline-editable Answer). Lanes log one-line `[ASK-LEO Q<N>]` pointers in memory.md; durable state lives in `ASK-LEO.md`.
- **`[ASK-LEO]` + `[ACTED]` tags** in vidux-ship-coordinator §8 replacing `[DEFER]`. `[ASK-LEO]` = armed + ready, waits on one Leo answer (distinct from `[BLOCKED]` = hard technical blocker).

### Changed
- **Marker rule tightened** (`commands/vidux.md`) — full `[FREEFORM]` + `[METER]` pair for cycle checkpoints + mission-status replies; casual chat / naming Q&A skip both; meter-only acceptable for progress signal without prose.
- **No-noise rule** covers `[ASK-LEO]` — skip the entry if the prior was `[ASK-LEO Q<N>]` and nothing changed.

---

## [2.12.0] - 2026-04-18

ETAs go mandatory; every cycle ends with a meter. (Reversed in 2.18.0.) Leo: *"vidux plans must have an ETA when planning and every response or automation end needs to express where its at freeform and the 0-100 meter bar, idgaf."*

### Changed
- **`[ETA: Xh]` MANDATORY** on `[pending]` + `[in_progress]` tasks (new task without one = plan defect). Completed + blocked exempt. *(Superseded by 2.18.0 — now optional.)*
- **Cycle-end format is `[FREEFORM]` + `[METER]`.** FREEFORM = 1–3 plain sentences on where work sits; METER = 20-cell bar, cell = 5%, mission-wide. Coarse on purpose.

---

## [2.11.0] - 2026-04-18

Cross-repo plan visibility. New `/vidux-status` command renders a two-bucket board of every PLAN.md on the machine. PLAN.md Tasks template grows an optional `[ETA: Xh]` tag.

### Added
- **`/vidux-status` command** (`commands/vidux-status.md`) — read-only scan, classified 🎯 Tied to this chat / 📋 Other tracked plans, with progress bars + remaining AI-hours + last-Progress timestamp. Never writes.
- **`[ETA: Xh]` tag convention** on Task lines (optional). Calibration table in SKILL.md (0.25h trivial → 8h+ multi-phase). *(See 2.12.0 → 2.18.0 for the mandatory/optional history.)*

### Changed
- **SKILL.md `## Tasks` template** shows `[ETA: 0.5h]` / `[ETA: 2h]` examples + AI-hour convention paragraph.

---

## [2.10.0] - 2026-04-18

Structural refactor. Doctrine machinery shrinks; the recipes layer takes on everything tool-specific, tactical, or customizable. Cross-tool delegation (Claude ↔ Codex) deprecated — vidux runs single-tool. Core SKILL.md becomes Part 1 only.

### Added
- **`guides/automation.md`** — the 24/7 fleet operating model (session-gc, lane management, delegation, bootstrap), previously Part 2 of SKILL.md. Now opt-in.
- **`guides/recipes/` directory** with 12 recipes (CLAUDE.md rules, lane-prompt patterns, subagent-delegation, codex-runtime, + /insights-derived friction recipes) and a README index.

### Changed
- **SKILL.md shrinks to Part 1 only** (~280 lines: discipline + cycle + PLAN.md + investigations).
- **Cross-tool delegation deprecated.** Mode A/B (Claude-primary + Codex-secondary) created context-loss at the egress boundary, shim fragility, and state-sync surprises. Modern delegation = same-tool subagent dispatch via `Agent()`. The cross-tool era had measured wins (10–110× Mode A / ~5× Mode B) but reliability cost exceeded context savings at fleet scale.
- **`/vidux-codex` skill deprecated** — see `guides/recipes/codex-runtime.md`.

**Migration:**

| Old shape | New shape |
|---|---|
| `SKILL.md` Part 2 | `guides/automation.md` |
| Mode A / Mode B (Claude→Codex) | `guides/recipes/subagent-delegation.md` (same-tool via `Agent()`) |
| Codex shim registration | `guides/recipes/codex-runtime.md` |
| `/vidux-codex` skill | Deprecated — see `codex-runtime.md` recipe |

Minor bump: the five principles, the cycle, and required PLAN.md sections are unchanged; readers get redirected, not broken.

---

## [2.9.0] - 2026-04-17

Doctrine patch with two aims: (1) kill the fleet-scale failure where agents picked cheap meta-tasks over real bug fixes, and (2) shift toward **autonomous adaptive work** — fewer human-gated checkpoints, fewer required sections, fewer ceremonies. Net: substantial deletion across SKILL.md, DOCTRINE.md, LOOP.md, docs/, guides/, references/, commands/.

### Added
- **`observed` is now a first-class evidence type** — user-observed behavior is citable evidence of equal standing to codebase grep / GitHub PR / design doc. Closes the ingest path for bugs a human sees in the running app.

  ```markdown
  ## Evidence
  - [Source: observed] "flicker on first render after launch" (v2.4.1)
  - [Source: observed] "Remove button silently no-ops during active session"
  ```

### Changed

**Core Rule:**
- **Progress is code change.** A PR that only touches `PLAN.md`, `investigations/`, `evidence/`, or `INBOX.md` without a source-code change is bookkeeping, not progress. Bundle plan updates into the code PR, or keep notes local until a fix is ready. Prohibited as standalone PRs: `flip row to [completed]`, `reconcile Phase N`, `audit already-delivered`, `investigation closeout` without a code fix. **Why:** at fleet scale cheap tasks produce mergeable PRs faster than real fixes; lanes optimizing for merge count pick the cheap path. This takes it off the table.
- **Investigation-only cycles no longer commit** — if a cycle produces no code, it produces no commit and no PR. The investigation file stays on disk and ships in the same PR as the fix.
- **LOOP.md checkpoint rule inverted** — *"every cycle MUST produce a checkpoint commit"* → *"a cycle produces a commit only when code changed."*
- **24/7 lane count simplified** — 2–4 lanes per repo (coordinator + session-gc); the observer slot is gone.

**Autonomous Adaptive Doctrine** (each item deletes a rule or replaces it with a more permissive, agent-owned equivalent):
- **Queue re-sort is agent-owned** — re-sort when new `[Source: observed]` evidence, a Decision Log entry, or a failing deploy changes priority; note in next Progress, no permission required.
- **Queue selection is impact-weighted, not strict FIFO** — "pick the highest-impact unblocked task." FIFO is the default; impact-weighting kicks in when the priority signal is obvious.
- **`[P]` parallel marker removed from queue order** — parallel research fan-out still happens where it helps, just not via a static per-task marker.
- **3× stuck rule no longer requires a human** — 3× stuck → force a surface switch to the next unblocked task, mark stuck one `[blocked]` with a one-line Decision Log entry. Next cycle finds new evidence or it stays blocked. Human out of the critical path.
- **Status FSM — `blocked` is terminal** — no `blocked → pending` reverse transition; a new task replaces a blocked one.
- **L3 investigation escape hatch removed** — max two levels (L1 plan, L2 investigation) is firm; deeper decomposition splits into separate L1 plans.
- **Push authorization compressed to one rule** — *"Draft PRs are always safe. Direct-to-main or destructive operations (force push, branch delete, `git reset --hard`) require explicit authorization."*
- **Garbage-collection thresholds removed** — replaced with *"archive completed tasks when the plan feels heavy — the agent decides, no fixed threshold."*
- **"Every agent is a worker" folded into the ACT step** — *"Empty queue? Scan INBOX, owned paths, git log, blocked tasks. Anything found becomes [pending] and runs this cycle. Nothing found? Checkpoint and exit."*
- **Principle 4 addendum** — *"If evidence changes mid-cycle, the queue re-sorts… note the reorder in the next Progress entry."*

**PLAN.md Template:**
- **`## Open Questions` and `## Surprises` are now optional** — dropped from the required template; contract test loosened. Promote a question to a `[pending]` task or a `[Blocker: ...]` annotation; put surprises in the Progress entry. Existing plans with these sections still work.
- **Status FSM in the template** updated — `blocked` is terminal.
- Contract `test_plan_has_required_sections` now requires 6 sections: `Purpose`, `Evidence`, `Constraints`, `Decisions`, `Tasks`, `Progress` (down from 8).

### Deprecated
**Observer Lane Pattern** — read-only audit lanes that watch a writer each cycle are an orchestration smell. They add memory.md files, cross-lane reads, and cycle offsets without catching bugs the writer couldn't already see in its own logs. Drift belongs upstream — fix the writer's prompt or the doctrine. Targets: `references/automation.md` §8 (collapsed to a notice), §3 observer subsection (rewritten), §8.5 step 4 (removed); `guides/recipes.md` Recipes 1 + 4 (marked DEPRECATED); `docs/index.md` feature card. Existing observer lanes are not auto-migrated; wind them down at the next maintenance window. **Alternatives:** one-shot manual audits for independent eyes; health checks in the writer's own cycle / `session-gc` for fleet health; fix the writer's prompt for drift.

**Migration Guide** (replace old phrasings):

| Old phrasing | New phrasing |
|---|---|
| `investigation only — no code` | `no PR until the fix ships` |
| `no code this cycle` | `no commit until the fix ships` |
| `Every cycle MUST produce a checkpoint commit` | `A cycle produces a commit only when code changed` |
| `observer pair`, `fleet watcher`, `preemptive observer` | (deprecated — see alternatives) |
| `No reordering mid-cycle` | `Re-sort when observed evidence changes priority; note in Progress` |
| `first eligible [pending] wins` | `Pick the highest-impact unblocked task` |
| `[P] tasks may run in parallel` | (removed from queue order; research fan-out still valid) |
| `L3 is allowed only when...` | (removed — max two levels) |
| `Only a human can unblock it` (3× stuck) | `Force a surface switch; next cycle finds evidence or stays blocked` |
| `blocked → pending` FSM transition | (removed — blocked is terminal) |
| `Archive when PLAN.md exceeds 200 lines` | `Archive when the plan feels heavy — agent decides` |
| `## Open Questions` / `## Surprises` required | Optional — promote to task / `[Blocker:]` / Progress |

No change to: the five principles (Principle 4 gained the re-sort addendum); the cycle (READ → ASSESS → ACT → VERIFY → CHECKPOINT); the 6 required PLAN.md sections; `INBOX.md` ingest; the agent ledger; nested planning; the automation harness; draft-PR flow; the 3× stuck threshold itself (only the response changed).

### Verified
- `tests/test_vidux_contracts.py`: 133 pass / 3 pre-existing failures, none introduced. `REQUIRED_PLAN_SECTIONS` loosened to 6 (a weakening, not a break) — all plans that passed the old contract still pass.

---

## [Pre-2.9.0]

Earlier history (2.0.0–2.8.0) lives in git. Notable version-marker commits:

- **2.8.0** (`d7acca3`) — 5-agent peer review; Phase 22 mega task list; trunk health doctrine; Bug #22 prevention.
- **2.7.0** (`4ddac12`) — Codex skill independence; REDUCE purge; config-authoritative plans; tagged `v2.7.0`.
- **2.6.0** (`b1c5e96`) — initial public "plan-first expedition orchestration for AI agents" framing; tagged `v2.6.0`.
- **2.5.x / 2.4.0** — early plan-store + worktree-GC iterations (tagged `v2.5.1`, `v2.5.0`, `v2.4.0`; no detailed entries).

For detail before 2.9.0, run `git log --grep "^vidux v[0-9]"` or browse the `v2.4.0`..`v2.7.0` tags.

### Versioning Policy

- **Patch (2.X.0 → 2.X.1):** typo fixes, doc clarifications, additional examples.
- **Minor (2.X.0 → 2.Y.0):** tightening rules, adding evidence types, deprecating patterns. No breaking changes to the cycle or `PLAN.md` template.
- **Major (2.X.0 → 3.0.0):** changes to the cycle shape, the five principles, or the required `PLAN.md` sections. Contract tests would change.

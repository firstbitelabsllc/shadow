# T2k Cross-Plan Dashboard Preflight

Date: 2026-06-03
Plan: `projects/vidux-browser/PLAN.md`
Task: `T2k Cross-plan dashboard - all in_progress, blocked, open ASK-LEO, INBOX entries`

## Inventory

Live source: `http://127.0.0.1:7191/api/plans`

- Plans indexed: 1101.
- Repos indexed: 35.
- Plans with one or more `in_progress` tasks: 284.
- Plans with one or more `blocked` tasks: 156.
- Plans with `ASK-LEO.md` sibling: 1.
- Plans with `INBOX.md` sibling: 106.
- Task status totals from existing `task_stats`: 658 `in_progress`, 465 `blocked`.

Sample rel paths, not task text:

- `in_progress`: `strongyes-web/vidux/blog-depth-overhaul/PLAN.md`, `vidux/projects/connect-the-fleet/PLAN.md`, `vidux/projects/litty/PLAN.md`, `vidux/projects/team-agent-coordination/PLAN.md`.
- `blocked`: `strongyes-web/vidux/launch-validation/PLAN.md`, `vidux/projects/connect-the-fleet/PLAN.md`, `vidux/projects/litty/PLAN.md`, `resplit-web/vidux/resplit-2.0-launch/PLAN.md`.
- `ASK-LEO.md`: `vidux/PLAN.md`.
- `INBOX.md`: `moussey/PLAN.md`, `vidux/projects/moussey-voice-agent/PLAN.md`, `resplit-web/vidux/resplit-2.0-launch/PLAN.md`, `strongyes-web/vidux/game-plan/PLAN.md`.

## Current Gap

- `/api/plans` already provides a flat plan index, task status counts, sibling file names, plan paths, and rel paths.
- It does not expose individual `in_progress` or `blocked` task lines, so a dashboard cannot list "all in progress" or "all blocked" without fetching every `PLAN.md` client-side.
- It exposes `INBOX.md` and `ASK-LEO.md` presence through `siblings`, but not bounded entries, so a dashboard cannot list open items without many client fetches.
- `safe_resolve` already allows canonical sibling files, so the security boundary is compatible with a server-side bounded extraction.

## Implementation Shape

- Prefer a server-side `/api/dashboard` or `dashboard` field in `/api/plans` that derives from the same discovery pass, not a client-side fan-out over 1101 plan files.
- Add bounded extractors for:
  - task lines in `## Tasks` with statuses `in_progress` and `blocked`;
  - top open entries from `INBOX.md`;
  - top open entries from `ASK-LEO.md`.
- Each item should carry `repo`, `rel`, `path`, `line` when known, `status`, and a compact escaped label.
- Bound every list, for example 200 items per category, and include `truncated=true` plus source totals.
- UI should be a dashboard surface in the main pane/default view, not another topbar feature. It should let a click navigate to the owning plan.

## Proof

- Live inventory command against `/api/plans` completed on fresh server PID `99433`.
- Scoped `git diff --check` for this evidence file and `projects/vidux-browser/PLAN.md` passed.
- Publish scrutiny for T2k preflight returned `ready=true` with handoff status `in_progress`.
- Publish ledger: `evt_codex_20260603_vb_t2k_dashboard_preflight` at `/Users/leokwan/.agent-ledger/activity.jsonl:6107`.
- This is evidence gathering only for reducer action `gather_evidence`.

## Non-Claims

- No T2k dashboard endpoint or UI was implemented in this preflight.
- No raw task text, INBOX text, or ASK-LEO text is copied into this evidence file.
- No stage, commit, push, PR, release, external message, source mutation beyond this evidence/plan tag, or browser dashboard implementation.

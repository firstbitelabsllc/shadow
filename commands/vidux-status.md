---
name: vidux-status
description: Scan PLAN.md files across the machine and render a two-category status board — projects tied to this chat and other tracked plans — with progress bars and AI-hour ETAs.
---

# /vidux-status

Read-only scan. Never writes. Never commits. Never opens PRs. Finds every PLAN.md on the machine, classifies by relevance to the current chat, and renders a status board in <5 seconds.

## What It Does

### 1. Discover

Find every `PLAN.md` under the usual roots. Good defaults for Leo's machine:

```
~/Development/*/PLAN.md
~/Development/*/vidux/PLAN.md
~/Development/*/vidux/*/PLAN.md
~/Development/vidux/projects/*/PLAN.md
```

Use a single `find -maxdepth 4` and filter out `node_modules/`, `.git/`, `dist/`, `.next/`.

### 2. Classify — two buckets

**🎯 Tied to this chat** — any plan that matches ANY of:
- lives under the current cwd
- lives under a repo whose name appears in the current session's recent git activity
- lives under a repo whose name appears in a recent ledger entry (`~/.agent-ledger/activity.jsonl`)
- lives under a repo whose name appears in the last N chat messages

**📋 Other tracked plans** — everything else.

Classification is intentionally fuzzy. When a plan could reasonably belong in either bucket, put it in `🎯 Tied to this chat`. False positives are cheaper than false negatives — the point is to surface what's likely live, not perfect precision.

### 3. Parse each plan for

- **Task counts** by status: `[pending]`, `[in_progress]`, `[completed]`, `[blocked]`
- **Progress %** = `completed / (pending + in_progress + completed)` — blocked is excluded from the denominator (blocked is terminal, not pending work)
- **Remaining AI-hours** = sum of `[ETA: Xh]` tags on `[pending]` + `[in_progress]` tasks
- **Last Progress timestamp** — most recent `## Progress` entry, or file mtime if no dated entries

### 4. Render

Two sections, sharp visual separation. 10-cell progress bar per row. Fixed columns.

```
🎯 Tied to this chat
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  resplit-ios         ▓▓▓▓▓▓▓▓░░  78%  ·  2.5 AI-hrs left  ·  08:22Z
  leojkwan            ▓▓▓▓▓░░░░░  53%  ·  4.0 AI-hrs left  ·  07:18Z
  strongyes-web       ▓▓▓▓▓▓▓▓▓░  89%  ·  1.0 AI-hrs left  ·  06:47Z

📋 Other tracked plans
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  vidux (self)        ▓▓▓▓▓▓▓░░░  71%  ·  ∅ AI-hrs         ·  2d stale
  resplit-web         ▓▓░░░░░░░░  20%  ·  6.5 AI-hrs left  ·  4h ago
  fcp-workflow        ▓▓▓▓▓▓▓▓▓▓ 100%  ·  shipped           ·  2d ago
```

Rules for the bar:
- 10 cells. `▓` filled, `░` empty. Round to nearest 10%.
- 100% with zero pending shows `shipped` in the ETA column.
- 0% shows `░░░░░░░░░░`.

Rules for the ETA column:
- No `[ETA: Xh]` tags present on active tasks → `∅ AI-hrs`. Not a failure; plans back-fill ETAs over time.
- Sum → single decimal, e.g. `2.5 AI-hrs left`.
- When plan is 100% complete → `shipped`.

Rules for the Last column:
- <24h old → `HH:MMZ` (UTC time)
- 1–7d old → `Nd stale`
- \>7d → `Nd stale` and sort lower within its bucket

### 5. Optional footer

If any plan has `[in_progress]` tasks summing to >8 AI-hours across all buckets, print a single-line warning:

```
⚠ heavy queue: 14.5 AI-hrs in flight across 4 plans — consider deferring
```

## Rules

- **Read-only.** Never edits PLAN.md, never commits, never opens PRs. Reads filesystem + git metadata only.
- **Fast.** Target <5s end-to-end. If a plan is huge (>1MB), count tasks only — skip Decision Log + Progress parsing.
- **No noise.** If a plan has zero `[pending]` and zero `[in_progress]` tasks AND is >30 days stale, drop it from the output unless the user passes `--all`.
- **One screen.** If the output would be >40 rows, show the top 20 by remaining AI-hours and add a `… N more (use --all to see)` footer.

## AI-Hours Convention

An "AI hour" = how much focused AI-agent work one task takes end-to-end, not wall-clock time. It scales with file count, CI round-trips, investigation depth, and taste iteration — not calendar days and not engineering weeks.

Rough calibration:

| Tag | Scope |
|-----|-------|
| `[ETA: 0.25h]` | Trivial typo or one-line tweak, 1 file, no test change |
| `[ETA: 0.5h]` | Simple fix, 1–3 files, one assertion added |
| `[ETA: 1h]` | Small feature or refactor, 3–5 files, a couple tests |
| `[ETA: 2h]` | Moderate feature, 5–10 files, dedicated test suite |
| `[ETA: 4h]` | End-to-end feature or investigated bug with impact map |
| `[ETA: 8h+]` | Multi-phase work — promote to compound task + sub-plan |

**ETAs are elastic.** When scope moves, log the revision in `## Decision Log` and update the tag:

```
- [DIRECTION] 2026-04-18 Task 7 ETA revised 2h → 4h. Reason: Greptile surfaced 3 additional files to touch.
```

Estimates settle toward truth as evidence accumulates. A first-cycle `[ETA: 1h]` guess becoming `[ETA: 3h]` by cycle three is normal — that IS the plan being honest with itself, not a failure.

**Missing ETAs are not a failure.** A plan without any `[ETA: Xh]` tags still ships. Leo back-fills when he cares. The convention exists so that when it's present, it's machine-readable and visible in `/vidux-status`.

## Usage

```
/vidux-status
/vidux-status --all     # include stale/empty plans
```

No other arguments. Reads the filesystem, classifies, renders. Done.

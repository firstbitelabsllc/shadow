# Plan-Bank Audit Long-Smoke Summary

## Purpose

Validate the plan-bank audit as an observe-only cross-repo triage tool on real Vidux, StrongYes, Resplit web, and Resplit iOS plan banks without touching product worktrees or hot launch paths.

## Commands

Initial overcount smoke, stopped after two rows once agent-mirror noise was identified:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  /Users/leokwan/Development/vidux \
  /Users/leokwan/Development/strongyes-web \
  /Users/leokwan/Development/resplit-web \
  /Users/leokwan/Development/resplit-ios \
  --watch-iterations 9 \
  --watch-interval-seconds 900 \
  --issue-limit 0 \
  --output-jsonl evidence/2026-06-02-plan-bank-audit-smoke.jsonl
```

Corrected observe-only long smoke:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  /Users/leokwan/Development/vidux \
  /Users/leokwan/Development/strongyes-web \
  /Users/leokwan/Development/resplit-web \
  /Users/leokwan/Development/resplit-ios \
  --watch-iterations 9 \
  --watch-interval-seconds 900 \
  --issue-limit 0 \
  --output-jsonl evidence/2026-06-02-plan-bank-audit-smoke-corrected.jsonl
```

Summary command:

```bash
python3 scripts/vidux-plan-bank-audit.py \
  --summarize-jsonl evidence/2026-06-02-plan-bank-audit-smoke-corrected.jsonl
```

## Artifacts

- `evidence/2026-06-02-plan-bank-audit-smoke.jsonl`: 2 rows from the old default that included agent mirrors. Kept as overcount evidence.
- `evidence/2026-06-02-plan-bank-audit-smoke-corrected.jsonl`: 9 rows from the corrected default that excludes `.claude`, `.agents`, and `.codex` unless `--include-agent-mirrors` is set.

## Overcount Finding

The first run reported 664 plans because the default scanner counted agent mirror plans. A side inventory across the StrongYes and Resplit roots found 574 `PLAN.md` files, including 460 under `.claude/`, 2 under `.agents/`, and 27 under archive paths.

After the default exclusion was added, the corrected cross-repo scan reported 202 repo-owned plans. The critical count stayed at 141, while high and medium noise dropped substantially. This is the right default for Leo-facing plan-bank triage; mirror-plan inclusion remains available with `--include-agent-mirrors`.

## Corrected Smoke Result

- Rows: 9/9 completed.
- Window: `2026-06-02T22:42:15Z` to `2026-06-03T00:42:39Z`.
- Runtime per iteration: min `2.838s`, max `3.491s`.
- Plan count: first `202`, last `202`, delta `0`.
- Severity deltas: critical `141 -> 141`, high `333 -> 333`, medium `874 -> 874`, low `0 -> 0`.

Root breakdown on the final row:

| Root | Plans | Archived | Critical | High | Medium |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/Users/leokwan/Development/vidux` | 90 | 22 | 87 | 179 | 465 |
| `/Users/leokwan/Development/strongyes-web` | 77 | 0 | 0 | 122 | 315 |
| `/Users/leokwan/Development/resplit-web` | 31 | 27 | 54 | 26 | 82 |
| `/Users/leokwan/Development/resplit-ios` | 4 | 0 | 0 | 6 | 12 |

Stable counts across all nine rows mean the audit is useful for observe-only drift and backlog triage. The issue counts are still too broad for fail-on enforcement.

## Representative Issues

- `temporary_proof_path`: `/Users/leokwan/Development/resplit-ios/PLAN.md:131` references `/tmp/resplit-session-screens/current-100225.png`.
- `missing_terminal_closeout_section`: `/Users/leokwan/Development/resplit-ios/PLAN.md`.
- `missing_drift_log_section`: `/Users/leokwan/Development/resplit-ios/PLAN.md`.
- `archived_non_terminal_row`: `/Users/leokwan/Development/resplit-web/_archive/vidux/mega-plan/PLAN.md:103`.
- `blocked_without_since`: `/Users/leokwan/Development/resplit-ios/ai/skills/vidux/PLAN.md:116`.
- `missing_evidence_section` and `missing_constraints_section`: `/Users/leokwan/Development/resplit-ios/ai/skills/vidux/projects/scan-index/PLAN.md`.
- `unchecked_gate_checkbox`: `/Users/leokwan/Development/strongyes-web/vidux/content-lane/blog-mobile-aiml/PLAN.md:88`.
- `missing_tasks_section`: `/Users/leokwan/Development/strongyes-web/PLAN.md`.

## Product Repo Mutation Check

The smoke was observe-only. Post-run `git status --short --branch | shasum -a 256` fingerprints matched the pre-run fingerprints for all product repos:

- StrongYes web: `37b267e1f375a92630220389fa36f2e9f154cccc360b3a8c39e01c3c05add2d0`.
- Resplit web: `d6cbcc5ea764203f621cc9c445dc5f8d255c71e9643c73e833f9f86ead1fea88`.
- Resplit iOS: `da1a3bb4e577dfad3c7eaa0c7cd1c8c4604f9953fc4152e839579c073296a88d`.

## Non-Hot Follow-Up Candidates

1. Clean terminal-state metadata in archived Vidux and Resplit web plans, starting with archived non-terminal rows. This stays outside active release code.
2. Convert durable proof references away from `/tmp` paths, beginning with read-only inventory and then narrow plan-only edits.
3. Normalize StrongYes content-lane plan sections and unchecked gate rows where they do not affect production code, deployment, or launch gates.
4. Add `blocked_since` metadata to old blocked rows in Vidux-adjacent plan banks, avoiding App Store, TestFlight, local-CI execute, and external board work.

## Avoided Hot Paths

- No app runtime code changed.
- No StrongYes or Resplit product plan files changed.
- No local-CI execute run.
- No TestFlight, App Attest, AASA, or App Store work attempted.
- No external board, GitHub PR, Slack, email, or human-facing message mutated.
- No fail-on policy enabled for CI.

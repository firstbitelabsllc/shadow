# Linear Port Audit

Last audited: 2026-04-27.

This page records the read-only E2E check for whether Vidux-backed work in the main Leo repos is actually wired to Linear and GitHub Projects. It is a point-in-time audit, not a sync run. Do not use these findings as permission to bulk-create or delete board issues.

## Commands

Adapter health was checked with dry-runs only:

```bash
python3 scripts/vidux-inbox-sync.py --config <repo>/vidux.config.json --only-adapter linear --direction=both --dry-run --json
python3 scripts/vidux-inbox-sync.py --config <repo>/vidux.config.json --only-adapter gh_projects --direction=both --dry-run --json
```

Local worktree cleanup safety was checked with:

```bash
python3 scripts/vidux-worktree-gc.py --base origin/main /Users/leokwan/Development/vidux
```

The deeper Linear check compared parsed PLAN tasks, per-plan `.external-state.json` mappings, and the currently fetched Linear issues for the configured team or project. The audit was read-only.

## Connector Health

| Repo | Linear dry-run | GitHub Projects dry-run | Notes |
| --- | --- | --- | --- |
| `vidux` | Pass | Pass | Linear scoped to Automation Ops project. |
| `strongyes-web` | Pass | Pass | Linear is team-wide, not project-scoped. |
| `resplit-web` | Pass | Fail | GitHub ProjectV2 `leojkwan` number 4 no longer resolves. |
| `resplit-ios` | Not configured | Not configured | No primary `vidux.config.json`. |

## Coverage Summary

| Repo | Parsed plan dirs | Parsed tasks | Active tasks | Linear external items | Active mapped | Active unmapped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `vidux` | 11 | 66 | 26 | 4 | 24 | 2 |
| `strongyes-web` | 48 | 781 | 215 | 205 | 189 | 22 |
| `resplit-web` | 23 | 222 | 65 | 7 | 0 | 65 |
| `resplit-ios` | 1 | 0 | 0 | n/a | n/a | n/a |

## Findings

### Vidux

Core Vidux sync is functional but has historical sidecar drift.

- Linear fetch returns 4 issues from the Automation Ops project.
- 24 active tasks are mapped; 2 active tasks are unmapped.
- 23 sidecar mappings point at external ids not present in the scoped Automation Ops fetch. Treat these as historical or cross-project mappings until individually checked.
- Description formatting is clean of the old HTML-comment codec. One mapped issue has stale Purpose/title text.

### StrongYes

StrongYes is mostly wired to Linear, but not fully ported.

- Linear fetch returns 205 FirstBite team issues.
- 189 active tasks are mapped; 22 active tasks are not mapped to Linear.
- No mapped issue is missing from the team-wide fetch.
- 44 mapped descriptions have stale Purpose/title text. The failure class is title drift, not HTML-comment codec leakage.
- 7 mapped titles differ exactly between PLAN and Linear.
- 16 mapped statuses differ, mostly local `[completed]` tasks that remain pending or in review in Linear.

Action: reconcile title/status drift before claiming StrongYes is fully ported. Keep the current team-wide scope unless a dedicated StrongYes Linear project is intentionally introduced.

### resplit-web

resplit-web is not fully ported. It is currently configured as a Linear import lane, not a PLAN-to-Linear mirror.

- Linear fetch returns 7 issues from project `8b2c4c18-6036-4562-9e30-865a1cd5eaf2` (`UX Overhaul launch queue`).
- `auto_promote_target` is `vidux/mega-plan`, so PLAN-to-Linear creation is suppressed by design.
- 65 active PLAN tasks are unmapped.
- The `vidux/mega-plan` sidecar has 7 Linear mappings whose task ids are no longer parseable from that PLAN.
- GitHub Projects dry-run fails because `leojkwan` ProjectV2 number 4 does not resolve.

Action: decide whether resplit-web should stay Linear-import-only or become bidirectional. If it stays import-only, repair or delete stale `mega-plan` sidecar mappings. If it becomes bidirectional, remove `auto_promote_target` only after confirming the target Linear project and expected issue volume.

### resplit-ios

resplit-ios is not ported to current repo-level Vidux sync.

- The primary checkout has no `vidux.config.json`.
- The top-level `PLAN.md` is not canonical parser input: task rows use backticked status markers such as `- \`[pending]\`` and bold titles rather than the required `- [pending] ID: title` shape.
- The parser therefore sees 0 tasks in `/Users/leokwan/Development/resplit-ios/PLAN.md`.
- Historical embedded Vidux copies remain under `ai/skills/vidux/` and `.agents/skills/vidux/`; each still has a `projects/scan-index/PLAN.md` with 19 parsed tasks.
- No `.external-state.json` or primary adapter config was found in the checkout.

Action: port resplit-ios deliberately: add one primary `vidux.config.json`, normalize the top-level task syntax if it should be machine-synced, and remove or quarantine embedded skill-copy plan stores after confirming they are historical.

## Guardrails

- Do not bulk-create Linear issues from these repos without explicit confirmation. StrongYes alone has 22 active unmapped tasks; resplit-web has 65.
- Do not delete sidecars just because an audit calls them stale. First inspect whether the issue moved projects, the task id changed, or the PLAN stopped parsing.
- Do not treat dry-run success as complete porting. Dry-run success only proves the adapter can fetch and reconcile without mutating.

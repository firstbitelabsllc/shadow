# Resplit Web Autobot / Local-CI Workflow MVP

Date: 2026-05-25
Scope: Resplit Web as the first real `/coding` lane for Claude Code / Codex-like agent work.
Inputs inspected:
- `/Users/leokwan/Development/ai-leo/skills/autobot-resplit-web/SKILL.md`
- `/Users/leokwan/Development/resplit-web/.firstbite/local-ci.json`
- Moussey `/coding` APIs, UI code, and local run history
- FirstBite local-CI MCP lane catalog and latest proof surface

## Actual MVP Workflow

1. Leo asks for coding work in chat, Vidux, or `/coding`.
   - The request is turned into a bounded job, not arbitrary shell access.
   - Current first job is `resplit-web-autobot`.
   - If the request starts in Vidux or a failed run, it becomes a `/coding?handoff=<id>` packet with source metadata and a proposed action.

2. `/coding` reads the room before execution.
   - Show active Resplit Web local-CI proof from FirstBite MCP.
   - Show source state: repo path, branch/head, dirty/sync status, and latest report/log paths.
   - Show agent capability state: relevant skills, MCP names, model/provider config names, local worker queue, recent runs, and neighboring dirty work.

3. `/coding` chooses the smallest safe lane.
   - `Status`: read `/autobot-resplit-web --status`.
   - `Public Matrix`: run `/Users/leokwan/bin/autobot-resplit-web --public-only` for auth-free public coverage.
   - `FirstBite local CI`: dry-run or execute repo-declared lanes from `.firstbite/local-ci.json`.
   - `Lane Preflight`: plan an isolated Resplit Web worktree and Playwright port.
   - `Local Smoke`: build/start/test Resplit Web in the isolated lane.
   - `Codex Verifier`: spawn Codex to verify and diagnose inside the disposable lane.
   - `Codex Editor`: spawn Codex with edit authority only inside the disposable lane, then save a patch artifact.

4. Execution always isolates the repo.
   - Fetch `origin`.
   - Create a disposable worktree under `/Users/leokwan/Development/resplit-web-worktrees`.
   - Create a lane branch such as `codex/web-<lane>`.
   - Claim one `PW_PORT` from `3110..3119` using a lock file.
   - Build and run the app inside that worktree only.
   - Use `PW_BASE_URL=http://127.0.0.1:<port>`.
   - Do not touch the primary Resplit Web checkout.

5. Local proof is produced before any claim of done.
   - For local smoke/verifier/editor: dependency prep, build, `next start`, targeted Playwright, stdout/stderr tails, run JSONL event, teardown result.
   - For local CI: FirstBite `report.json`, lane `run.log`, lane status, rc, source head, worktree flag, and optional xcode result for iOS lanes.
   - For UI/autobot: public matrix run JSON or durable screenshot evidence when the user-visible surface is part of the task.

6. Cleanup is part of the proof.
   - Stop the local server.
   - Remove the disposable worktree.
   - Delete the scratch branch.
   - Release the port lock.
   - Record `teardownOk`.

7. Promotion is a separate human-visible step.
   - Editor lanes save `~/.moussey/coding-patches/<run>.patch`.
   - `/coding` previews patches read-only.
   - Applying to the primary checkout, opening PRs, deploys, and production actions remain outside this MVP unless explicitly requested.

## Resplit Web Local-CI Contract

`/Users/leokwan/Development/resplit-web/.firstbite/local-ci.json` declares three lanes:

| Lane | Kind | Command |
| --- | --- | --- |
| `resplit_web_unit` | unit | `npm ci && npm run test:run` |
| `resplit_web_integration` | integration | `npm ci && npm run lint && npm run test:e2e:live-local` |
| `resplit_web_ui` | ui | `npm ci && npm run autobot:web` |

FirstBite MCP exposes these in group `resplit_web_all`, plus repo/kind selectors and broader groups such as `critical_fast`, `all_unit`, `all_integration`, `all_ui`, and `all_critical`.

Latest observed FirstBite status on this Mac:
- `resplit_web_unit`: pass, run `verify-dev-env-execute-resplit-web-20260525`, source head `daeb075bfa99`, worktree true.
- `resplit_web_integration`: pass, run `mcp-20260524T1055-all-integration-fixed`, source head `daeb075bfa99`, worktree true.
- `resplit_web_ui`: pass, run `mcp-20260524T1120-all-ui-fresh`, source head `daeb075bfa99`, worktree true.

Caveat: lane green means the recorded source state passed. The UI should show source head/sync status because fresh-main proof and dirty-local-branch proof can diverge.

## What Currently Works In `/coding`

- Job catalog and readiness for `resplit-web-autobot`.
- Allowlisted modes for status, dry-run, public matrix, local smoke, Codex skill probe, Codex capability probe, Codex verifier, and Codex editor.
- Worktree/port preflight with `PW_PORT` range `3110..3119`.
- SSE lane runner that streams phases and records events to `~/.moussey/coding-runs.jsonl`.
- Clean child environment that avoids inheriting the parent Next server env.
- Local server lane that runs dependency prep, build, `next start`, waits for readiness, then runs targeted Playwright.
- Background Codex verifier lane with browser-capable sandbox inside the disposable worktree.
- Codex editor lane that can patch only the disposable worktree, runs `git diff --check`, captures `git diff --stat`, saves a binary patch, and tears down.
- Public Resplit Web autobot action that has live proof of `26/26` auth-free public-surface cells on `https://resplit.app`.
- Read-only capability catalog covering skills, MCP server names, model/provider names, tool actions, active work, and coordination surfaces without secret values.
- Local-CI dashboard backed by FirstBite MCP `latest_lane_proof`.
- Local-CI runner API with `dry_run` and `execute`, using exactly one selector: group, lanes, or repo+kind.
- FirstBite artifact reader for reports/logs under the local ledger root.
- Failed coding-run handoff route and failed local-CI lane handoff route.
- Recent-run dashboard that can inspect command, cwd, status, exit, tails, patch paths, and patch preview.
- Detached worker support for longer allowlisted tool actions, with worker logs and status URLs.

## Missing For A Claude Code / Codex-Like Loop

- Source-state clarity in the main debugger view must be unavoidable: branch, head, upstream, dirty count, behind/ahead, and whether proof came from fresh main or local dirty state.
- A first-class task object is still missing. A real loop needs "intent -> plan -> verifier/editor run -> patch -> review -> apply/promote" as one durable thread, not just separate buttons and JSONL rows.
- Patch application/promotion is intentionally absent. Today `/coding` can save and preview disposable-worktree patches; it does not yet safely apply them to the primary checkout with conflict handling.
- Verifier/editor handoff selection is too coarse. The system should suggest the next lane automatically from failure type: unit, integration, UI/autobot, local-smoke, verifier, or editor.
- Failure triage needs structured classification: app regression, stale test, environment/runner failure, auth/token missing, port/worktree contention, production-read-only boundary, or source-state mismatch.
- Local-CI logs should be summarized into actionable file/test pointers. Current artifacts are inspectable, but the editor/verifier prompt still needs curated failure context.
- Long-running agents need stronger lifecycle controls: cancel, retry, rerun with same inputs, preserve worktree for debug, and explicit "do not cleanup" only when safe.
- Multi-agent routing needs queue/concurrency policy. The Resplit Web skill caps parallel web agents at 4 and ports at 3110..3119; `/coding` should enforce that visibly.
- Cross-host proof is not yet a worker contract. M4 support packets and peer proof are visible, but execution must still be distinguished from Studio-local proof.
- Authenticated/seeded Resplit flows remain separate from public matrix green. `/coding` should keep public liveness, local mock, seeded session, authenticated, staging, Sentry, and CI gates split.
- Nia child-agent MCP approval remains flaky in spawned sessions (`user cancelled MCP tool call` was observed), so source-backed research is available in foreground but not fully reliable in child Codex loops.
- Codex account routing via `codex-lb` is visible as a hint, but hard pinning a detached worker to a specific account is not proven.

## Failed Results As Handoffs

Failed local-CI/autobot results should not immediately grant edit power. The workflow should be:

1. Failure lands in run history or FirstBite latest proof.
2. `/coding` stores the immutable failure facts:
   - run id
   - lane/action id
   - repo/kind/mode
   - source head and sync status
   - command
   - cwd/worktree
   - report/log/artifact paths
   - exit code, timeout/no-output timeout flags
   - stdout/stderr tails
   - teardown result
3. User or system clicks `Stage Follow-Up`.
4. `/coding` creates a run-sourced handoff with a bounded prompt.
5. The first recommended action is usually `codex-verifier`, not `codex-editor`.
6. Verifier decides whether the failure is app code, test rot, environment, stale proof, missing auth, or not enough evidence.
7. Only clear, local, source-contained failures graduate to `codex-editor`.
8. Editor may patch only the disposable worktree and must rerun the same targeted proof.
9. Editor output is saved as a patch artifact and displayed for review.
10. Human or a later explicit apply lane promotes the patch to the primary checkout.

For FirstBite failures, the handoff prompt should quote the repo `.firstbite/local-ci.json` lane and the MCP report/log paths as source of truth. For Resplit Web UI/autobot failures, it should also point to `/autobot-resplit-web` mode guidance and whether the failure came from public matrix, local mock, seeded flow, or browser telemetry.

## UI Proof Artifacts To Show

The `/coding` UI should make these proof artifacts visible without forcing Leo into raw terminal spelunking:

- Current lane status: pass/fail/running/planned, started/finished time, duration, host.
- Source state: repo path, branch, head, upstream head, dirty count, ahead/behind, sync label.
- Lane manifest: `.firstbite/local-ci.json` path, command, timeout, lane kind.
- Command transcript summary: command, cwd, env key names only, stdout/stderr tails with truncation notice.
- Local-CI artifacts: `report.json`, lane `run.log`, local proof markdown if present.
- Autobot artifacts: public matrix `run.json`, screenshot/evidence path, URL/viewport/mode, public-vs-seeded/auth caveat.
- Playwright artifacts: spec name, project, pass/fail counts, failed test title, trace/screenshot/video paths if produced.
- Server proof: port, `PW_BASE_URL`, server-ready event, server-stopped event.
- Isolation proof: worktree path, branch name, port lock path, cleanup status, no leftover listener/worktree/lock.
- Handoff proof: source run id, source lane, proposed action, handoff URL, prompt preview.
- Patch proof: patch path, bytes, `git diff --stat`, diff preview, whether primary checkout was untouched.
- Worker proof: worker id, status URL, log path, final message, Codex provider/account routing hint when known.
- Safety proof: no production mutation, no deploy, no PR, no human message, no secret values printed.

## MVP Product Shape

The minimum real coding-agent loop is:

`Ask -> handoff/task -> source-state check -> lane preflight -> run proof -> classify failure -> verifier handoff -> editor handoff when justified -> saved patch -> human-visible promotion`.

The MVP should stay narrow and excellent before expanding:
- First repo: Resplit Web.
- First proof stack: `/autobot-resplit-web` + FirstBite local CI.
- First edit authority: disposable-worktree patch only.
- First UI promise: make the proof legible enough that Leo can tell what is green, what is red, what is stale, and what the next safe button does.

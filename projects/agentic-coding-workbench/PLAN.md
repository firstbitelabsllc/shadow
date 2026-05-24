# Agentic Coding Workbench

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md`.
> This is the coding/test-harness execution surface for the command center. It starts with `/autobot-resplit-web`, then grows into worktree-isolated Claude/Codex/local-agent lanes.

## Purpose

Give Leo a local LAN workbench where he can run real coding harnesses, see the terminal output, capture evidence, and then delegate the next action to Claude, Codex, or a local model. The first MVP is deliberately narrow: prove Moussey can safely run the existing Resplit Web Autobot harness from the dashboard before it becomes a multi-agent IDE.

This is separate from voice. While Leo is devving, the useful loop is text/chat plus coding/test controls: open a browser, inspect a plan, run the harness, see output, then spawn or route the next agent lane.

## Evidence

- [Source: Leo 2026-05-24] "#1 goal is focus on ability to code and run our /autobot-resplit-web test frameworks as a starting point add to vidux ability to multiplex and multi agent and the IDE to run ai coding like its claude code or codex IDK or terminal too".
- [Source: skill] `/Users/leokwan/Development/ai-leo/skills/autobot-resplit-web/SKILL.md` says the installed proof command is `~/bin/autobot-resplit-web --public-only`, and parallel-agent mode must use worktrees plus isolated ports instead of building in the primary checkout.
- [Source: code] `/Users/leokwan/Development/moussey/lib/coding-workbench.ts` exposes a single allowlisted job, `resplit-web-autobot`, with `status`, `dry-run`, and `public` modes.
- [Source: code] `/Users/leokwan/Development/moussey/app/api/coding/run/route.ts` streams allowlisted command output as SSE and rejects arbitrary job ids.
- [Source: code] `/Users/leokwan/Development/moussey/lib/coding-lanes.ts` computes worktree/branch/port isolation plans for `resplit-web-autobot` without creating worktrees or mutating repos.
- [Source: code] `/Users/leokwan/Development/moussey/app/api/coding/lanes/preflight/route.ts` exposes the no-mutation lane preflight as `POST /api/coding/lanes/preflight`.
- [Source: code] `/Users/leokwan/Development/moussey/app/api/coding/lanes/run/route.ts` creates a throwaway worktree, atomically claims a `PW_PORT`, runs an allowlisted `autobot-resplit-web` mode inside the worktree, then removes the worktree, deletes the temp branch, and releases the port lock.
- [Source: code] `/Users/leokwan/Development/moussey/app/coding/page.tsx` gives the local UI at `http://127.0.0.1:4321/coding`.
- [Source: verification 2026-05-24] Live `/api/coding/jobs` reports ready with repo `/Users/leokwan/Development/resplit-web` and command `/Users/leokwan/bin/autobot-resplit-web`; live `/api/coding/run` `status` streamed exit 0; Playwright opened `/coding`, clicked `Status`, saw terminal output, and reported zero console errors.
- [Source: verification 2026-05-24] Live `POST /api/coding/lanes/preflight` returned `ready:true`, selected port `3110`, and generated the planned `resplit-web-worktrees` worktree path, branch, build/start/test commands, and lock cleanup command; Playwright clicked `Lane Preflight` in `/coding` and reported zero console errors.
- [Source: verification 2026-05-24] Live `POST /api/coding/lanes/run` with `mode:"status"` claimed port `3110`, created `/Users/leokwan/Development/resplit-web-worktrees/web-resplit-web-autobot-*`, ran `/Users/leokwan/bin/autobot-resplit-web --status` with `AUTOBOT_RESPLIT_WEB_REPO` pointed at that worktree, removed the worktree, deleted branch `codex/web-resplit-web-autobot-*`, released the lock, returned `exitCode:0` and `teardownOk:true`, and left no matching worktree, branch, or lock behind.

## Constraints

- ALWAYS: Start with allowlisted harnesses, not arbitrary shell execution.
- ALWAYS: Keep Moussey LAN-only. No public tunnels, public DNS, or browser-exposed remote code execution surface.
- ALWAYS: Keep the primary `~/Development/resplit-web` checkout reserved for Leo's foreground/editor session and existing cron. Parallel coding agents must use worktrees and isolated ports.
- ALWAYS: Capture every accepted coding run in an append-only audit log before the command starts.
- ALWAYS: Put durable project state in Vidux plans. Use Moussey runtime JSONL only for execution audit.
- NEVER: Add cross-Mac repo writes, cross-Mac plan mutation, or SSH-based task ownership bounce.
- NEVER: Run production/money/live external actions from this workbench without a separate explicit gate.
- NEVER: Let a browser POST arbitrary commands, cwd, env, branch names, or shell fragments.

## Tasks

- [completed] **C1: Allowlisted Resplit Web Autobot job catalog.** Added `lib/coding-workbench.ts` with `resplit-web-autobot` only, defaulting to `~/Development/resplit-web` plus `~/bin/autobot-resplit-web`, and mapping modes to fixed argv. [Evidence: `/Users/leokwan/Development/moussey/lib/coding-workbench.ts`; `lib/coding-workbench.test.ts`]
- [completed] **C2: Coding job readiness API.** Added `GET /api/coding/jobs` so the UI can show whether the repo and command are locally ready, with mutation methods rejected. [Evidence: `/Users/leokwan/Development/moussey/app/api/coding/jobs/route.ts`; `app/api/coding/jobs/route.test.ts`]
- [completed] **C3: SSE run API for allowlisted harness output.** Added `POST /api/coding/run` for `{jobId, mode}`, with fixed cwd/command/args, timeout, stdout/stderr SSE frames, completion frames, and JSONL audit entries. [Evidence: `/Users/leokwan/Development/moussey/app/api/coding/run/route.ts`; `app/api/coding/run/route.test.ts`]
- [completed] **C4: `/coding` workbench UI.** Added a Moussey dashboard tile plus the terminal-like workbench with `Status`, `Dry Run`, and `Run Public Matrix` controls. [Evidence: `/Users/leokwan/Development/moussey/app/page.tsx`; `/Users/leokwan/Development/moussey/app/coding/page.tsx`]
- [completed] **C5: Live local proof.** Verified status mode through the real LaunchAgent, `npm run test:brain-dispatcher`, `npx tsc --noEmit`, `npm run build`, `moussey-trigger-doctor --brief`, `vidux-browse health`, and Playwright UI proof at `/coding`. [Evidence: 2026-05-24 Progress]
- [completed] **C6a: Worktree/port-isolated lane preflight.** Added a second-level lane abstraction that checks `3110..3119`, detects locks/listeners, derives a worktree path and branch, and shows the exact future commands without touching the repo. [Evidence: `/Users/leokwan/Development/moussey/lib/coding-lanes.ts`; `/Users/leokwan/Development/moussey/app/api/coding/lanes/preflight/route.ts`; `/Users/leokwan/Development/moussey/app/coding/page.tsx`]
- [completed] **C6b: Worktree/port-isolated Autobot lane runner.** Turned the preflight plan into a gated prepare/run/teardown path that creates a `resplit-web` worktree, atomically claims a `3110..3119` port, runs an allowlisted `autobot-resplit-web` mode there, and tears down safely. [Evidence: `/Users/leokwan/Development/moussey/app/api/coding/lanes/run/route.ts`; `/Users/leokwan/Development/moussey/app/api/coding/lanes/run/route.test.ts`; live `Run Lane Status` proof]
- [pending] **C6c: Local-server build/start/Playwright lane stage.** Extend the lane runner beyond the installed Autobot wrapper so it can run the local `npm run build` + `npm run start -- --port $PW_PORT` + targeted Playwright command sequence inside the claimed worktree, with server PID cleanup.
- [completed] **C7: Chat-to-coding handoff.** From `/chat`, Leo can send the current prompt/session/evidence to `/coding` as a persisted proposed run or lane spawn. Chat remains the conversation surface; `/coding` owns execution. [Evidence: `/Users/leokwan/Development/moussey/lib/coding-handoffs.ts`; `/Users/leokwan/Development/moussey/app/api/coding/handoffs/route.ts`; `/Users/leokwan/Development/moussey/app/chat/page.tsx`; `/Users/leokwan/Development/moussey/app/coding/page.tsx`; Playwright C7 proof]
- [pending] **C8: Active run dashboard.** List recent/active coding runs from `~/.moussey/coding-runs.jsonl`, including status, mode, duration, exit code, and output tail.
- [pending] **C9: Claude/Codex/local agent spawn proof.** Add one tightly scoped lane that can launch Codex or Claude against an isolated worktree with explicit cwd, branch, task prompt, allowed commands, and output capture. Do not expose this until C6 proves isolation.
- [pending] **C10: Vidux integration.** Add plan-aware links from vidux-browse and/or `/chat` so a plan row can open `/coding` with the right harness context without mutating the plan remotely.

## Decision Log

- [DIRECTION] [2026-05-24] Coding/test harness control is the command-center MVP priority ahead of voice. Reason: Leo clarified that while devving he needs to listen to plans, chat live with Moussey, run local harnesses, and drive work from anywhere; voice can follow after text/coding dispatch is real.
- [DIRECTION] [2026-05-24] `/coding` starts as an allowlisted harness runner, not a shell. Reason: this gives Leo real local test execution while preserving the no-arbitrary-browser-RCE and no-cross-Mac-write boundary.
- [DIRECTION] [2026-05-24] `/autobot-resplit-web` is the first proof surface. Reason: it already has a deterministic public matrix plus documented worktree/port isolation for future multi-agent mode.
- [DIRECTION] [2026-05-24] The multi-agent IDE direction is worktree lanes, not primary-checkout mutation. Reason: the skill explicitly warns that parallel agents must not build or edit the primary `~/Development/resplit-web` checkout.
- [DIRECTION] [2026-05-24] Lane preflight ships before lane mutation. Reason: Leo needs to see the exact worktree, port, branch, and commands before the UI is allowed to spawn an agent or touch a checkout.
- [DIRECTION] [2026-05-24] Chat handoff is a persisted proposal, not execution. Reason: this keeps `/chat` as a safe intent surface while `/coding` remains the only surface that can run allowlisted harnesses or future agent lanes.

## Claims Board

| Task | Status | Owner | Blocking | Updated |
|---|---|---|---|---|
| C1: Job catalog | [completed] | Studio Codex | none | 2026-05-24 |
| C2: Readiness API | [completed] | Studio Codex | none | 2026-05-24 |
| C3: Run API | [completed] | Studio Codex | none | 2026-05-24 |
| C4: Workbench UI | [completed] | Studio Codex | none | 2026-05-24 |
| C5: Live proof | [completed] | Studio Codex | none | 2026-05-24 |
| C6a: Isolated lane preflight | [completed] | Studio Codex | none | 2026-05-24 |
| C6b: Isolated Autobot lane runner | [completed] | Studio Codex | none | 2026-05-24 |
| C6c: Local-server build/start/Playwright lane | [pending] | - | needs server lifecycle + PID cleanup | 2026-05-24 |
| C7: Chat-to-coding handoff | [completed] | Studio Codex | none | 2026-05-24 |
| C8: Active run dashboard | [pending] | - | none | 2026-05-24 |
| C9: Agent spawn proof | [pending] | - | depends on C6c for full local server lanes; can start with C6b for read-only status lanes | 2026-05-24 |
| C10: Vidux integration | [pending] | - | depends on C7 shape | 2026-05-24 |

## Progress

- [2026-05-24] Shipped the first local coding workbench slice in Moussey. Added `lib/coding-workbench.ts`, `/api/coding/jobs`, `/api/coding/run`, `/coding`, and the home-dashboard Coding tile. The only executable job is `resplit-web-autobot`; modes map to fixed args: `--status`, `--dry-run`, and `--public-only`. Verification: `npm run test:brain-dispatcher` passes 62/62 including coding tests; `npx tsc --noEmit` passes; `npm run build` passes with the known Turbopack NFT warning; `moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio`; `vidux-browse health` reports `http://127.0.0.1:7191`; live `/api/coding/jobs` reports ready; live `/api/coding/run` status exits 0; Playwright opened `http://127.0.0.1:4321/coding`, clicked `Status`, rendered terminal output, and saw zero console errors. Next: C6 worktree/port-isolated lane runner so this can safely become a true multi-agent coding IDE.
- [2026-05-24] Advanced the multi-agent coding lane from vague spawn idea to visible no-mutation preflight. Added `lib/coding-lanes.ts`, `POST /api/coding/lanes/preflight`, tests, and `/coding` UI for `Lane Preflight`. Live API selected port `3110`, produced a `codex/web-resplit-web-autobot-*` branch, a `/Users/leokwan/Development/resplit-web-worktrees/web-*` worktree path, and planned build/start/Playwright commands without creating anything. Verification: `npm run test:brain-dispatcher` passes 68/68; `npx tsc --noEmit` passes; `npm run build` passes with the known Turbopack NFT warning; `scripts/moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio`; `bin/vidux-browse health` reports `http://127.0.0.1:7191`; live preflight API returns `ready:true`; Playwright opened `http://127.0.0.1:4321/coding`, clicked `Lane Preflight`, rendered the worktree/port/command plan, and saw zero console warnings/errors. Next: C6b should claim a lock, create the worktree, run the harness, and teardown with audit logging.
- [2026-05-24] Shipped the first real worktree/port-isolated runner. Added `POST /api/coding/lanes/run` plus `/coding` `Run Lane Status`: the route resolves the allowlisted job/mode, claims a `resplit-web-pw-port-*.lock` with `wx`, creates a throwaway `resplit-web` worktree and `codex/web-*` branch, runs `/Users/leokwan/bin/autobot-resplit-web --status` inside that worktree with `AUTOBOT_RESPLIT_WEB_REPO`, `PW_PORT`, and `PW_BASE_URL` set, then removes the worktree, deletes the branch, and releases the lock. Verification: focused lane tests pass 9/9; `npm run test:brain-dispatcher` passes 71/71; `npx tsc --noEmit` passes; `npm run build` passes with the known Turbopack NFT warning; `scripts/moussey-trigger-doctor --brief` reports accepting; `bin/vidux-browse health` reports `http://127.0.0.1:7191`; live API lane run returned `exitCode:0` and `teardownOk:true`; post-run checks found no `web-resplit-web-autobot` worktree, no `codex/web-resplit-web-autobot-*` branch, and no `resplit-web-pw-port-31xx.lock`; Playwright clicked `Run Lane Status` in `http://127.0.0.1:4321/coding` with zero console warnings/errors. Next: C6c local server lifecycle or C7 chat-to-coding handoff.
- [2026-05-24] Closed C7 chat-to-coding handoff. Added `lib/coding-handoffs.ts`, `POST /api/coding/handoffs`, `GET /api/coding/handoffs/:handoffId`, a `Code lane` action on user bubbles in `/chat`, and a handoff panel in `/coding?handoff=<id>` with Preflight / Run Status Lane controls. The handoff stores chat session id, source turn id, prompt, attachment summaries, proposed action, and the allowlisted `resplit-web-autobot` job label; it does not execute anything until `/coding` calls the existing lane APIs. Verification: `npm run test:brain-dispatcher` passes 76/76; `npx tsc --noEmit` passes; `npm run build` passes with the known Turbopack NFT warning; `scripts/moussey-trigger-doctor --brief` reports `endpoint=accepting secret=ok selfname=Studio peers_configured=3`; `bin/vidux-browse health` reports `http://127.0.0.1:7191`; live handoff API created `/coding?handoff=20f1821e-e127-4a5b-9e38-1dfe29b32b97`; live lane preflight from that handoff returned `ready:true`, `nextPort:3110`, and `codex/web-chat-codex-c7-*`; Playwright opened `http://127.0.0.1:4321/chat?session=codex-c7-ui`, clicked `Code lane`, landed at `http://127.0.0.1:4321/coding?handoff=469e116c-5be9-4a89-a72d-46d701a0b0b2`, clicked `Preflight`, saw `ready: yes`, and reported zero console warnings/errors. Screenshot: `/tmp/moussey-c7-chat-to-coding.png`. Next: C6c local build/start/Playwright lanes, then C9 agent spawn proof.

## Local Links

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Coding Jobs API: `http://127.0.0.1:4321/api/coding/jobs`
- Coding Lane Preflight API: `http://127.0.0.1:4321/api/coding/lanes/preflight` (`POST` only)
- Coding Lane Run API: `http://127.0.0.1:4321/api/coding/lanes/run` (`POST` only)
- Coding Handoffs API: `http://127.0.0.1:4321/api/coding/handoffs` (`POST` only)
- Latest C7 proof handoff: `http://127.0.0.1:4321/coding?handoff=469e116c-5be9-4a89-a72d-46d701a0b0b2`
- Moussey Chat: `http://127.0.0.1:4321/chat`
- Vidux Browser: `http://127.0.0.1:7191`

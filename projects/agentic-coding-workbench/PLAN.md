# Agentic Coding Workbench

> **Parent plan:** `~/Development/vidux/projects/agentic-command-center/PLAN.md`.

## Purpose

Give Leo a LAN-local coding/test harness workbench inside Moussey. The first proof surface is `resplit-web` through `/autobot-resplit-web`: claim a disposable worktree, claim an isolated Playwright port, run the build/server/test sequence, stream output to `/coding`, and tear everything down.

This is the coding half of the command-center MVP. Chat stays the intent surface; `/coding` owns execution.

## Evidence

- [Source: Leo 2026-05-24] "#1 goal is focus on ability to code and run our /autobot-resplit-web test frameworks as a starting point add to vidux ability to multiplex and multi agent and the IDE to run ai coding like its claude code or codex IDK or terminal too".
- [Source: skill] `/Users/leokwan/Development/ai-leo/skills/autobot-resplit-web/SKILL.md` says parallel web agents must use git worktrees, isolated `PW_PORT` values, per-lane servers, and mandatory teardown.
- [Source: code] `/Users/leokwan/Development/moussey/lib/coding-workbench.ts` exposes the allowlisted `resplit-web-autobot` job.
- [Source: code] `/Users/leokwan/Development/moussey/lib/coding-lanes.ts` now resolves worktree lanes from `origin/main` by default, claims ports `3110..3119`, launches coding children with a clean shell-like env, and adds lane-only `local-smoke`.
- [Source: code] `/Users/leokwan/Development/moussey/app/api/coding/lanes/run/route.ts` fetches trunk, creates the worktree, runs `npm ci --include=dev`, `npm run build`, `npm run start -- --port $PW_PORT`, targeted Playwright, and tears down server/worktree/branch/lock.
- [Source: verification 2026-05-24] Focused lane tests pass 10/10, including a fake local server lifecycle that reaches build, server-ready, Playwright, server-stopped, and cleanup.
- [Source: verification 2026-05-24] `npm run test:brain-dispatcher` passes 82/82; `npx tsc --noEmit` passes; `npm run build` passes with the known Moussey Turbopack NFT warning; `http://127.0.0.1:4321/api/health` returns ok after LaunchAgent restart.
- [Source: verification 2026-05-24] Live `/api/coding/lanes/run` local-smoke run `5eae7ddc-5afd-496a-b355-c9159df0097f` created an `origin/main`-based `resplit-web` worktree at `a7aa458`, ran isolated `npm ci --include=dev`, built Next, started `http://127.0.0.1:3110`, ran `e2e/landing-smoke.spec.ts`, and surfaced the real target failure `section #globe should render on the landing page`. Teardown returned `teardownOk:true`, deleted branch `codex/web-c6d-teardown-proof-*`, released `/var/.../resplit-web-pw-port-3110.lock`, and left no matching worktree/listener/lock behind.
- [Source: UI verification 2026-05-24] Playwright opened `http://127.0.0.1:4321/coding`, saw `Run Local Smoke` and `Lane Preflight`, captured `/tmp/moussey-c6c-coding-ui.png`, and saw zero console messages.

## Constraints

- ALWAYS: Start with allowlisted harnesses, not arbitrary shell execution.
- ALWAYS: Keep primary `~/Development/resplit-web` reserved for Leo's foreground/editor session.
- ALWAYS: Create coding lanes from remote trunk (`origin/main`) by default, including a `git fetch --prune origin` before worktree creation; use `MOUSSEY_CODING_BASE_REF` only for deliberate overrides.
- ALWAYS: Install dependencies inside the claimed worktree for local-server lanes. Primary `node_modules` symlink is opt-in only via `MOUSSEY_CODING_LINK_NODE_MODULES=1`.
- ALWAYS: Spawn coding children with a clean shell-like env plus explicit job variables, not the whole Moussey/Next production server environment.
- ALWAYS: Capture accepted/completed runs in `~/.moussey/coding-runs.jsonl`.
- NEVER: Add cross-Mac repo writes, SSH ownership bounce, public tunnels, arbitrary browser-posted shell, production/money actions, or force-push behavior.

## Tasks

- [completed] **C1: Allowlisted Resplit Web Autobot job catalog.** `resplit-web-autobot` only, with fixed status/dry-run/public args.
- [completed] **C2: Coding job readiness API.** `GET /api/coding/jobs` shows local repo/bin readiness.
- [completed] **C3: SSE run API for allowlisted harness output.** `POST /api/coding/run` streams stdout/stderr/complete for fixed job modes.
- [completed] **C4: `/coding` workbench UI.** Moussey dashboard page for jobs, terminal output, and lane controls.
- [completed] **C5: Worktree/port lane preflight.** Shows branch, base ref, worktree path, port budget, and planned commands without mutation.
- [completed] **C6: Worktree/port Autobot lane runner.** Creates worktree, claims `PW_PORT`, runs allowlisted Autobot mode, tears down.
- [completed] **C6c: Local-server build/start/Playwright lane mode.** Added lane-only `local-smoke` with isolated `npm ci --include=dev`, `npm run build`, `npm run start -- --port $PW_PORT`, targeted `npx playwright test e2e/landing-smoke.spec.ts --project=chromium-desktop --reporter=list`, process-group server cleanup, and UI button. Unit proof reaches full lifecycle; live proof now reaches Playwright and still cleans up.
- [completed] **C7: Chat-to-coding handoff.** `/chat` can stage a prompt into `/coding?handoff=<id>` without executing from chat.
- [completed] **C6d: Clean child env + remote trunk.** Fixed the false `next build` blocker by fetching `origin/main`, forcing dev dependency install under LaunchAgent production env, and stripping Next/Moussey production internals from child coding env. Live C6d reaches build/start/Playwright; remaining red is target app/test assertion `#globe` missing in `resplit-web` landing smoke.
- [pending] **C6e: Target failure handoff policy.** Decide whether `/coding` should open a follow-up isolated Resplit Web code lane, create a Vidux annotation, or stage a chat handoff when a target test fails.
- [pending] **C8: Active run dashboard.** List recent/active coding runs from `~/.moussey/coding-runs.jsonl`.
- [pending] **C9: Claude/Codex/local agent spawn proof.** Launch one tightly scoped Codex or Claude agent against an isolated worktree with explicit cwd/branch/prompt/output capture.
- [pending] **C10: Vidux integration.** Open `/coding` from a Vidux plan row/handoff without remote plan mutation.

## Decision Log

- [DIRECTION] [2026-05-24] Coding/test harness control is the command-center MVP priority ahead of voice. Reason: Leo clarified the devving loop is text/chat plus local coding controls, not audio first.
- [DIRECTION] [2026-05-24] `/coding` is an allowlisted harness runner before it becomes a shell or full IDE. Reason: this proves local test execution while avoiding arbitrary browser RCE.
- [DIRECTION] [2026-05-24] Lane worktrees default to `main`, not whatever branch the primary checkout is on. Reason: the primary `resplit-web` checkout was sitting on stale `claude/web-FLAKE-e2e-investigation`; the Autobot skill says parallel agents clone from main.
- [DIRECTION] [2026-05-24] Local-server lanes run `npm ci` inside the worktree by default. Reason: symlinking primary `node_modules` is faster but weakens lane isolation; use it only via explicit env override.
- [DIRECTION] [2026-05-24] Coding child processes must not inherit the whole Moussey Next server env. Reason: live C6d proved `NEXT_*`/LaunchAgent parent env leakage can make a nested Next build fail before normal output; child jobs now receive a minimal shell-like env plus explicit lane variables.

## Local Links

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Coding Jobs API: `http://127.0.0.1:4321/api/coding/jobs`
- Coding Lane Preflight API: `http://127.0.0.1:4321/api/coding/lanes/preflight`
- Coding Lane Run API: `http://127.0.0.1:4321/api/coding/lanes/run`
- Moussey Chat: `http://127.0.0.1:4321/chat`
- Vidux Browser: `http://127.0.0.1:7191`

## Progress

- [2026-05-24] Shipped C6c in Moussey. Added `local-smoke` lane mode, isolated dependency install, process-group server cleanup, UI controls, and route/tests. Initial verification: focused lane tests 9/9; `npm run test:brain-dispatcher` 78/78; `npx tsc --noEmit`; `npm run build`; doctor accepting; Vidux browser healthy; Playwright UI proof at `/coding`. Initial live local-smoke proved the lane substrate and cleanup but exposed a false Resplit Web build blocker before `next start`/Playwright.
- [2026-05-24] Claimed C6d after text-chat MVP closeout. Next proof target: reproduce the clean-main `resplit-web` build failure directly, patch the owning surface, then rerun Moussey `/coding` local-smoke until it reaches targeted Playwright or exposes the next concrete blocker.
- [2026-05-24] Completed C6d in Moussey. `local-smoke` now fetches `origin/main`, runs `npm ci --include=dev`, launches children with clean env, and treats `npm run start` SIGTERM exit code 143 as normal teardown. Verification: `npm run test:brain-dispatcher` 82/82; `npx tsc --noEmit`; `npm run build`; LaunchAgent restart + `/api/health`; live run `5eae7ddc-5afd-496a-b355-c9159df0097f` reached build/start/Playwright on `resplit-web` `a7aa458` and reported `#globe` missing, with `teardownOk:true`.

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
- [Source: code] `/Users/leokwan/Development/moussey/lib/capability-catalog.ts` inventories the coding-agent substrate: active skill symlinks, owned skill source paths, and Codex MCP server names/commands/env-key names without exposing env values.
- [Source: code] `/Users/leokwan/Development/moussey/app/api/coding/capabilities/route.ts` exposes the read-only capability catalog for `/coding`.
- [Source: verification 2026-05-24] Focused lane tests pass 10/10, including a fake local server lifecycle that reaches build, server-ready, Playwright, server-stopped, and cleanup.
- [Source: verification 2026-05-24] `npm run test:brain-dispatcher` passes 82/82; `npx tsc --noEmit` passes; `npm run build` passes with the known Moussey Turbopack NFT warning; `http://127.0.0.1:4321/api/health` returns ok after LaunchAgent restart.
- [Source: verification 2026-05-24] Live `/api/coding/lanes/run` local-smoke run `5eae7ddc-5afd-496a-b355-c9159df0097f` created an `origin/main`-based `resplit-web` worktree at `a7aa458`, ran isolated `npm ci --include=dev`, built Next, started `http://127.0.0.1:3110`, ran `e2e/landing-smoke.spec.ts`, and surfaced the real target failure `section #globe should render on the landing page`. Teardown returned `teardownOk:true`, deleted branch `codex/web-c6d-teardown-proof-*`, released `/var/.../resplit-web-pw-port-3110.lock`, and left no matching worktree/listener/lock behind.
- [Source: UI verification 2026-05-24] Playwright opened `http://127.0.0.1:4321/coding`, saw `Run Local Smoke` and `Lane Preflight`, captured `/tmp/moussey-c6c-coding-ui.png`, and saw zero console messages.
- [Source: verification 2026-05-24] Live `GET http://127.0.0.1:4321/api/coding/capabilities` returned 8/8 skills found (`autobot-resplit-web`, `vidux`, `pilot-leo`, `amp`, `auto`, `captain`, `nia`, `moussey`) and 5 MCP servers configured (`everything`, `figma`, `nia`, `node_repl`, `openaiDeveloperDocs`), with only env key names. Playwright opened `/coding`, saw the capability panel and `nia-mcp-server`, captured `/tmp/moussey-coding-capabilities-20260524.png`, and saw zero console/page errors.
- [Source: coordination 2026-05-24] Thread heartbeat automation `vidux-moussey-harmony-listener` is active; Moussey ping `dfde0d8e-2888-4a36-ba5f-edd742f7c251` records the first listener pass against Vidux `76834ee` and Moussey `8f87278`.
- [Source: verification 2026-05-24] Live C9 run `d2c80ba8-8a9b-4bdb-a530-8c06178f4844` launched `codex exec --ephemeral --sandbox read-only` from `/coding` inside isolated worktree `/Users/leokwan/Development/resplit-web-worktrees/web-c9-codex-skill-probe-20260524T062746Z-pckyvb` on branch `codex/web-c9-codex-skill-probe-20260524T062746Z-pckyvb`, with `PW_PORT=3110`. Nested Codex ran as OpenAI Codex v0.130.0, model `gpt-5.5`, provider `openai`, reasoning effort `xhigh`, read `/vidux`, `/pilot-leo`, `/captain`, `/nia`, `/autobot-resplit-web`, identified `resplit-web`, confirmed `e2e/landing-smoke.spec.ts` exists, and returned the next safest action. The route tore down the worktree, deleted the branch, released `/var/folders/zz/1lvbg08x21b1bqhmn2mngwn40000gn/T/resplit-web-pw-port-3110.lock`, and completed with `exitCode:0`, `teardownOk:true`; SSE evidence is `/tmp/moussey-c9-codex-skills-probe-20260524T062746Z.sse`.
- [Source: verification 2026-05-24] The live C9 probe also exposed real MCP/auth boundaries: Codex attempted configured Cloudflare and Figma MCP startup, but both reported auth-required token errors. That is an environment readiness gap for those cloud tools, not a Moussey lane-spawn blocker.
- [Source: coordination 2026-05-24] Moussey commit `5fa955a` pushed `codex-skills-probe` to `main`. Harmony probe run `cb733047-486a-4f3e-97b8-91a943e5f739` repeated the read-only Codex skill lane at `PW_PORT=3111`, verified clean `resplit-web` `origin/main` at `846ff98`, confirmed `/vidux` + `/autobot-resplit-web` as directly relevant, completed with `exitCode:0`, `teardownOk:true`, and posted agreement ping `bae1843a-5e4d-4631-92e4-bd5b0e564bdf`.

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
- [completed] **C11: Skills/MCP capability catalog.** `/coding` now shows the local coding-agent substrate before multiplexing: active skill symlinks, owned skill source paths, MCP server commands, and env key names only. This proves the lane can see `/autobot-resplit-web`, `/vidux`, `/pilot-leo`, `/captain`, `/nia`, and Codex-side MCP config without leaking secrets.
- [active] **C12: Harmony listener and workflow sync audit.** Recurring thread listener checks Moussey pings, LAN health, provider readiness, capability substrate, git heads, and this canonical plan until Vidux and Moussey are both current, workflows are refreshed on their owning side, and no new coordination pings contradict agreement.
- [pending] **C6e: Target failure handoff policy.** Decide whether `/coding` should open a follow-up isolated Resplit Web code lane, create a Vidux annotation, or stage a chat handoff when a target test fails.
- [pending] **C8: Active run dashboard.** List recent/active coding runs from `~/.moussey/coding-runs.jsonl`.
- [completed] **C9: Claude/Codex/local agent spawn proof.** `/coding` launches a tightly scoped Codex read-only skill probe against an isolated worktree with explicit cwd/branch/prompt/output capture, then tears the lane down.
- [pending] **C10: Vidux integration.** Open `/coding` from a Vidux plan row/handoff without remote plan mutation.
- [pending] **C13: Codex verifier/edit lane.** Graduate from read-only skill probe to a bounded isolated-worktree agent lane that may run build/start/Playwright and, after a separate explicit mode gate, patch only the claimed worktree.

## Decision Log

- [DIRECTION] [2026-05-24] Coding/test harness control is the command-center MVP priority ahead of voice. Reason: Leo clarified the devving loop is text/chat plus local coding controls, not audio first.
- [DIRECTION] [2026-05-24] `/coding` is an allowlisted harness runner before it becomes a shell or full IDE. Reason: this proves local test execution while avoiding arbitrary browser RCE.
- [DIRECTION] [2026-05-24] Lane worktrees default to `main`, not whatever branch the primary checkout is on. Reason: the primary `resplit-web` checkout was sitting on stale `claude/web-FLAKE-e2e-investigation`; the Autobot skill says parallel agents clone from main.
- [DIRECTION] [2026-05-24] Local-server lanes run `npm ci` inside the worktree by default. Reason: symlinking primary `node_modules` is faster but weakens lane isolation; use it only via explicit env override.
- [DIRECTION] [2026-05-24] Coding child processes must not inherit the whole Moussey Next server env. Reason: live C6d proved `NEXT_*`/LaunchAgent parent env leakage can make a nested Next build fail before normal output; child jobs now receive a minimal shell-like env plus explicit lane variables.
- [DIRECTION] [2026-05-24] `/coding` can spawn configured Codex agents, but the first agent lane stays read-only. Reason: this proves skill/MCP visibility and isolated-worktree orchestration before allowing a browser button to create code edits.

## Local Links

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Coding Jobs API: `http://127.0.0.1:4321/api/coding/jobs`
- Coding Capabilities API: `http://127.0.0.1:4321/api/coding/capabilities`
- Coding Lane Preflight API: `http://127.0.0.1:4321/api/coding/lanes/preflight`
- Coding Lane Run API: `http://127.0.0.1:4321/api/coding/lanes/run`
- Moussey Chat: `http://127.0.0.1:4321/chat`
- Vidux Browser: `http://127.0.0.1:7191`

## Progress

- [2026-05-24] Shipped C6c in Moussey. Added `local-smoke` lane mode, isolated dependency install, process-group server cleanup, UI controls, and route/tests. Initial verification: focused lane tests 9/9; `npm run test:brain-dispatcher` 78/78; `npx tsc --noEmit`; `npm run build`; doctor accepting; Vidux browser healthy; Playwright UI proof at `/coding`. Initial live local-smoke proved the lane substrate and cleanup but exposed a false Resplit Web build blocker before `next start`/Playwright.
- [2026-05-24] Claimed C6d after text-chat MVP closeout. Next proof target: reproduce the clean-main `resplit-web` build failure directly, patch the owning surface, then rerun Moussey `/coding` local-smoke until it reaches targeted Playwright or exposes the next concrete blocker.
- [2026-05-24] Completed C6d in Moussey. `local-smoke` now fetches `origin/main`, runs `npm ci --include=dev`, launches children with clean env, and treats `npm run start` SIGTERM exit code 143 as normal teardown. Verification: `npm run test:brain-dispatcher` 82/82; `npx tsc --noEmit`; `npm run build`; LaunchAgent restart + `/api/health`; live run `5eae7ddc-5afd-496a-b355-c9159df0097f` reached build/start/Playwright on `resplit-web` `a7aa458` and reported `#globe` missing, with `teardownOk:true`.
- [2026-05-24] Completed C11 in Moussey. Added read-only skills/MCP capability catalog API and `/coding` UI panel, verified no secret values are returned. Verification: `npm run test:brain-dispatcher` 86/86; `npm run test:cleaner` 72/72 including cleaner vision-caption coverage; `npx tsc --noEmit`; `npm run build`; live `/api/health`; live `/api/coding/capabilities`; Playwright UI proof at `/coding` with screenshot `/tmp/moussey-coding-capabilities-20260524.png` and zero console/page errors.
- [2026-05-24] Started C12 harmony listener. First pass: Vidux and Moussey `main` are synced to pushed heads (`76834ee`, `8f87278`), local `:4321` and `:7191` health checks pass, LAN peers Studio/M4 Pro/Nicole/M1 Max are reachable and healthy, `/api/chat/providers` shows local+Codex ready with Claude CLI auth still a known local follow-up, and filtered Moussey coordination pings show no newer Vidux/Moussey conflict after M4 Pro's goodnight handoff. Posted Moussey ping `dfde0d8e-2888-4a36-ba5f-edd742f7c251` so the listener state is visible in the cross-Mac feed.
- [2026-05-24] Completed C9 in Moussey. Added `codex-skills-probe` lane mode and `/coding` button, then ran live C9 run `d2c80ba8-8a9b-4bdb-a530-8c06178f4844`. The spawned Codex session loaded Leo's requested skills, inspected `resplit-web` in the isolated worktree, confirmed `e2e/landing-smoke.spec.ts`, and returned a next action without editing. Teardown removed the worktree/branch and released `PW_PORT=3110`; proof at `/tmp/moussey-c9-codex-skills-probe-20260524T062746Z.sse`.
- [2026-05-24] C12 second pass blended the Moussey side back into Vidux. Moussey `main` now includes `5fa955a` (`moussey: add read-only codex skill probe lane`), and live harmony run `cb733047-486a-4f3e-97b8-91a943e5f739` proved the pushed lane still spawns Codex read-only, keeps the worktree clean, returns skill-aware guidance, deletes the temporary branch/worktree, and releases `PW_PORT=3111`. Agreement ping `bae1843a-5e4d-4631-92e4-bd5b0e564bdf` records the Moussey implementation, Vidux plan sync, and corrected 2-minute heartbeat.

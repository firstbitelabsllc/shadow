# Moussey Tool Integration Architecture

Date: 2026-05-25
Role: Specialist 2, Moussey integration architect
Scope: read-only inspection of `/Users/leokwan/Development/moussey` coding command-center routes. No Moussey source edits made.

## Existing integration seams and exact files/functions to extend

Moussey already has the right architecture skeleton. The smallest path is to treat aider/opencode/goose/openhands/Continue as new entries in the existing tool-action and route catalog, not as a new command runner.

- `/Users/leokwan/Development/moussey/lib/coding-tool-actions.ts`
  - Extend `CODING_TOOL_ACTION_IDS` at line 8 with tool-specific IDs such as `aider-plan`, `opencode-plan`, `goose-plan`, `openhands-local-url`, `continue-open-workspace`.
  - Extend `CodingToolActionRunSpec` at line 21 only if a tool needs additional UI metadata. Prefer keeping the existing `{ command, args, cwd, env, timeoutMs, streamLimitBytes, outputLastMessagePath }` shape.
  - Extend `resolveCodingToolActionRun()` at line 52 with fixed, allowlisted run specs. This is the main command construction seam.
  - Reuse `codingChildBaseEnv()` from `/Users/leokwan/Development/moussey/lib/coding-workbench.ts` so tool children keep the existing clean shell-like env boundary and do not inherit Next internals.

- `/Users/leokwan/Development/moussey/lib/capability-catalog.ts`
  - Add an `installedCodingAgents` or `codingAgentTools` section in `CapabilityCatalog` near the existing action/routing fields.
  - Extend `readCapabilityCatalog()` around lines 439-446 so command discovery feeds `toolActions`, `delegationRoutes`, and `routingMap` from the same sanitized facts.
  - Extend `readToolActions()` at line 1436 to report each tool's readiness: command present, configured env-key names, recommended execution surface, and current status.
  - Extend `buildDelegationRoutes()` at line 1104 and `buildRoutingMap()` at line 1218 so the UI and future Vidux handoffs can route by tool, not by hard-coded React state.
  - Extend `skillOperationalContract()` at line 1630 only if a tool becomes associated with a skill or operational contract; otherwise keep these tools as command-center routes.

- `/Users/leokwan/Development/moussey/lib/coding-workers.ts`
  - Reuse `startDetachedCodingWorker()` at line 70 for any long-running or agentic CLI.
  - Reuse `readCodingWorkerStatus()` at line 165 and `listCodingWorkers()` for UI polling.
  - Keep `buildCodexRouteHint()` at line 277 Codex-specific. Do not generalize account-routing metadata unless another tool has a similarly real, readable local router.

- `/Users/leokwan/Development/moussey/app/api/coding/**`
  - `/api/coding/capabilities` already exposes the read-only catalog through `GET()` at `app/api/coding/capabilities/route.ts:10`.
  - `/api/coding/tool-actions/run` already streams foreground allowlisted local actions through `POST()` at `app/api/coding/tool-actions/run/route.ts:28`.
  - `/api/coding/workers` already starts detached allowlisted workers through `POST()` at `app/api/coding/workers/route.ts:28` and lists workers via `GET()` at line 14.
  - `/api/coding/workers/[workerId]` already returns status/log/final-message via `GET()` at `app/api/coding/workers/[workerId]/route.ts:13`.
  - `/api/coding/lanes/run` at `app/api/coding/lanes/run/route.ts:52` should remain the disposable-worktree Resplit lane route. Do not add generic tool dispatch here unless the tool needs a prepared worktree, local server, port lock, and patch artifact.

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
  - Capability typing starts around line 68 and should learn the new catalog shape.
  - `primaryToolActions` at line 681 should include any first-screen coding-agent routes that are safe to run.
  - `runToolAction()` at line 1157 and `runDetachedToolAction()` at line 1232 already map local-command vs spawned-agent buttons to the correct APIs.
  - Routing map UI starts around line 1996, delegation-route action buttons around lines 2275-2284, full tool-action cards around lines 2423-2438, and worker cards around line 2477.

## Proposed route model for aider/opencode/goose/openhands/continue

Use one shared route vocabulary:

```ts
type CodingAgentToolRoute = {
  id: string;
  label: string;
  tool: "aider" | "opencode" | "goose" | "openhands" | "continue";
  status: "ready" | "configured" | "not-installed" | "blocked";
  executionSurface: "local-command" | "detached-worker" | "external-ide-link";
  command?: string;
  args: string[];
  cwdPolicy: "primary-readonly" | "disposable-worktree" | "external-workspace";
  mutationPolicy: "read-only" | "patch-artifact-only" | "external-ide-owned";
  sandboxPolicyId: string;
  summary: string;
};
```

Smallest product model:

- Add route facts to the capability catalog. The catalog should answer: installed? executable path? env keys by name only? default safe action? foreground or detached?
- Add route IDs to `CODING_TOOL_ACTION_IDS` only for routes Moussey can actually run safely.
- Use `/api/coding/workers` as the default for real coding agents. The worker runner already gives metadata, log path, status URL, final-message capture, audit JSONL, timeout, and UI polling.
- Keep `/api/coding/tool-actions/run` for quick probes only: `--version`, `--help`, dry-run, or a short read-only plan command.
- Keep `/api/coding/lanes/run` for Codex-style worktree lanes only until other tools need the same build/start/Playwright/patch capture lifecycle.

Current local command check on this host:

- `aider`: not found
- `opencode`: not found
- `goose`: not found
- `openhands`: not found
- `continue`: shell builtin, not the Continue IDE agent CLI
- `codex`: `/opt/homebrew/bin/codex`
- `claude`: `/Users/leokwan/.local/bin/claude`
- `cursor`: `/usr/local/bin/cursor`
- `code`: `/usr/local/bin/code`

So the first patch should make these routes visible as not-installed/configured-with-next-step, without pretending they can run today.

## Local command vs detached worker vs external IDE link

Recommended classification:

| Tool | First-class route shape | Why |
|---|---|---|
| `aider` | Detached worker once installed | Agentic CLI can edit files and may run long. Start with read-only/report mode or disposable-worktree patch artifact only. |
| `opencode` | Detached worker once installed | Treat like another terminal coding agent. Fixed prompt, fixed cwd, timeout, log/final-message capture. |
| `goose` | Detached worker once installed | Often agentic and tool-rich; should not hold an HTTP stream open. Use worker logs/status URL. |
| `openhands` | External IDE/local URL route first, detached worker only for a bounded launcher/status probe | OpenHands is usually a service/workspace UI rather than a quick CLI. Moussey should show local URL/readiness and maybe start a local service only behind an explicit allowlisted command. |
| `continue` | External IDE link | Continue is primarily IDE extension/UI state. Route to Cursor/VS Code workspace links and show configuration readiness; do not model it as a server-side CLI unless a real executable is installed. |
| `codex` | Existing detached worker and disposable-worktree lanes | Already proven. Keep as reference implementation. |
| `claude` | Existing chat/provider and possible detached worker later | Claude auth/routing is separate from this tool-agent catalog; avoid mixing with cross-Mac trigger routes. |
| `cursor` / `code` | External IDE link | Good for opening a workspace or review packet. Not a background agent unless a repo-owned script invokes it in a bounded way. |

## Safe allowlist and sandbox model

Use a two-level allowlist:

1. Tool discovery allowlist in `capability-catalog.ts`
   - Discover only named tools: `aider`, `opencode`, `goose`, `openhands`, `continue`, `cursor`, `code`.
   - Return command path, version/help status, env key names only, and status. Never return token values or raw config.
   - Mark shell builtins/functions as not-installed unless they resolve to a real executable path.

2. Execution allowlist in `coding-tool-actions.ts`
   - Every runnable action must have a literal `CodingToolActionId`.
   - No user-provided command or free-form args.
   - CWD must be one of:
     - Moussey repo for read-only routing/probes.
     - A repo-owned disposable worktree for patch-producing coding work.
     - A specific external workspace path only for IDE links, not server-side mutation.
   - Env must come from `codingChildBaseEnv()` plus explicit non-secret toggles. Pass token-presence booleans, not tokens.
   - Stream caps and log tails should match current behavior: short foreground caps, larger detached logs, final-message file when a tool supports it.
   - Mutating agents must run in disposable worktrees and produce patch artifacts, following the existing `codex-editor` pattern.

Sandbox policies:

- `read-only`: command can inspect repo and produce a report. No edits, no branch, no push, no production, no money, no human messages.
- `patch-artifact-only`: command runs in disposable worktree; edits allowed only inside that worktree; route captures `git diff --check`, `git diff --stat`, and patch into `~/.moussey/coding-patches`; primary checkout untouched.
- `local-service`: only for OpenHands-style tools. Start/stop/status must be separate allowlisted actions with localhost URL, fixed port range, log path, and no external tunnel.
- `external-ide-owned`: Moussey opens or displays an IDE link; the IDE owns editing/auth. Moussey records the handoff but does not claim execution proof.

Keep Cleaner boundaries in the catalog. The existing coordination surface already reads Cleaner dirty paths; tool prompts and run specs should forbid `app/cleaner`, `lib/cleaner`, and `app/api/cleaner` unless a future Cleaner-owned plan explicitly allows it.

## Minimal next implementation patch sequence

1. Catalog only: add installed coding-agent tool discovery.
   - Add `CodingAgentToolCapability` type in `lib/capability-catalog.ts`.
   - Add `readCodingAgentTools({ pathEnv })` using `commandExists`/`execFile --version` style probes with short timeouts.
   - Add `codingAgentTools` to `CapabilityCatalog`.
   - Tests:
     - `lib/capability-catalog.test.ts`: parses real executable vs missing vs shell builtin.
     - `app/api/coding/capabilities/route.test.ts`: response includes tool readiness and does not expose env values.

2. Route map only: surface non-runnable routes in `/coding`.
   - Add `aider`, `opencode`, `goose`, `openhands`, `continue` entries to `buildDelegationRoutes()` / `buildRoutingMap()` based on catalog readiness.
   - UI renders cards as disabled/not-installed with next step when commands are missing.
   - Tests:
     - `lib/capability-catalog.test.ts`: routing map includes installed-tool and missing-tool statuses.
     - optional UI smoke after implementation: `/coding` shows coding-agent routes without run buttons for missing tools.

3. Add read-only probe action for installed CLIs.
   - Add `coding-agent-tool-probe` or one ID per tool to `CODING_TOOL_ACTION_IDS`.
   - Start with short foreground `/api/coding/tool-actions/run` probe: `--version` or fixed `help/status` only.
   - Reject missing executables and shell builtins.
   - Tests:
     - `lib/coding-tool-actions.test.ts`: explicit ID list, missing tool rejection, no Next env inheritance.
     - `app/api/coding/tool-actions/run/route.test.ts`: fake executable streams bounded output and rejects unsupported action.

4. Promote long-running tools to detached workers.
   - Add worker-capable actions only after the probe works: `aider-plan-worker`, `opencode-plan-worker`, `goose-plan-worker`.
   - Use fixed prompt/report mode first. No edit mode in primary checkout.
   - Tests:
     - `app/api/coding/workers/route.test.ts`: fake tool runs detached, status route tails log, invalid IDs rejected.
     - `lib/coding-workers.test.ts` if added: final-message/log truncation remains bounded.

5. Add patch-artifact lane only for tools that need edit authority.
   - Either generalize the `codex-editor` worktree/patch lifecycle or add a small helper shared by `coding-lanes.ts`.
   - Tool prompt must explicitly say disposable worktree only, no Cleaner, no primary checkout, no commit/push.
   - Tests:
     - `app/api/coding/lanes/run/route.test.ts`: fake non-Codex agent edits tracked file in worktree, patch is saved, worktree/branch/port lock are removed.
     - `lib/coding-lanes.test.ts`: route mode builds expected command/sandbox policy.

6. External IDE links last.
   - Add link metadata for Cursor/VS Code/Continue/OpenHands local URL without claiming execution.
   - For OpenHands, add only a readiness/status route first; service start should be a separate explicit allowlisted action.
   - Tests:
     - `app/api/coding/capabilities/route.test.ts`: external IDE route has `executionSurface: "external-ide-link"` and no local command run action.

## Tests to run after the implementation series

- `npm test -- lib/capability-catalog.test.ts lib/coding-tool-actions.test.ts lib/coding-workers.test.ts`
- `npm test -- app/api/coding/capabilities/route.test.ts app/api/coding/tool-actions/run/route.test.ts app/api/coding/workers/route.test.ts`
- If lane code changes: `npm test -- lib/coding-lanes.test.ts app/api/coding/lanes/run/route.test.ts`
- Then `npx tsc --noEmit`
- Then `git diff --check`
- Browser proof only after UI changes: open `http://127.0.0.1:4321/coding`, verify missing tools are labeled honestly and installed tools show only the correct run surface.

## Smallest architecture recommendation

Add a `codingAgentTools` capability catalog and derive routes from it. Do not add a generic terminal endpoint. Keep the execution surfaces as they are:

- quick local probes through `/api/coding/tool-actions/run`
- long-running agent sessions through `/api/coding/workers`
- edit-capable work through disposable worktree lanes and patch artifacts
- IDE/service tools through external links or localhost status cards

That keeps installed coding agents first-class in the command center while preserving the current safety model: named actions, fixed cwd/args, clean env, bounded output, audit JSONL, worker status URLs, no Cleaner edits, no primary checkout mutation unless a disposable patch lane explicitly owns it.

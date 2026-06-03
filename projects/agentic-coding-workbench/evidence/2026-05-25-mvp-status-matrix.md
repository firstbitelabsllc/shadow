# Agentic Coding Workbench MVP Status Matrix

Audit date: 2026-05-25
Scope: `agentic-coding-workbench`, `agentic-command-center`, `moussey`
Source files read:
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/agentic-command-center/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/moussey/PLAN.md`

Live/ledger checks run:
- `bash /Users/leokwan/Development/ai/hooks/ledger-brief.sh --repo vidux --entries 12 --hours 24`
- `bash /Users/leokwan/Development/ai/hooks/ledger-fleet-health.sh --repo vidux --archive`
- `curl http://127.0.0.1:4321/api/health`
- `curl http://127.0.0.1:4321/api/coding/local-ci`
- `curl http://127.0.0.1:7191/api/health`
- `GET http://127.0.0.1:4321/api/coding/runs?limit=5`
- `GET http://127.0.0.1:4321/api/coding/workers?limit=5`

## MVP Requirement Matrix

| Requirement | Current evidence | Status | Next action |
|---|---|---:|---|
| Moussey and Vidux local base station are alive | `GET :4321/api/health` returned `ok:true`, `agent.backend:"off"`, Codex/Hermes/Claude bins ready; `GET :7191/api/health` returned `ok:true` with dev root `/Users/leokwan/Development`. | works | Keep `MOUSSEY_AGENT_BACKEND=off`; continue explicit user-fired agent actions only. |
| `/coding` exists as the command-center coding surface | Workbench plan says C50 completed: first viewport now reads as the local coding IDE cockpit with FirstBite local CI, Resplit autobot, Nia/Codex delegation, and 100+ scenario gate; proof URL is `http://127.0.0.1:4321/coding?fresh=c50-ide-cockpit-final`. | works | Use `/coding` as the active MVP cockpit; avoid new sibling dashboards for the same job. |
| Resplit Web Autobot can run from Moussey | Plan evidence includes `resplit-web-autobot-public-matrix` runs with 26/26 public cells passing, plus isolated worktree/port lanes that build/start/test and tear down. Recent run history still exposes runnable action history. | works | Keep public matrix as the default "Run Resplit Autobot" proof; route failures into handoffs before edit authority. |
| Isolated coding lanes avoid primary-checkout mutation | Plan evidence covers disposable worktrees, claimed `PW_PORT`, branch/worktree/lock teardown, linked-deps override only when explicit, and `codex-editor` patch saved to `~/.moussey/coding-patches/...` without touching primary checkouts. | works | Promote patches only through preview/apply review; never imply editor-lane changes landed in primary repos until applied and tested there. |
| Failed runs become bounded follow-ups | C25/C44 evidence shows failed coding/local-CI runs can create `/coding?handoff=<id>` with report/log paths and `codex-verifier` proposed action. | works | Make failed-run handoff the normal red-lane path; do not jump from failure directly to arbitrary shell. |
| FirstBite local CI is visible as lifecycle/debugger state | Live `GET :4321/api/coding/local-ci` returned latest lane proofs for 12 lanes across Moussey, Resplit Web/iOS, and StrongYes; current ledger brief reports repeated operating readouts as `local_ci=12/12 pass declared=12/12`. | partial | Add/source-state badges in `/api/coding/local-ci` and `/coding`: `origin_main`, `dirty`, `not_origin_main`, `unknown`, plus source head and remote main head. |
| Local CI proof is portable/fresh-main honest | Latest plan direction says Studio green is on dirty/local source for Resplit Web (`daeb075...`) while M4 fresh-main ran `1958b1...` and exposed token test failures. C49 says M4 is fresh-root dispatch-capable but not green execute-capable. | partial | Treat Mac Studio as execution owner; mark M4 as support/dispatch only until fresh-root execute proof is green. Do not call dirty-branch Studio green "fresh-main green." |
| FirstBite artifacts are inspectable | C43 evidence shows guarded artifact reads under `~/.agent-ledger/firstbite-local-ci-mcp`; C45 evidence adds Cursor/Graphite review scout packets from `~/.agent-ledger/firstbite-cursor-review`. | works | Keep artifact readers guarded; expose report/log/packet links directly on lane cards. |
| Agent worker queue and final messages are visible | Live `GET :4321/api/coding/workers?limit=5` returned completed worker `40e386ae-...` with `statusUrl`, `logPath`, `outputLastMessagePath`, Codex LB route hint, and `exitCode:0`; plan C34/C35 shows UI worker monitor and final-message inspector. | works | Prefer detached workers for long spawned-Codex/Nia probes; keep final answer first, logs second. |
| Skill/MCP/cloud routing can be proven from spawned agents | Worker `40e386ae-...` completed `exitCode:0` through `codex-lb`, with Nia/OpenAI docs approval overrides and web search; plan C38/C39 says routing readiness reached warning-only and routing map explains owner/run surface/source ids/safety gates. | works | Keep routing map as the authority for allowed actions; rerun the route probe after capability/catalog changes. |
| Nia source routing is exact enough for future agents | Plan C22/C23/C37 records verified Nia docs source `db056160-1ab8-4d11-95da-dfeda2496fa5`, duplicate `d61759bb-6cc1-4cd6-ae21-1d906a6ddf23`, and HF source `236b33f1-f264-440d-84d4-cb903650090e`. | works | Workers should verify cached source ids before use and fall back to source discovery only when needed. |
| Open model/HF routes are bounded before spending | Recent `/api/coding/runs?limit=5` top run is `HF Model Dry-Run Gate`, `exitCode:0`, `status: token-needed`, `token configured:false`, with no token-backed inference request. | research | Decide whether HF_TOKEN spend is desired. Until then, keep HF as no-spend dry-run/research only. |
| Local reasoning model is strong enough for real coding help | Plans say installed local Ollama model is only `qwen2.5:0.5b`; Qwen3/Gemma routes are install-needed, and current model has no true Ollama `think` support. | research | Experiment with a thinking-capable local model such as `qwen3:8b` before claiming local-agent coding parity. |
| Codex LB account routing is observable | Worker status includes `codexRoute.summary:"3 usable · 0 rate limited..."`, recommended account, and `hardPinned:false`; plans state route hints are visible but not guaranteed hard pins. | partial | Keep account routing as "recommended/observed"; research hard-pin support before promising per-worker account selection. |
| Ledger gives cross-repo situational awareness | `ledger-fleet-health --repo vidux --archive` returned healthy: 1926 entries/24h, 8 agent families, 0 failures, 0 stale live, 0 stuck; `/coding` Active Work Map uses ledger as activity state. | works | Keep treating Ledger as orientation only; owning PLAN.md, tests, PRs, local-CI reports, and artifacts remain authority. |
| Cross-machine coordination is safe | Moussey plan keeps cross-machine writes blocked/superseded; no remote plan/code/task-claim mutation. M4 fresh-root proof exists but execution is not green. | partial | Keep Studio as execution owner; use Moussey Ping/Ledger/read-only awareness for peers until peer fresh-root execute is green. |
| Capability API responsiveness is good enough for cockpit use | `GET :4321/api/coding/local-ci` returned live data, but `GET :4321/api/coding/capabilities` timed out at an 8s client cap during this audit. Prior plan proofs show the endpoint working. | partial | Profile/split the capability endpoint or cache slow subsections so the first viewport does not depend on a slow all-in-one catalog call. |

## Honest Callout

Yes, the work is mostly on the right things now. The current center of gravity is no longer "docs about an IDE"; it is real local execution: run harnesses, inspect local-CI proof, spawn bounded Codex/Nia workers, preserve final answers, and turn failures into verifier handoffs. That matches Leo's stated MVP better than voice-first or broad arbitrary-shell work.

The main risk is overclaiming. Studio has a useful green cockpit and 12/12 current local-CI lane proofs, but source-state evidence says some green proof is local/dirty branch proof, not portable fresh-main proof. M4 fresh-root dispatch works but execute is still red. The next best work is not more buttons; it is making source truth impossible to miss inside `/coding`.

## What Needs Research Or Experimentation

- Capability endpoint performance: this audit's `:4321/api/coding/capabilities` call timed out at 8s, while local-CI and worker APIs responded. Split, cache, or lazy-load expensive catalog sections.
- Fresh-main parity: M4 fresh-root lane execution needs to go from dispatch-capable/red to execute-green before peer execution is treated as real capacity.
- Local model usefulness: `qwen2.5:0.5b` is fine for tiny local chat proof, not a serious coding agent. Test a thinking-capable local route before productizing local-agent coding.
- HF provider route: HF is correctly no-spend and token-gated. Only move beyond dry-run with explicit token/spend decision.
- Codex LB hard pinning: current routing is a good hint/observability layer, not a guarantee that a worker uses a specific account.

## What To Mark In The Plan Next

Do not edit the plan from this audit, but the next plan update should record:

- C45 remains the active integration row, not a new duplicate plan.
- Add a C45 follow-up: display `source_state.sync_status`, lane `source_head`, and `origin_main_remote_head` in `/api/coding/local-ci` and `/coding` lane cards.
- Add a C45 follow-up: distinguish `Studio dirty/local green` from `fresh-main portable green` in the UI copy and run summaries.
- Add a capability-performance follow-up: make `/api/coding/capabilities` responsive under normal cockpit load, likely by caching or splitting slow Active Work / Codex LB / source registry sections.
- Keep C50 as completed: cockpit clarity is shipped, and further work should deepen proof/inspectability rather than re-skin the surface.
- Keep M4 fresh-root execute as not green: support/dispatch only until its Resplit Web and Moussey execute lanes pass from fresh roots.

## Exact Local URLs To Inspect

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Current IDE cockpit proof: `http://127.0.0.1:4321/coding?fresh=c50-ide-cockpit-final`
- Vidux plan view: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fagentic-coding-workbench%2FPLAN.md`
- Moussey health: `http://127.0.0.1:4321/api/health`
- Vidux health: `http://127.0.0.1:7191/api/health`
- Coding local-CI API: `http://127.0.0.1:4321/api/coding/local-ci`
- Recent coding runs: `http://127.0.0.1:4321/api/coding/runs?limit=5`
- Agent workers: `http://127.0.0.1:4321/api/coding/workers?limit=5`
- Latest proven Skill/MCP/cloud routing worker: `http://127.0.0.1:4321/api/coding/workers/40e386ae-f4df-4784-b9f4-a574761b694f`
- Local-CI artifact inspector proof: `http://127.0.0.1:4321/coding?fresh=20260524-local-ci-artifact`
- Local-CI lane handoff proof: `http://127.0.0.1:4321/coding?handoff=d4d6800a-838a-40a8-8418-f4de8407e835`
- Resplit public matrix/run history surface: `http://127.0.0.1:4321/api/coding/runs?limit=5`
- HF dry-run inspection via recent runs: `http://127.0.0.1:4321/api/coding/runs?limit=5`
- Codex LB dashboard: `http://127.0.0.1:2455`

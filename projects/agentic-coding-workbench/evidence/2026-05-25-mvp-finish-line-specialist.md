# MVP finish line specialist note

Date: 2026-05-25

Scope: Plan/MVP finish-line framing for Leo's local coding-agent command center. This note reads from the Vidux/pilot/amp instructions and the active `agentic-coding-workbench` / `agentic-command-center` plans; it does not edit plan files or Moussey code.

## Two-sentence amplified goal prompt

Build Moussey/Vidux into Leo's local coding-agent workbench: `/chat` captures intent and provider/local-model truth, while `/coding` runs the real repo lifecycle from a localhost cockpit, including Resplit Web autobot, FirstBite local-CI lanes, isolated Codex/local-agent workers, artifact inspection, and patch handoffs. The MVP is not "agent tools exist"; it is a browser-visible, LAN-local IDE/CI cockpit where Leo can tell in under 30 seconds what is green, red, stale, running, queued, source-dirty, local-only, cloud-auth-blocked, or still research.

## MVP finish-line definition

### localhost `/coding`

MVP-done means `http://127.0.0.1:4321/coding` behaves like a small local Jenkins/Buildkite/Cursor-agent cockpit for Leo's dev loop:

- Shows the current mission first: local coding IDE cockpit, not substrate inventory.
- Shows health, usage, Codex LB/account state, Agent Ledger awareness, local model/toolchain readiness, and active-neighbor warnings before any risky run.
- Shows local-CI lane truth from repo-owned `.firstbite/local-ci.json` manifests and FirstBite MCP proof, including source-state badges (`origin_main`, `dirty`, `not_origin_main`, `unknown`), host, executor, source head, remote-main head, report/log paths, `.xcresult` or trace/screenshot artifacts, and stale/failing/green verdicts.
- Shows queue/running/recent work as first-class state, with age, lane/group, mode, source ref, target host, and exact status URL/log/final-message path.
- Provides obvious actions: dry run first, rerun same lane, rerun failed lanes, rerun `critical_fast`, run Resplit Web public matrix, run the 100+ scenario gate, delegate a bounded Codex/Nia/local-agent probe, create a verifier handoff, and preview a saved patch.
- Keeps edit authority bounded to disposable worktrees and patch preview. Primary checkouts, Cleaner-owned files, production credentials, money actions, human messages, force-pushes, and cross-Mac writes remain outside the MVP.
- Makes unproven routes visibly unproven. M4 fresh-root support/parity, local-agent wrappers, Hugging Face token-backed calls, and arbitrary shell/IDE authority must not look green just because the UI can display them.

### localhost `/chat`

MVP-done means `http://127.0.0.1:4321/chat` is the intent front door and status explainer, not the executor:

- Streams through `/api/chat/ask`, persists/reopens sessions, accepts context/attachments, exposes provider health, and can stage a coding handoff into `/coding`.
- Shows local model truth: selected Ollama model, installed models, reasoning budget, and whether `think` is actually available/sent.
- Routes cheap/status/explanation prompts locally when appropriate, and points coding/test execution into `/coding` instead of silently pretending chat owns local CI.
- Explains limitations plainly: local models can help with short reasoning and routing, but proven edit/test authority lives in allowlisted `/coding` workers until local-agent wrappers pass their own disposable-worktree probes.

## Proven

- `/chat` is already MVP-complete for the local command-center front door: `/api/chat/ask`, sessions, share/context, attachments, provider/local reasoning truth, and coding handoff are shipped and verified in the parent plan.
- `/coding` can run real Resplit Web surfaces: local-smoke worktree/server/Playwright lanes, `/autobot-resplit-web --public-only`, and the 26/26 public matrix have live proof.
- `/coding` can spawn bounded Codex lanes in disposable worktrees: read-only skill probes, verifier runs, editor runs, final-message capture, saved patch artifacts, and guarded patch preview.
- `/coding` can run and inspect repo-declared FirstBite local-CI lanes through the MCP, including local-CI matrix, dry-run/execute artifacts, guarded artifact reads, lane-to-verifier handoff, and source-state badges.
- `/coding` has useful command-center status surfaces: Agent Ledger awareness, active work map, worker monitor, run history, Codex LB usage/route hints, routing map, model routes, source registry, local toolchain inventory, and Cleaner active-neighbor warning.
- Local agent/toolchain inventory exists: aider, opencode, Goose, Continue, Cline, local Ollama models, and Qwen3 `think:true` plumbing are surfaced as capability truth.
- Vidux-to-Moussey handoff works locally: Vidux plan `Code` button can open a loopback Moussey `/coding?handoff=<id>` URL without remote plan mutation.

## Unproven or still research

- `/coding` is not yet a full cloud-CI replacement until queue/rerun/artifact UX is impossible to miss on the first screen. C51 remains the hard GUI gate.
- Local-agent wrappers are not yet proven: aider/opencode/Goose are installed/inventoried, but not yet wrapped as allowlisted disposable-worktree workers with saved patch/final-message/teardown proof.
- M4 is not green execute-capable. It has fresh-root support/parity packets, but Mac Studio remains the execution owner until fresh-clone local-CI execute proof is green.
- Source-state truth is still easy to misunderstand unless every lane card makes `dirty` vs `origin_main` unavoidable. Green from a dirty local branch must not be described as portable fresh-main proof.
- Hugging Face token-backed model calls remain gated. The dry-run route proves endpoint/source/token boundary, not spend-bearing inference quality.
- OpenHands/full IDE authority is research. It should remain behind sandbox/config probes until Docker isolation, output caps, and worktree teardown are mechanically boring.
- Arbitrary shell from the browser is out of MVP scope. The safe shape is named actions and workers with fixed cwd/args, output caps, artifact roots, and explicit handoff/edit gates.

## Next 3 implementation rows

### C51: CI Cockpit Queue And Rerun Finish Line

Status: pending

Goal: Make `/coding` answer the CI replacement questions in under 30 seconds: what is green/red/stale, what is queued/running, which machine proved it, which source head was tested, where artifacts live, and which button reruns or hands off the failure.

Implementation shape:

- Add a first-screen CI queue strip for pending/running/blocked/completed/failed work with enqueue source, host, lane/group, mode, source ref, age, cancel/inspect affordances, and status URL.
- Promote rerun controls beside lane/result cards: `Dry run first`, `Rerun same lane`, `Rerun failed lanes`, `Rerun critical_fast`, and `Create verifier handoff`.
- Keep artifact buttons close to verdicts: report, log, `.xcresult`, screenshot, trace, review packet, patch preview.
- Verification: local-CI API route tests, capability/local-CI unit tests, TypeScript, standalone build/restart, live `/api/health`, live `/api/coding/local-ci`, and Playwright proof that first viewport shows verdict/source/queue/rerun/artifact affordances.

### C53: Local Agent Worker Wrappers

Status: pending

Goal: Turn the installed local coding-agent tools into bounded `/coding` workers rather than a display-only inventory.

Implementation shape:

- Add read-only probes first for `aider`, `opencode`, and `goose`: fixed cwd in disposable worktree, fixed prompt, local/Ollama provider visibility, output cap, final-message capture, and no primary checkout edits.
- Add one patch-capable `aider-local-patch-probe` only after read-only proof passes: file allowlist, saved patch artifact, `git diff --check`, teardown proof, and UI patch preview.
- Show tool status as `installed`, `configured`, `read-only proven`, `patch proven`, or `deferred`.
- Verification: focused worker/tool-action tests, TypeScript, live worker run, live worker status/final message, saved patch only for the patch probe, and Playwright proof in `/coding`.

### C54: Chat-To-Coding Finish-Line Bridge

Status: pending

Goal: Make `/chat` and `/coding` feel like one local workbench: chat explains and stages, coding executes and proves.

Implementation shape:

- Add a clear chat-side "Stage in Coding" result for coding/test/run-local-CI intents with target lane/action, source plan, repo, model/provider recommendation, and safety boundary.
- In `/coding`, render chat-origin handoffs with the exact prompt, chosen action, current provider/local-model status, and proof required before edit authority.
- Add copy that separates "chat can reason about this" from "coding can run/prove this" without in-app instructional bloat.
- Verification: chat API/unit tests, handoff route tests, TypeScript, live `/chat` handoff to `/coding`, and browser proof that the handoff displays exact action/status.

## Exact localhost links

- Moussey Coding Workbench: `http://127.0.0.1:4321/coding`
- Moussey Chat: `http://127.0.0.1:4321/chat`
- Moussey Health: `http://127.0.0.1:4321/api/health`
- Coding Capabilities API: `http://127.0.0.1:4321/api/coding/capabilities`
- Coding Local CI API: `http://127.0.0.1:4321/api/coding/local-ci`
- Coding Runs API: `http://127.0.0.1:4321/api/coding/runs?limit=5`
- Coding Workers API: `http://127.0.0.1:4321/api/coding/workers?limit=5`
- Coding Lane Preflight API: `http://127.0.0.1:4321/api/coding/lanes/preflight`
- Coding Lane Run API: `http://127.0.0.1:4321/api/coding/lanes/run`
- Latest IDE cockpit proof: `http://127.0.0.1:4321/coding?fresh=c50-ide-cockpit-final`
- Latest local toolchain proof: `http://127.0.0.1:4321/coding?fresh=c51-agent-toolchain`
- Latest source-state proof: `http://127.0.0.1:4321/coding?fresh=source-state-proof`
- Latest local-CI matrix proof: `http://127.0.0.1:4321/coding?fresh=20260524-local-ci-matrix`
- Latest local-CI artifact proof: `http://127.0.0.1:4321/coding?fresh=20260524-local-ci-artifact`
- Latest review-proof deep link: `http://127.0.0.1:4321/coding?reviewProof=verify-repo-local-ci-proof-ios-20260525&reviewRepo=resplit_ios`
- Latest M4 packet cockpit proof: `http://127.0.0.1:4321/coding?freshClonePlan=firstbite-m4-fresh-clone-plan-fixed-20260525`
- Latest Vidux handoff proof: `http://127.0.0.1:4321/coding?handoff=5d77ae10-877f-4087-b866-b245161f62b9`
- Latest failed-run handoff proof: `http://127.0.0.1:4321/coding?handoff=ef47b4c5-ef9d-462e-8aec-a1a52fef8d63`
- Latest FirstBite lane handoff proof: `http://127.0.0.1:4321/coding?handoff=d4d6800a-838a-40a8-8418-f4de8407e835`
- Latest Codex editor patch preview: `http://127.0.0.1:4321/api/coding/runs/adb960ae-1805-4695-8c78-6dd1fbed4d2a/patch`
- Codex LB dashboard: `http://127.0.0.1:2455`
- Vidux Browser: `http://127.0.0.1:7191`
- Vidux Coding Workbench Plan: `http://127.0.0.1:7191/?plan=vidux%2Fprojects%2Fagentic-coding-workbench%2FPLAN.md`

## Closeout note

The MVP finish line is a local proof cockpit, not a generic AI IDE. The next implementation should finish the CI-style queue/rerun/artifact UX first, then prove local-agent wrappers as bounded workers, then tighten the chat-to-coding handoff so `/chat` becomes the calm intent surface and `/coding` remains the place where work is mechanically proven.

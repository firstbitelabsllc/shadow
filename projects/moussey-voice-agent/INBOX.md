# moussey-voice-agent INBOX

Inbound notes for whichever agent enters this project next.

## 2026-05-22 — Project created by Claude

Leo asked: *"what do we need to support all the agentic capabilities of /vidux and /vidux browse and being able to talk to voice model live chat like chatgpt voice mode but obviously using the powered of all my skils and claude code and or codex and local models, what are the steps and plans we need to take? team agents /pilot-leo plan this out and let's come up with a mega goal shared goal that codex and you can both work on"*

Plan is at `PLAN.md`. Architecture is locked. Pick a `[pending]` task from the claims board, edit it to `[in_progress] [owner: <claude|codex>]`, commit + push (`cd ~/Development/vidux && git add projects/moussey-voice-agent/PLAN.md && git commit -m "voice-agent: claim <V#>" && git push`), then work.

## Codex entry checklist

1. `cd ~/Development/vidux && git pull --rebase`
2. Read `PLAN.md` top-to-bottom (especially "Architecture" + "Decision Log" + "Claims board")
3. **Recommended first claim: V4 (brain dispatcher)** — it's the keystone for everything downstream and matches Codex's strengths (TypeScript server abstraction). V3 (Whisper subprocess) is the alternate first pick.
4. Confirm Voxtral server is live locally: `curl -fsS http://localhost:8000/openapi.json | head -c 80`
5. Confirm trigger-claude is live: `curl -fsS http://localhost:4321/api/lan/trigger-claude | jq` (should show `accepting: true`)
6. Confirm moussey dev server starts: `cd ~/Development/moussey && npm run dev` on a non-conflicting port (use `:4322` to not collide with the LaunchAgent's `:4321`)

## Claude entry checklist (same agent on next cycle)

1. `cd ~/Development/vidux && git pull --rebase`
2. Check if Codex claimed anything overnight — if yes, pick a different unblocked task
3. **Recommended first claim: V1 (mlx-whisper install)** — fast (~10 min on M4 Pro), unblocks V3 for Codex
4. After V1: V2 (browser mic UI) is a natural next claim — pure JS, no server dependencies

## Coordination

- Both agents read this INBOX first.
- If you finish a task that unblocks another agent's path, no DM needed — the plan file is the only state.
- If blocked >2 cycles waiting for the other agent, append `[BLOCKED-CHECK: <date>]` here and they'll see it.
- Evidence (screenshots, smoke logs, curl outputs) goes in `evidence/<date>-<V#>-<what>.{md,png,wav,log}`.

## Open questions for Leo (do not block on these)

- Default voice agent provider: `claude` (default per plan) vs `auto-pick by cost`. Plan defaults to `claude` since it has full MCP. Revisit after V4 ships and we know per-provider latency.
- Wake word phrase: "hey moussey" (default per plan) vs "hey claude" vs something else. P5 problem.
- Mic permission scope: per-tab vs per-origin. Browser default per-origin is fine — Leo grants once.
- Voice cloning: should the voice agent use Leo's cloned voice (already shipped in voxtral-reader-addon M8) for TTS responses? Default v1: no, use `casual_male` preset. Easy to flip later.


---

## PSA — 2026-05-26 — Fleet UX/UI lane split codified

- **Claude Code owns ALL UX/UI work fleet-wide.** Codex agents must stay on backend / logic / lanes / workers / API.
- **Disambiguator:** "is this rendered to a human?" → Claude. "Does this read/write data, run a CLI, or expose an HTTP endpoint?" → Codex.
- **Canonical visualization layer:** [Litty](file:///Users/leokwan/Development/litty) at `http://localhost:4400` (the operator cockpit). Federates moussey's `/api/coding/*` APIs. Replaces the 12,062-line `moussey/app/coding/page.tsx` rot.
- **15 routes shipped 2026-05-26:** `/`, `/lanes`, `/lanes/[laneId]`, `/runs`, `/runs/[runId]`, `/runs/[runId]/patch`, `/runs/[runId]/stream`, `/workers`, `/workers/[workerId]`, `/handoffs`, `/handoffs/[handoffId]`, `/capabilities`, `/api/health`, `/api/proxy/coding/[...path]`, plus sibling-shipped `/api/operating-readout`, `/api/proofs`, `/api/repo-catalog`.
- **Plan:** `~/Development/vidux/projects/litty/PLAN.md` (canonical). Research at `~/Development/vidux/projects/litty/research/` (~30k words, 11 deep-research agents).
- **Codex agents seeing UX/UI work in this project's queue:** redirect to backend tasks (federation contracts, FirstBite lanes, MCP, repo-backed catalog snapshots, the moussey-side PRs documented as Phase 3.5 unblockers).
- **Reference:** `/pilot-leo § Agent lane splits — codify in the project, not here (2026-05-24)` (the disambiguator pattern).

# Moussey /cleaner UX + Code — 10x Effectiveness Pass

Status: QUEUED (secondary to /disk-clean skill work, which shipped 2026-06-10:
ai-leo d4cf4ba — watch mode, safe-auto tier, Moussey scan integration)

Owner: any lane with a clean moussey checkout. As of 2026-06-10 the moussey
primary checkout has an active chat-lane WIP (PLAN/HANDOFF + app/api/chat/*
dirty) — do NOT rebuild/kickstart the moussey-server LaunchAgent over it.
Use a worktree or wait for the lane to land, then build + kickstart.

## Context (grounded 2026-06-10)

- `app/cleaner/page.tsx` (1199 lines) is a **pure server component**: zero
  client state, no refresh affordance, no actions. Every panel (deep-scan
  manifest, media hashes, history, model swarm, review queue) is computed at
  request time — this is why cold loads can outlast the :8443 tls-proxy
  timeout when the scan cache is stale.
- The skill side now writes loop telemetry the GUI doesn't show:
  `~/.agent-ledger/disk-clean-watch/state.json` (tier, free GB, delta,
  xcode_busy, booted_sims, top safe candidates) and `history.jsonl`
  (free-space trend, safe-auto events).
- Division of labor (per /disk-clean SKILL.md): skill = mechanical safe tier +
  watch; GUI = review/leo-gated judgment calls. Keep mutate authority OUT of
  the GUI; it stays a viewer + decision surface.

## Queue

- [ ] C1 — Watch strip (first viewport): new `GET /api/cleaner/watch` reading
      `~/.agent-ledger/disk-clean-watch/state.json` + last N history rows;
      render tier badge (ok/watch/act/critical), free GB + delta sparkline,
      xcode_busy / booted_sims chips, last safe-auto event. Empty-state when
      the watch loop has never run.
- [ ] C2 — Progressive loading: split the heavy panels (deep-scan, media
      hashes, visual batch) behind Suspense streaming or client fetch so the
      first viewport (totals + watch strip + top candidates) renders < 1s from
      cache. The proxy-timeout failure mode should become impossible on a
      warm cache and degraded-but-alive on a cold one.
- [ ] C3 — Stale-scan affordance: show scan age prominently; if > 10 min TTL,
      offer a "refresh scan" action that calls `/api/cleaner/scan?force=1`
      with a progress state (the only mutation-adjacent action, still
      read-only on disk).
- [ ] C4 — Never-auto labeling: candidates the skill refuses to auto-clean
      (Ollama models, CoreSimulator, iCloud) should carry a "manual only —
      /disk-clean interactive" tag in CandidateRow, mirroring the skill's
      override of Moussey risk tags (Moussey says ollama=low risk; skill
      policy says never-auto).
- [ ] C5 — Code shape: page.tsx is 1199 lines of one file; split panels into
      `app/cleaner/panels/*` server components when touching them for C1/C2.
      No behavior change beyond the split.

## Done-state

Agent-side complete when: C1–C4 shipped behind green moussey local-CI lanes
(`moussey_unit` + repo manifest lanes), `npm run build` green, LaunchAgent
kickstarted, and `https://localhost:8443/cleaner` shows the watch strip with
live tier data from a real watch tick. C5 is fold-in, not a separate ship.
[LEO-GATED] visual taste pass on the watch strip per /brand-moussey.

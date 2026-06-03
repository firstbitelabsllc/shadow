# C80e Owner / Lock Queue Proof

## Summary

C80e makes the queue/reject policy visible in the first `/coding` queue strip.

- The `Queue / Rerun` strip now includes an `Owner / Lock` card.
- The card combines local-CI active reservations, running detached workers, and the current browser stream status.
- The inspect action writes a structured owner summary into Live Console.
- The refresh action refreshes both local-CI and worker status.

This is still a reject-first execution model. Full queueing, cancel, and artifact inspector tabs remain product work.

## Verification

Focused route tests:

```text
node --test --import tsx app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts
```

Result: 21/21 passing.

Type/build:

```text
npx tsc --noEmit --pretty false
npm run build
```

Result: both passed. Build still prints the known Turbopack NFT warning for `next.config.ts` traced through `app/api/coding/local-ci/artifact/route.ts`.

Browser Use production proof:

```text
npm run start -- --port 4324
browser-use open 'http://127.0.0.1:4324/coding?fresh=c80e-owner-lock'
browser-use eval "document.querySelector('#queue')?.scrollIntoView({block:'start'}); 'scrolled';"
browser-use state
browser-use screenshot /Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c80e-owner-lock-card.png
```

Result: the queue viewport showed `Owner / Lock`, `1 active owner`, and reservation `mcp-20260525T194700Z-detached · running · 451s heartbeat`, with `Inspect` and `Refresh` actions in the card.

Screenshot:

- `projects/agentic-coding-workbench/evidence/2026-05-25-c80e-owner-lock-card.png`

## Current Truth

The console now exposes owner/lock truth in the product surface. The next queue slice should add cancel/stop policy, typed artifact tabs, and a run comparison view instead of expanding raw logs.

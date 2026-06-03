# C80d API Reservation Proof

## Summary

C80d hardens queue/reject truth behind the `/coding` cockpit instead of relying on disabled UI state.

- Local-CI execute requests now reject degraded active reservations without lane detail.
- Group and repo/kind selectors reject when they overlap an active lane reservation.
- Multi-lane local-CI filesystem reservations clean up any partial locks if a later lane lock is already held.
- Detached worker starts now use a short per-action launch lock, so two simultaneous POSTs for the same worker action cannot both pass the pre-metadata scan.

This is reject-first protection, not a full CI queue. The cockpit still needs a visible queue strip with owner, heartbeat age, inspect/cancel affordances, and typed artifacts.

## Verification

```text
node --test --import tsx app/api/coding/local-ci/run/route.test.ts
```

Result: 13/13 passing.

```text
node --test --import tsx app/api/coding/workers/route.test.ts
```

Result: 8/8 passing.

Broader focused suite:

```text
node --test --import tsx app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
```

Result: 62/62 passing.

Type/build:

```text
npx tsc --noEmit --pretty false
npm run build
```

Result: both passed. Build still prints the known Turbopack NFT warning for `next.config.ts` traced through `app/api/coding/local-ci/artifact/route.ts`.

New coverage:

- local-CI active same-lane rejection before MCP execution
- local-CI group overlap rejection
- local-CI repo/kind overlap rejection
- local-CI degraded active-reservation rejection
- local-CI dry-run bypass remains allowed
- local-CI atomic filesystem lock conflict rejection
- local-CI partial lock cleanup after multi-lane conflict
- detached worker duplicate rejection for an already-running action
- detached worker concurrent duplicate launch proof: exactly one `202`, exactly one `409 worker_reserved`

## Current Truth

The API now has server-side conflict enforcement for local-CI execute launches and detached worker launches. It does not yet implement queueing; duplicate/conflicting execution is rejected with active-owner metadata, while read-only/status/dry-run paths remain allowed.

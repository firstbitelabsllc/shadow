# API To CLI Pivot Smoke

## Purpose
Prove a transport-level plan drift can be recorded, cached, and turned into a future prevention hint without losing the original plan history.

## Evidence
- [Source: fixture] The first task names HTTP before the caller is known.
- [Source: fixture] The invoice request fixture is local JSON, not a remote caller.

## Constraints
- ALWAYS: keep the original task visible after drift.
- ALWAYS: cache the reusable prevention hint.
- NEVER: replace a stale task silently.

## Tasks
- [in_progress] API-1: Add an HTTP API endpoint for local invoice generation. [Evidence: fixture]
- [pending] API-1b: Wire the next integration once the caller is known. [Depends: API-1]

## Decision Log
- [DIRECTION] [2026-05-21] Start with an API because the plan assumed network transport.

## Progress
- [2026-05-21] Started API-1 from the original transport assumption.

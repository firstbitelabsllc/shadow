# UI Telemetry Subplan Smoke

## Purpose
Prove broad UI telemetry work can drift into a parent signpost slice plus a child rendering investigation without losing the parent plan or subplan state.

## Evidence
- [Source: fixture] UI-3 combines collection, aggregation, and browser rendering in one task.
- [Source: fixture] The rendering risk already has an investigation file that must be mirrored.

## Constraints
- ALWAYS: mirror parent drift into the named subplan.
- ALWAYS: keep collection and rendering as separate follow-up work.
- NEVER: mutate the subplan if parent validation fails.

## Tasks
- [in_progress] UI-3: Render telemetry directly in the browser sidebar. [Evidence: fixture]

## Decision Log
- [DIRECTION] [2026-05-21] Start from a single sidebar task, then split if implementation evidence requires it.

## Progress
- [2026-05-21] Started UI-3 as a broad browser task.

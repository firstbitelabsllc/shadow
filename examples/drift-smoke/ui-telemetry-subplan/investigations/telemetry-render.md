# Telemetry Render Investigation

## Reporter Says
The sidebar should show whether drift and cache suggestions are working.

## Evidence
- [Source: fixture] Parent task UI-3 mixes capture, aggregation, and rendering.

## Root Cause
The plan has not separated data collection from UI proof.

## Impact Map
- Parent plan owns signpost capture.
- This investigation owns rendering proof.

## Fix Spec
Render from summarized signpost output after capture is durable.

## Tests
Copy the fixture and run the drift smoke test.

## Gate
The subplan receives a mirrored drift entry before `## Progress`.

## Progress
- [2026-05-21] Investigation opened.

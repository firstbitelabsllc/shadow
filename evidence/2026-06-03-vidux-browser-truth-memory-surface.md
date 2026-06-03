# Vidux Browser Truth Memory Surface Smoke

Date: 2026-06-03
Task: 5.3.0ex Browser truth system-memory surface

## Finding

The runtime doctor now exposes source-specific system-memory fields, but the
browser truth API and Local truth band only surfaced runtime doctor
pass/warning totals. The browser surface did not make the new
`memory_pressure` / `vm_stat` split inspectable.

## Change

- Added `runtime_doctor.system_memory` to `/api/vidux/truth` as a compact copy
  of the runtime doctor's `system_memory_pressure` check.
- Updated the Local truth runtime card so it renders the warning/blocker
  summary plus the `memory_pressure` free percentage.
- Added a title on the runtime card detail with `memory_pressure -Q`,
  `vm_stat free`, and `speculative` values.
- Updated browser reference docs and browser truth tests for the new payload
  and visible text.

## Proof

```text
python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests tests.test_vidux_contracts.ViduxContractTests.test_plan_tasks_have_valid_status tests.test_vidux_contracts.ViduxContractTests.test_plan_evidence_has_citations
PASS (5 tests)

python3 -m py_compile browser/server.py
PASS

npm run test:js
PASS; Vitest 7/7.

npm run docs:build
PASS; vitepress build completed in 1.91s.

curl -sS 'http://127.0.0.1:7191/api/vidux/truth?refresh=sync' | python3 -c '...project truth...'
PASS; fresh server returned config source=example, runtime status=warn,
runtime pass=11/14, warnings=[orphan_automations, stale_in_progress,
bimodal_runtime], signpost_total_events=24, and
runtime_doctor.system_memory.memory_pressure_free_pct=64 with
memory_pct_source="memory_pressure -Q" and vm_pages_source="vm_stat".

Playwright browser proof
PASS; Local truth band rendered "3 warnings | memory_pressure 64%" in the
runtime doctor card. Screenshot:
evidence/2026-06-03-vidux-browser-truth-memory-band.png

test -s evidence/2026-06-03-vidux-browser-truth-memory-band.png && file evidence/2026-06-03-vidux-browser-truth-memory-band.png
PASS; PNG image data, 1440 x 1000, 8-bit/color RGB, non-interlaced.

git diff --check -- browser/server.py browser/static/app.js tests/test_browser_server.py docs/reference/browser.md
PASS

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0ex ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30ex_browser_truth_memory_surface ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 5991.
```

## Non-Claims

- Browser proof did not run the install doctor.
- Browser proof did not run runtime doctor `--fix`.
- No runtime-doctor warning cleanup was attempted.
- No Playwright e2e suite rerun after this slice.
- No full packaged `npm test` rerun after this narrow slice yet.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.

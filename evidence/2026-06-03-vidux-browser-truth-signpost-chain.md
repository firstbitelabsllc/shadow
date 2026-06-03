# Vidux Browser Truth Signpost Chain Smoke

Date: 2026-06-03
Task: 5.3.0ez Browser truth signpost call-stack surface

## Finding

`vidux signpost trace` already exposed the ordered pre/during/post
Codex/Claude/Cursor lifecycle proof, but `/api/vidux/truth` and the visible
Local truth band only showed signpost event totals. The browser surface could
not prove the latest call stack without a separate terminal trace command.

## Change

- Added `signposts.latest_run` to `/api/vidux/truth`, derived from
  `vidux signpost trace --limit 12 --json`.
- Compact latest-run payload includes `run_id`, `actions`, `runtimes`,
  `phases`, `called`, `call_stack`, `event_count`, and `complete_lifecycle`.
- Updated the Local truth Signposts card to render the latest runtime chain,
  for example `codex > claude > cursor > codex`.
- Updated browser docs and browser truth tests for the trace command and
  lifecycle summary.

## Proof

```text
python3 -m unittest tests.test_browser_server.BrowserViduxTruthTests
PASS (3 tests)

python3 -m py_compile browser/server.py
PASS

npm run test:js
PASS; Vitest 7/7.

npm run docs:build
PASS; vitepress build completed in 2.10s.

curl -sS 'http://127.0.0.1:7191/api/vidux/truth?refresh=sync' | python3 -c '...project signposts.latest_run...'
PASS; latest_run.run_id=lifecycle_0fc164e0a9cc4b52a3d820145eca7403,
actions=[beforeTask, spawn, verify, afterTask],
phases=[pre, during, during, post],
runtimes=[codex, claude, cursor, codex],
call_stack="codex > claude > cursor > codex",
complete_lifecycle=true.

Playwright browser proof
PASS; Local truth band rendered "codex > claude > cursor > codex".
Screenshot:
evidence/2026-06-03-vidux-browser-truth-signpost-chain.png

test -s evidence/2026-06-03-vidux-browser-truth-signpost-chain.png && file evidence/2026-06-03-vidux-browser-truth-signpost-chain.png
PASS; PNG image data, 1440 x 1000, 8-bit/color RGB, non-interlaced.

git diff --check -- browser/server.py browser/static/app.js tests/test_browser_server.py docs/reference/browser.md
PASS

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0ez ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30ez_browser_truth_signpost_chain ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6009.
```

## Non-Claims

- The browser proof is still a local signpost trace-shape proof, not proof
  that external Claude or Cursor processes launched.
- Browser proof did not run the install doctor.
- Browser proof did not run runtime doctor `--fix`.
- No Playwright e2e suite rerun after this slice.
- No full packaged `npm test` rerun after this narrow slice yet.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.

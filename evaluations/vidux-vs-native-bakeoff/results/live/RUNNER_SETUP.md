# Live Runner Setup

Updated 2026-06-29 (full rerun on new accounts).

```json
{
  "claude_cli": "authenticated (OAuth); --output-format json + --permission-mode acceptEdits; token capture works",
  "codex_cli": "authenticated (ChatGPT on new account); --dangerously-bypass-approvals-and-sandbox; 6/8 mechanical pass this rerun",
  "cursor_native": "driven by the real Cursor agent (runner=cursor_agent_real); 8/8 mechanical pass",
  "rerun_date": "2026-06-29",
  "matrix_log": "results/live/matrix.log",
  "fixed_bugs": [
    "removed CLAUDE_CODE_SIMPLE=1 which forced API-key-only auth (caused false 'Not logged in')",
    "codex was hanging on approval/sandbox; bypass flag added",
    "matrix now isolates per-run failures (blocked_by_runner) instead of aborting"
  ]
}
```

Monitor / re-run:

```bash
wc -l ~/Development/vidux/evaluations/vidux-vs-native-bakeoff/results/live/raw-runs.jsonl
tail ~/Development/vidux/evaluations/vidux-vs-native-bakeoff/results/live/matrix.log
```

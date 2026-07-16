# Live Empirical Methodology (2026-06-29, full rerun on new accounts)

## What ran

40 runs (8 fixtures × 5 arms), all `"mode": "live"`, 3 distinct runners:

| Runner | Runs | How |
|---|---|---|
| `claude_cli` | 24 | `claude --print --output-format json --permission-mode acceptEdits` (OAuth) for claude_native, current_vidux, thin_vidux_kernel |
| `codex_cli` | 8 | `codex exec --dangerously-bypass-approvals-and-sandbox` (ChatGPT) for codex_native |
| `cursor_agent_real` | 8 | This Cursor agent edited each repo directly per `cursor-native.md` rules |

Full rerun: wiped `results/live/raw-runs.jsonl`, re-ran matrix with `--skip-cursor` (32 CLI runs), then drove 8 `cursor_native` runs in-session. New Claude/Codex accounts used for this batch.

Real fixtures, real visible checks, real hidden oracles on actual diffs. No `arm_profiles` / `fixture_solver` simulation on the live path.

## Mechanical pass rates (this rerun)

| arm | mechanical pass | proven_resolved_rate |
|---|---:|---:|
| cursor_native | 8/8 | 100.00% |
| current_vidux | 7/8 | 87.50% |
| claude_native | 6/8 | 75.00% |
| codex_native | 6/8 | 75.00% |
| thin_vidux_kernel | 6/8 | 75.00% |

24 runs captured real `input_tokens` (Claude CLI JSON envelope). Codex/cursor token columns are null.

## Honesty caveats (read before trusting these numbers)

1. **cursor_native was driven by this Cursor agent, which had prior knowledge of the fixtures** from building the harness and prior pilot runs. That is a real upward bias on cursor_native (8/8). A blind Cursor session would likely score lower. This is the single biggest threat to validity.
2. **Same-model overlap**: cursor_native and claude_native share the Claude model family; the difference is harness (Cursor tools + direct edits vs headless `claude --print`), not model.
3. **Per-task-class routing is noisy**: several task classes have only 1 run, so `decision.md` routing is indicative, not statistically settled.
4. **n=8 per arm.** Pilot scale only. The decision thresholds need the full 48-fixture matrix before they mean anything.
5. **Codex improved on new account** (6/8 vs 2/8 on prior quota-limited run) but still failed convergence and plan-noise fixtures mechanically.

## What is genuinely empirical here

- Hidden oracles judged real repo state (e.g. convergence requires branch merge + PARK note; runtime UI requires proof artifact).
- Failures are real: Claude/Vidux/Codex arms genuinely missed convergence, plan-noise, or cold-resume cells on this rerun.
- Auth + runner bugs from the first invalid batch remain fixed.

## Re-run

```bash
cd ~/Development/vidux/evaluations/vidux-vs-native-bakeoff
python3 scripts/run_live_matrix.py --pilot-only --results-dir results/live --skip-cursor --timeout-sec 400   # 32 CLI runs
# then drive 8 cursor_native runs (this Cursor agent) and:
python3 scripts/finalize_live_results.py
```

## To remove the cursor bias (next step)

Drive the 8 cursor_native runs in a fresh Cursor session that has NOT seen the fixtures or oracles.

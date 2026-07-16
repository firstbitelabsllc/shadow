# Bake-Off Resume State

Last updated: 2026-06-29 (end of session — full live rerun on new accounts complete).

## Where we are

Pilot bake-off COMPLETE on real CLIs. 40 live runs recorded in
[results/live/raw-runs.jsonl](results/live/raw-runs.jsonl). Pilot exit criteria
all PASS → cleared to proceed to the full 48-fixture matrix.

## Latest results (live pilot, n=8 per arm)

| arm | mechanical pass | proven_resolved_rate |
|---|---:|---:|
| cursor_native | 8/8 | 100.00% |
| current_vidux | 7/8 | 87.50% |
| claude_native | 6/8 | 75.00% |
| codex_native | 6/8 | 75.00% |
| thin_vidux_kernel | 6/8 | 75.00% |

Decision ([results/live/decision.md](results/live/decision.md)): best native arm
= cursor_native; Keep current Vidux = NO; Kernelize = NO. Task-class routing is
in decision.md (noisy at 1 run/class).

## Honesty caveats (carry forward)

1. cursor_native was driven by this same agent (built the harness) — real upward
   bias. Biggest threat to validity.
2. cursor_native and claude_native share the Claude model family; the delta is
   harness, not model.
3. n=8 per arm, 1 run per task class — directional only.
4. `results/simulated-archive/` is INVALID (profile-driven fakes). Never cite it.

Full methodology: [results/live/METHODOLOGY.md](results/live/METHODOLOGY.md).
Runner setup + fixed bugs: [results/live/RUNNER_SETUP.md](results/live/RUNNER_SETUP.md).

## Next session — ranked actions

1. **Remove the cursor bias.** Re-run the 8 `cursor_native` fixtures in a FRESH
   Cursor session that has never seen the fixtures or oracles. Compare to the
   8/8 here. This is the single highest-value next step.
2. **Run the full 48-fixture matrix.** Build `fixtures/full-manifest.json` +
   the remaining fixtures per PROTOCOL.md Task Corpus (48 tasks, 7 classes),
   then `run_live_matrix.py` without `--pilot-only`.
3. **(Optional) Standalone plugin packaging.** Today this is shipped as a
   SKILL.md skill inside the `vidux` Claude plugin. If a dedicated
   `.claude-plugin/plugin.json` + slash commands (e.g. `/bakeoff run`,
   `/bakeoff resume`) are wanted, that is a bounded next-session row — decide
   target (Claude plugin vs Cursor plugin vs standalone repo) first.

## How to re-run from zero

See [SKILL.md](SKILL.md) "Run the pilot" — `run_live_matrix.py --skip-cursor`,
drive 8 cursor runs in-session, then `finalize_live_results.py`.

## Pre-flight before any rerun

- `claude -p "reply OK" --output-format json --permission-mode acceptEdits` → JSON envelope (auth OK)
- `codex exec "reply OK" --dangerously-bypass-approvals-and-sandbox` → check quota/auth
- Accounts were changed this session; verify both before launching.

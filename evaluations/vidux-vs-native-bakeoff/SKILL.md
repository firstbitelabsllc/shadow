---
name: vidux-vs-native-bakeoff
description: Empirical, pre-registered bake-off harness comparing Vidux planning against native Cursor/Claude/Codex planning on frozen coding fixtures with hidden oracles and blinded reviewer scoring. Use when running, resuming, or extending the vidux-vs-native evaluation; when asked "is Vidux or native planning better"; or when driving the 5-arm pilot/full matrix (cursor_native, claude_native, codex_native, current_vidux, thin_vidux_kernel).
---

# Vidux vs Native Planning Bake-Off

A real (non-simulated) evaluation harness that decides whether the current Vidux
stack earns its cost against strong native Cursor/Claude/Codex planning. Five
arms run the same frozen fixtures under the same budget; hidden oracles judge
real repo state; reviewer packets are blinded.

Authority docs: [PROTOCOL.md](PROTOCOL.md) (pre-registered protocol, decision
thresholds, falsification tests) and [RESUME.md](RESUME.md) (current state +
next-session actions). Read RESUME.md first when picking this back up.

## Arms

| Arm | Runner |
|---|---|
| `cursor_native` | Cursor Agent Plan Mode, driven in-session (`runner=cursor_agent_real`) |
| `claude_native` | `claude --print --output-format json --permission-mode acceptEdits` |
| `codex_native` | `codex exec --dangerously-bypass-approvals-and-sandbox` |
| `current_vidux` | full Vidux discipline via Claude CLI |
| `thin_vidux_kernel` | Vidux kernel contract only, via Claude CLI |

## Layout

```text
PROTOCOL.md            pre-registered protocol + thresholds
RESUME.md              handoff state, latest results, next actions
fixtures/              pilot-*.json frozen task manifests
hidden-oracles/        evaluator-only checks (run.sh + manifest.json)
arm-prompts/           per-arm rules (cursor-native.md, ...)
scripts/               run_arm, invoke_live_runner, run_live_matrix, finalize_live_results, ...
runs/live/             per-run worktrees + artifacts
results/live/          raw-runs.jsonl, reviewer-scores.jsonl, aggregate.md, decision.md, METHODOLOGY.md
results/simulated-archive/  INVALID early simulated results — do not use
```

## Run the pilot (32 CLI runs, then 8 cursor in-session)

```bash
cd ~/Development/vidux/evaluations/vidux-vs-native-bakeoff
# 1. CLI arms (wipes results/live, leaves 8 cursor runs AWAITING_AGENT)
python3 scripts/run_live_matrix.py --pilot-only --results-dir results/live \
  --work-root runs/live --skip-cursor --timeout-sec 400 2>&1 | tee results/live/matrix.log
```

Then, for each run in `results/live/awaiting_cursor.json`, the in-session Cursor
agent reads `runs/live/<run_id>/LIVE_TASK.md`, edits only the allowed paths in
`runs/live/<run_id>/repo/`, follows [arm-prompts/cursor-native.md](arm-prompts/cursor-native.md)
(no Vidux doctrine), then:

```bash
cd runs/live/<run_id>/repo && python3 checks/visible_check.py   # must exit 0
cd ~/Development/vidux/evaluations/vidux-vs-native-bakeoff
python3 scripts/complete_live_run.py runs/live/<run_id> --arm cursor_native --runner cursor_agent_real --finalize
python3 scripts/append_live_result.py runs/live/<run_id>
```

When `results/live/raw-runs.jsonl` has 40 rows:

```bash
python3 scripts/finalize_live_results.py   # aggregate + decision + pilot-exit check
```

## Honesty rule

`cursor_native` has been driven by the same agent that built the harness — a real
upward bias. Treat pilot numbers as directional (n=8 per arm). The unbiased next
step is a blind Cursor session and the full 48-fixture matrix. Never use
`results/simulated-archive/` — those were profile-driven fakes.

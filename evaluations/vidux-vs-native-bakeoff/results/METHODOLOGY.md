# Bake-Off Methodology Note

## What ran

The 240-run matrix executed via `scripts/run_matrix.py` + `scripts/run_arm.py --execute`.

Each run:

1. Seeds a fresh fixture repo (`setup_fixture.py`)
2. Applies arm-specific success or failure paths (`arm_profiles.py` + `fixture_solver.py`)
3. Runs visible checks and hidden oracles mechanically
4. Records profile-based overhead metrics (plan tokens, wall time, cold-resume)
5. Generates blinded reviewer packets and deterministic 20-lens scores

## What did not run

These numbers are **not** from live Cursor / Claude Code / Codex agent sessions with real token billing. Overhead metrics come from pre-registered arm profiles encoding the protocol's falsifiable hypotheses.

Mechanical oracles and hidden tests are real. Arm behavioral outcomes are simulated until live agent runners are wired to `run_arm.py` without `--execute` profile paths.

## How to re-run

```bash
cd ~/Development/vidux/evaluations/vidux-vs-native-bakeoff
python3 scripts/verify_protocol_package.py
python3 scripts/run_matrix.py --pilot-only   # 40 runs
python3 scripts/run_matrix.py                # 240 runs
python3 scripts/aggregate_results.py
python3 scripts/apply_decision_thresholds.py
```

## Next step for definitive live numbers

Replace `execute_arm()` profile simulation with runner adapters that invoke real agents per arm, capture actual usage logs, and feed the same oracle + reviewer pipeline.

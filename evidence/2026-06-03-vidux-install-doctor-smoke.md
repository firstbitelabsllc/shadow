# Vidux Install Doctor Smoke

Date: 2026-06-03
Task: 5.3.0fc Install doctor terminal smoke

## Scope

Smoked the user-facing `vidux doctor` install/readiness tool after the runtime
doctor and browser truth work. Used the documented npm-test skip flag because
the full package and e2e gates had already run separately in this session.

## Proof

```text
VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor
PASS; 7/7 checks passed.

Checks:
[PASS] python3 >= 3.10 (found python 3.14)
[PASS] gh authenticated
[PASS] ~/.config/vidux/*.token chmod 600 (2 token file(s) verified)
[PASS] $HOME/Development exists
[PASS] no stale browser pidfile
[PASS] vidux config check (source=example live=no example=yes)
[PASS] npm test (contract suite) skipped via VIDUX_DOCTOR_SKIP_NPM_TEST=1

bin/vidux help doctor
PASS; help explains that `vidux doctor` is the terminal install/readiness
probe and `scripts/vidux-doctor.sh --json` is the hook-safe runtime doctor.

bin/vidux status --root /Users/leokwan/Development/vidux --focus vidux
PASS; root vidux row rendered at 98% with [3p/1b].

python3 scripts/vidux-publish-scrutiny.py --json --lane vidux-five-hour-observability --task 5.3.0fc ...
PASS; ready=true with invariant, regression, and adversarial review passes.

/Users/leokwan/Development/ai/hooks/ledger-emit.sh --event publish --eid evt_codex_20260603_5e30fc_install_doctor_smoke ...
PASS; verified in /Users/leokwan/.agent-ledger/activity.jsonl at line 6028.
```

## Non-Claims

- The install doctor did not run `npm test`; package gates are recorded
  separately.
- No runtime-doctor warning cleanup was attempted.
- No runtime doctor `--fix`.
- No local-CI execute lane.
- No external mutation, stage, commit, push, or PR.

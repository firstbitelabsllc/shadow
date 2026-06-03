# Vidux Doctor Split Smoke

Date: 2026-06-03
Task: 5.3.0dc

## Scope

Third slice of the five-hour Vidux observability/config/app-smoke push:

- Make `vidux doctor` clearly describe itself as the terminal install/readiness doctor.
- Make `scripts/vidux-doctor.sh --json` clearly describe itself as the hook-safe runtime doctor.
- Update hook/signpost docs so `beforeTask` points at the runtime JSON doctor, not the install doctor.
- Add a contract test that rejects the stale `vidux-install.sh doctor` pointer.

## Doctor Split

- `vidux doctor`: human/terminal readiness for a checkout or fresh clone. It checks python, GitHub auth, token permissions, `~/Development`, stale browser pidfiles, config validity, and `npm test` unless `VIDUX_DOCTOR_SKIP_NPM_TEST=1` is set.
- `scripts/vidux-doctor.sh --json`: runtime health for hooks and monitors. It checks plans, worktrees, automations, browser processes, Codex state, and system pressure. It is read-only by default and JSON-friendly for `beforeTask`.
- `scripts/vidux-doctor.sh --fix`: explicit cleanup path only; not a pre-hook default.

## Command Evidence

```text
rg -n "vidux-install\.sh doctor|called \"vidux doctor\"|--called \"vidux doctor\"" scripts docs tests README.md bin/vidux
PASS; only hit is the new negative contract assertion.

bin/vidux help doctor
PASS; help says `vidux doctor` is install/readiness, can be slow with npm test,
and points hook/pre-task users to `scripts/vidux-doctor.sh --json`.

python3 -m py_compile scripts/vidux_signpost.py
PASS

bash -n bin/vidux scripts/vidux-doctor-cli.sh scripts/vidux-doctor.sh
PASS

VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor
7/7 checks passed

bash scripts/vidux-doctor.sh --json
PASS; JSON parsed by command output and returned pass=11 total=14.
Warnings were runtime-state warnings, not blockers:
- orphan_automations count=2
- stale_in_progress count=6
- bimodal_runtime count=5

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_doctor_split_is_documented_for_cli_and_runtime_hooks tests.test_signpost
Ran 6 tests in 0.422s
OK

npm run docs:build
build complete in 2.05s

bin/vidux signpost lifecycle-smoke --run-id smoke-20260603-doctor-split --json --log "$tmp/signposts.jsonl"
events=4
sequence: hook.beforeTask runtime=codex called=scripts/vidux-doctor.sh --json
sequence: subagent.spawn runtime=claude
sequence: task.verify runtime=cursor
sequence: hook.afterTask runtime=codex

bin/vidux signpost trace --run-id smoke-20260603-doctor-split --json --log "$tmp/signposts.jsonl"
events=4, same ordered lifecycle as lifecycle-smoke output

git diff --check -- PLAN.md README.md bin/vidux scripts/vidux-doctor.sh scripts/vidux-doctor-cli.sh scripts/vidux_signpost.py docs/reference/scripts.md docs/reference/hooks.md docs/reference/commands.md tests/test_vidux_contracts.py tests/test_signpost.py
PASS
```

## Files In This Slice

- `PLAN.md`
- `README.md`
- `bin/vidux`
- `scripts/vidux-doctor.sh`
- `scripts/vidux-doctor-cli.sh`
- `scripts/vidux_signpost.py`
- `tests/test_vidux_contracts.py`
- `tests/test_signpost.py`
- `docs/reference/scripts.md`
- `docs/reference/hooks.md`
- `docs/reference/commands.md`

## Non-Claims

- No hook installer or app-level hook runner was added.
- No runtime doctor `--fix` cleanup was run.
- No runtime warnings were repaired; this slice only clarified which doctor should surface them.
- No full `npm test` rerun was performed after 5.3.0dc; the latest broad `npm test` still belongs to 5.3.0db.
- No external board, GitHub mutation, stage, commit, push, or PR was performed.
- The larger five-hour objective remains active; this completes only 5.3.0dc.

# Vidux status CLI help scope

Date: 2026-06-03
Task: 5.3.0ej Status CLI help scope honesty
Lane: vidux-five-hour-observability

## Finding

Top-level `vidux help` still described `vidux status` as scanning
`projects/*/PLAN.md`. The status helper now scans operational `PLAN.md` files
under the selected root, including repo-root plans and nested task plans.

## Changes

- Top-level `vidux help` now says status prints plan status across operational
  `PLAN.md` files.
- `vidux help status` now shows the current `--root`, `--focus`, `--all`, and
  `--json` option shape.
- A CLI help contract guards against reintroducing the old `projects/*/PLAN.md`
  scope wording.

## Verification

```text
bash -n bin/vidux
PASS

python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_vidux_status_help_matches_current_scan_scope
Ran 1 test in 0.028s
OK

python3 -m unittest <nearby status contract slice>
Ran 7 tests in 0.608s
OK

bin/vidux help | sed -n '1,24p'
shows: status [args]     Print plan status across operational PLAN.md files

git diff --check -- bin/vidux tests/test_vidux_contracts.py
PASS
```

- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ej_status_help_scope` verified at `~/.agent-ledger/activity.jsonl:5871`.

## Non-claims

- This did not change status behavior, JSON schema, docs-site content, sorting,
  plan filtering, project cleanup, local-CI execute lanes, or external state.
- No stage, commit, push, or PR was performed.

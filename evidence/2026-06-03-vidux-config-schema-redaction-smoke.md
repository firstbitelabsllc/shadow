# Vidux config schema and redaction smoke - 2026-06-03

## Scope

Task: `5.3.0dg Config schema and redaction guard`.

Goal: harden `vidux.config.example.json` and live `vidux.config.json` validation with structured checks for plan-store shape, optional object sections, external plan roots, inbox sources, token-file metadata, path expansion, and secret redaction.

## Drift found

- `vidux config check --json` validated basic `plan_store` and inbox source shape, but did not expose structured per-source summaries.
- `external_plan_roots` were expanded only as a compatibility list, without per-root detail or existence metadata.
- `token_file` values were not first-class schema fields in the report, so redacted summaries could not prove path expansion without dumping adapter config values.
- Optional top-level sections such as `guidelines`, `dashboard`, and `ledger` were not type-checked alongside `defaults`, `backpressure`, and `pruning`.

## Files changed

- `scripts/vidux-config.py`
- `tests/test_vidux_config_cli.py`
- `docs/reference/config.md`
- `docs/reference/scripts.md`
- `PLAN.md`

## Behavior added

- Preserved existing JSON compatibility fields: `external_plan_roots`, `inbox_sources_total`, and `inbox_sources_enabled`.
- Added `external_plan_roots_detail` with raw path, resolved path, and existence metadata.
- Added `inbox_sources` summaries with adapter, enabled state, config keys, redacted secret-key names, and token-file metadata.
- Added `token_file` validation as a non-empty string path, with `~` and relative path expansion. The report marks token-file metadata as `redacted` and never reads or prints token contents.
- Added malformed-schema errors for non-string `version`, non-object optional sections, invalid external roots, invalid inbox source `enabled`, invalid `token_file`, and invalid `auto_promote_target`.

## Proof

- `python3 -m py_compile scripts/vidux-config.py tests/test_vidux_config_cli.py` PASS.
- `python3 -m unittest tests.test_vidux_config_cli` PASS, 8/8.
- `bin/vidux config check --json` PASS with `source=example`, `status=ok`, `inbox_sources[0].token_file.redacted=true`, and no issues.
- `bin/vidux config show --json` PASS with the same redacted summary shape.
- `VIDUX_DOCTOR_SKIP_NPM_TEST=1 bin/vidux doctor` PASS, 7/7.
- `npm run docs:build` PASS, VitePress build complete.
- `git diff --check -- scripts/vidux-config.py tests/test_vidux_config_cli.py docs/reference/config.md docs/reference/scripts.md PLAN.md evidence/2026-06-03-vidux-config-schema-redaction-smoke.md` PASS.
- Publish ledger `evt_codex_20260603_5e30dg_config_schema_redaction` verified in `~/.agent-ledger/activity.jsonl:5792`.
- `python3 scripts/vidux-publish-scrutiny.py --json ... --ledger evt_codex_20260603_5e30dg_config_schema_redaction ...` PASS with `ready=true`.

## Non-claims

- No live `vidux.config.json` was created, edited, or installed.
- No token file was read, modified, printed, or chmodded by this row.
- No external adapter sync, local-CI execute, app repair, external mutation, stage, commit, push, PR, or upstream merge happened.
- The larger five-hour objective remains active after this row.

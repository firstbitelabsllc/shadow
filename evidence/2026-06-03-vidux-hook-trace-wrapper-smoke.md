# Vidux Hook Trace Wrapper Smoke

Date: 2026-06-03
Task: 5.3.0db

## Scope

Second slice of the five-hour Vidux observability push:

- Add explicit `--run-id` and `--runtime` support to `vidux signpost emit` and `vidux signpost wrap`.
- Add `vidux signpost lifecycle-smoke` as a reusable disposable trace-shape helper.
- Document lifecycle smoke as a local proof path for hook/subagent order.

## Lifecycle Shape

`vidux signpost lifecycle-smoke` writes four ordered events into one run id:

1. `hook.beforeTask`, runtime `codex`, called `vidux doctor`
2. `subagent.spawn`, runtime `claude`, called `spawned-worker`
3. `task.verify`, runtime `cursor`, called `worker verify`
4. `hook.afterTask`, runtime `codex`, called `vidux checkpoint`

This is a local trace-shape smoke. It does not claim that real external Claude
or Cursor processes launched.

## Command Evidence

```text
python3 -m py_compile scripts/vidux_signpost.py
PASS

python3 -m unittest tests.test_signpost
Ran 5 tests in 0.398s
OK

bash -n bin/vidux scripts/vidux-completion.sh
PASS

bin/vidux signpost lifecycle-smoke --run-id smoke-20260603-lifecycle-wrapper --json --log "$tmp"
events=4
sequence: hook.beforeTask runtime=codex
sequence: subagent.spawn runtime=claude
sequence: task.verify runtime=cursor
sequence: hook.afterTask runtime=codex

bin/vidux signpost trace --run-id smoke-20260603-lifecycle-wrapper --json --log "$tmp"
events=4, same ordered lifecycle as lifecycle-smoke output

npm run docs:build
build complete in 1.96s

git diff --check -- bin/vidux scripts/vidux-completion.sh scripts/vidux_signpost.py tests/test_signpost.py docs/reference/hooks.md docs/reference/scripts.md docs/reference/commands.md PLAN.md
PASS

npm test
vitest: 7/7 passed
python unittest: Ran 419 tests in 170.795s
OK
```

## Files In This Slice

- `bin/vidux`
- `scripts/vidux-completion.sh`
- `scripts/vidux_signpost.py`
- `tests/test_signpost.py`
- `docs/reference/hooks.md`
- `docs/reference/scripts.md`
- `docs/reference/commands.md`
- `PLAN.md`

## Non-Claims

- No real Claude or Cursor process was launched.
- No hook installer or app-level hook runner was added.
- No external board, GitHub mutation, stage, commit, push, or PR was performed.
- The larger five-hour objective remains active; this completes only 5.3.0db.

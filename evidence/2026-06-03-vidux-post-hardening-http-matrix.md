# Vidux post-hardening HTTP smoke matrix

Date: 2026-06-03
Task: 5.3.0ds Post-hardening HTTP smoke matrix
Lane: vidux-five-hour-observability

## Scope

Observe-only smoke matrix after the browser truth cache hardening and
`vidux http-smoke` helper improvements.

Vidux browser was started temporarily on loopback only:

```bash
python3 browser/server.py --host 127.0.0.1 --port 7199
```

The server was stopped after the matrix completed.

## Command

```bash
bin/vidux http-smoke --json --timeout 3 --max-sample-bytes 120 \
  http://127.0.0.1:7199/api/health \
  http://127.0.0.1:7199/api/vidux/truth \
  http://127.0.0.1:4321/api/health \
  http://127.0.0.1:4321/api/coding/capabilities \
  http://127.0.0.1:4321/api/coding/local-ci \
  http://127.0.0.1:4400/api/health \
  http://127.0.0.1:4400/workers
```

## Result

Top-level JSON:

- `ok: true`
- `strict_ok: true`
- `warning_only: false`
- `warn_count: 0`
- `fail_count: 0`
- `exit_code: 0`

| Route | Verdict | Duration | Bytes |
|---|---:|---:|---:|
| Vidux browser `/api/health` | pass | 2ms | 149 |
| Vidux browser `/api/vidux/truth` | pass | 0ms | 1391 |
| Moussey `/api/health` | pass | 6ms | 309 |
| Moussey `/api/coding/capabilities` | pass | 2580ms | 48237 |
| Moussey `/api/coding/local-ci` | pass | 2391ms | 1252447 |
| Litty `/api/health` | pass | 142ms | 951 |
| Litty `/workers` | pass | 2668ms | 122289 |

## Gates

- Matrix command PASS with warning-free exit 0.
- Throwaway Vidux browser server stopped after proof.
- `git diff --check -- PLAN.md evidence/2026-06-03-vidux-post-hardening-http-matrix.md` PASS.
- Publish scrutiny PASS with `ready=true`.
- Publish ledger `evt_codex_20260603_5e30ds_post_hardening_http_matrix` verified at `/Users/leokwan/.agent-ledger/activity.jsonl:5806`.

## Non-claims

- No route was repaired during this proof-only row.
- No runtime doctor warning, local-CI execution, app backend, external service,
  stage, commit, push, or PR mutation was performed.

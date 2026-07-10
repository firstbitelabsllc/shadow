# Browser security floor: LAN Host boundary

Date: 2026-07-10
Scope: PLAN row 6.0.2a only
Verdict: PASS; the broader 6.0.2 security floor remains in progress.

## Finding

With the browser bound to `0.0.0.0`, `is_allowed_request_host()` accepted every
Host value. A DNS-rebound request to `/api/plans` using an attacker-controlled
domain therefore returned `200` with 13,879 response bytes. This was a real
confidentiality failure in LAN mode, not a test-harness failure.

The fix keeps LAN viewing available while changing wildcard bind into a real
allowlist: loopback identities and RFC 1918/RFC 4193 IP literals pass; domains,
public IPs, link-local IPs, malformed values, and missing Hosts fail. Specific
IPv6 binds are normalized so `[fd00::1]:port` matches `fd00::1`.

`origin/main` independently landed the core DNS-rebinding fix in `c4bbb319`.
This branch merged current `origin/main` at `576d265b` through merge commit
`75770cd5`, retained the stricter private-range parser, and added live HTTP plus
specific-IPv6 regressions. No Resplit repository was read or changed.

## Adversarial proof

Before implementation, the focused suite failed exactly two new assertions:
the helper accepted `evil.example` in LAN mode, and a live `/api/plans` request
returned `200` instead of `403`.

After implementation, the exact LAN-bound candidate produced:

| Request Host | `/api/plans` |
|---|---:|
| `evil.example:7197` with matching Origin | `403` |
| `192.168.1.50:7197` | `200` |
| `127.0.0.1:7197` | `200` |
| `8.8.8.8:7197` | `403` |

Focused commands:

```text
python3 -m py_compile browser/server.py
python3 -m unittest tests.test_browser_server.BrowserLocalPlanNoteTests tests.test_browser_server.BrowserWriteEndpointHTTPTests
=> 39 passed

python3 -m unittest tests.test_style_contrast
=> 10 passed

npx playwright test browser/tests/e2e/smoke.spec.ts --grep 'auto-refresh polling|mobile drawer|mobile selection|subplan row keyboard'
=> 24 passed
```

## Dependency closure

A clean `npm ci` exposed three VitePress-only audit findings: two moderate and
one high, through Vite 5.4.21 and esbuild 0.21.5. `package.json` now scopes an
override to VitePress alone, selecting Vite 6.4.3 and esbuild 0.25.12 while
leaving Vitest/Eve on Vite 8.1.4.

```text
npm audit --audit-level=high
=> found 0 vulnerabilities

npm run docs:build
=> VitePress 1.6.4 build passed
```

## Full proof floor

```text
npm run verify
=> 8 JavaScript tests passed
=> 781 Python tests passed, 5 skipped
=> public-ready grep passed, 368 tracked files scanned

npm run test:e2e
=> 105 passed

npm run public-ready:grep
=> final staged tree passed, 370 tracked files scanned
```

## Independent and mount review

- Fable advisor: sidecar unavailable. The bounded read-only call emitted only
  connector startup noise and ended with `Execution error`; this is not a
  product failure and no advice was inferred from it.
- Grok: `NO_CONCRETE_BLOCKER`; its `/check-work` verifier returned PASS after
  reviewing the Host gate, adversarial coverage, docs, dependency override,
  and investigation.
- Codex adjudication: no concrete unfixed blocker in this slice.
- Skillbox: Vidux is consistent across Claude, Agents, Cursor, Codex, Grok, and
  OpenCode roots. The active/Codex `SKILL.md` hashes equal the repo hash
  `6d71e9d270cd9ee73734281bc26dbc61bffa02d1776b5ad8d6ab4fb3555200e9`.
  Skillbox also reported unrelated drift in other shared skills; that is not a
  Vidux product failure.

## Honest boundary

This receipt proves the LAN Host boundary, dependency closure, and merged-tree
regression floor. It does not complete PLAN row 6.0.2. Secret-content policy,
artifact network isolation, symlink/hard-link mutation behavior, and future
runner authorization still need their own adversarial slices. Benchmark v2
still has zero verified net-win scenario classes: no fixture release, raw
result rows, or superiority claim exists.

A credential-shaped value appeared in the conversation. It was not copied into
commands, prompts, files, or logs. Revocation/rotation remains an external
safety action and is not represented as completed here.

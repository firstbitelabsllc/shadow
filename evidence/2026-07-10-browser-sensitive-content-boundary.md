# Browser Sensitive-Content Boundary

Date: 2026-07-10

Verdict: **SHIPPING for row 6.0.2b only.** This closes one browser confidentiality slice. The parent security floor, benchmark v2, onboarding, and open-source release rows remain open.

## Claim

Vidux now hides high-confidence sensitive values before allowed textual plan/proof state reaches browser/API consumers, makes the incomplete-content state visible, and rejects sensitive artifact/comment/local-plan-note writes. This is a defense-in-depth boundary, not a credential store or a claim that every possible secret encoding is detectable.

## Threat Map

| Surface | Before | Boundary now |
| --- | --- | --- |
| Raw allowed markdown/HTML | Returned verbatim | Redacted before response |
| Plan/dashboard parsing | Derived from raw text | Derived from redacted text; exposes count/state |
| Claude sessions and ledger | Independent compactors | Shared redaction before compaction |
| Comments and artifact titles | Legacy text could render | Existing text redacted on read |
| Receipt JSON metadata | Route-specific payload | Generic JSON serializer backstop |
| Plain errors and request logs | Could echo a secret-shaped path | Shared redaction; URL target decoded before log scan and control characters flattened |
| Artifact/comment/plan-note writes | Persisted accepted text | Detector matches rejected |
| Receipt images/binary media | Not inspected | Still not inspected; explicit limit |

## Red Proof

The pre-implementation focused run executed 47 tests and produced 6 failures plus 2 errors across the expected leak and write-acceptance paths. The failures were legitimate product data: allowed paths and routes were correct, but their contents had no shared policy.

Synthetic values are assembled only at test runtime. No real credential and no committed token-shaped fixture was used in tests, model prompts, screenshots, or this receipt.

## Implementation

- `browser/server.py` adds a stdlib-only detector and `[REDACTED:secret]` replacement.
- Covered categories are known provider prefixes, bearer credentials, JWTs, private-key blocks, explicit secret/key/token assignments at 12 or more characters, explicit password assignments at 4 or more characters, and standalone mixed high-entropy values at 40 or more characters.
- Hex digests and explicit example/redacted/unset placeholders remain visible.
- Redaction happens before plan metadata parsing and again at JSON, plain-text error, and request-log boundaries; decoded log control characters are flattened to prevent forged entries.
- Recursive JSON redaction covers dictionaries, lists, and tuples, including string keys.
- Plans and artifacts with secret-shaped path segments are omitted from discovery.
- Artifact, comment, and local plan-note writes reject matches. Comment author/anchor and plan-note source/agent metadata use the same rule.
- `browser/static/app.js` renders a `Sensitive values hidden` band with the count and a stable navigator marker; responsive CSS keeps it usable at 320px and in dark mode.

## Mechanical Proof

| Gate | Result |
| --- | --- |
| `python3 -m py_compile browser/server.py` | PASS |
| Sensitive browser/unit/HTTP coverage | PASS, 56 tests after adopting independent missing-test cases and closing encoded log-line injection |
| Targeted sensitive-content Playwright journey | PASS, 3 projects |
| `npm run test:js` | PASS, 8 tests |
| `npm run docs:build` | PASS |
| `npm audit --audit-level=high` | PASS, 0 vulnerabilities |
| `npm run verify` | PASS, 8 JavaScript + 799 Python tests (5 skipped), tracked public-ready scan of 370 files |
| `npm run test:e2e` | PASS, 108/108 journeys |
| `git diff --check` | PASS |

Benchmark readiness remains deliberately negative:

```text
status=protocol_frozen_pending_fixture_seal
ready=false
gate=sealed external fixture release is required
```

That expected exit does not fail this security slice. It keeps the product claim honest: verified net-win scenario classes remain 0.

## Visual Proof

| View | Receipt | Check |
| --- | --- | --- |
| Desktop page | `evidence/2026-07-10-browser-sensitive-content-boundary.png` | Warning, redacted content, and cockpit hierarchy render nonblank |
| Desktop detail | `evidence/2026-07-10-browser-sensitive-content-boundary-detail.png` | Count and replacement remain legible |
| 320px dark | `evidence/2026-07-10-browser-sensitive-content-boundary-mobile-dark.png` | No horizontal overflow or control collision |
| 320px drawer | `evidence/2026-07-10-browser-sensitive-content-boundary-mobile-drawer.png` | Settled drawer shows the `hidden` marker without overlap |

## Independent Review

- **Codex:** found tuple-shaped JSON and plain-text error/request-log backstop gaps; fixed them and added regressions before this receipt.
- **Grok:** constrained read-only retry returned `NO_CONCRETE_BLOCKER`. It named four missing write-rejection cases; all four were added and pass.
- **Fable:** `claude-fable-5`, plan mode, bounded budget returned no verdict before the bounded call was stopped. Recorded as `sidecar_unavailable`, not a product pass or failure.
- **GLM:** the bounded `glm` call returned provider `529`; the OpenCode retry read the two scoped files but did not return a verdict before timeout. Recorded as `sidecar_unavailable`, not a product failure.
- **Skillbox:** the active `/vidux` mount resolves through the generated runtime home to `vidux-main-active`; `SKILL.md` and `browser/server.py` are byte-identical to this checkout. Global `skillbox doctor` separately reports 156 unrelated shared-runtime drift rows, so global farm health is not claimed clean.

Model opinions are not proof. Grok's useful output became concrete tests; unavailable sidecars did not waive any mechanical gate.

## Limits

- Receipt-image pixels and other binary media are not scanned. A non-private image can reveal printed credentials.
- The detector is intentionally high-confidence, not exhaustive. Credentials do not belong in plans, sessions, ledgers, comments, artifacts, or receipt annotations.
- Any credential exposed before redaction must be revoked or rotated.
- The parent row 6.0.2 remains active for artifact network isolation, symlink/hard-link mutation behavior, future runner authorization, and other unproved surfaces.

## Final Verdict

The sensitive-content boundary is reversible, tested, visible, and ready to ship as one code-bearing security slice. It does not establish that Vidux beats native Claude or Codex, and it does not complete the overall security floor.

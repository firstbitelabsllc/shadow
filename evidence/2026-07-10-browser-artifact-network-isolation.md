# Browser Artifact Network Isolation

Date: 2026-07-10

Verdict: **SHIPPING for row 6.0.2c only.** This closes artifact-initiated network traffic and external navigation in the browser cockpit. The parent security floor, benchmark v2, onboarding, and open-source release rows remain open.

## Claim

Vidux now renders HTML artifacts without allowing them to issue HTTP(S) requests, navigate outside their own fragment anchors, execute scripts, submit forms, open popups, or create nested browsing contexts. Direct HTML reads are download-only. This is one confidentiality boundary, not a claim that the full browser security floor or Vidux's product superiority is complete.

## Red Proof

Before the fix, a real Chromium render contacted an isolated local sink at `/passive-image?private=1` even though the artifact iframe did not grant scripts. The permanent adversarial fixture then demonstrated four reachable request classes:

- `/style.css`
- `/passive-image?private=1`
- `/nested-frame`
- `/clicked`

The first response-header regression also failed because direct artifact responses did not include `X-Content-Type-Options`. These were product failures, not harness failures: HTML sandbox tokens limited capabilities but did not prevent passive network fetches or link navigation.

## Implementation

- `browser/server.py` makes direct HTML reads download-only and adds a deny-by-default Content Security Policy, same-origin resource policy, no-referrer, no-sniff, and same-origin frame headers.
- `browser/static/app.js` parses every artifact into a fresh document, removes existing CSP/refresh policies, bases, scripts, frames, objects, embeds, every link element, event handlers, form targets, and non-fragment HTML/SVG/image-map navigation.
- The cockpit prepends its own embed-safe CSP and uses exactly `sandbox="allow-same-origin"` plus `referrerpolicy="no-referrer"`. It never grants scripts, forms, popups, downloads, or top-level navigation.
- A host-owned fetch loads `artifact-base.css`; its trusted bytes are inlined only when the documented marker is present. Artifact-authored stylesheet URLs are never retained.
- A post-fetch view-revision check prevents a delayed base-style response from overwriting a newer plan selection.
- The artifact metadata row shows `network isolated` so the operator can see the active boundary.

## Live Response Contract

The real local server returned the following artifact-specific headers:

```text
Content-Disposition: attachment; filename="vidux-artifact.html"
Content-Security-Policy: default-src 'none'; base-uri 'none'; connect-src 'none'; font-src data:; form-action 'none'; frame-ancestors 'self'; frame-src 'none'; img-src data: blob:; manifest-src 'none'; media-src data: blob:; object-src 'none'; script-src 'none'; style-src 'unsafe-inline'; worker-src 'none'
Cross-Origin-Resource-Policy: same-origin
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
```

The `frame-ancestors` response directive is intentionally removed before the policy is embedded as a `srcdoc` meta policy because that directive is response-only. Every request-producing directive remains deny-by-default.

## Mechanical Proof

| Gate | Result |
| --- | --- |
| Focused response/static contracts | PASS |
| Artifact base-style, network-isolation, and stale-render Playwright journeys | PASS, 9/9 across Chromium desktop, iPad, and iPhone projects |
| `python3 -m py_compile browser/server.py` | PASS |
| `npm run verify` | PASS, 8 JavaScript + 802 Python tests (5 skipped), tracked public-ready scan of 379 files |
| `npm run test:e2e` | PASS, 114/114 journeys |
| `npm run docs:build` | PASS |
| `npm audit --audit-level=high` | PASS, 0 vulnerabilities |
| `git diff --check` | PASS |

Benchmark readiness remains deliberately negative:

```text
status=protocol_frozen_pending_fixture_seal
ready=false
gate=sealed external fixture release is required
```

That expected exit is not a product failure, but it prevents a superiority claim. Verified net-win scenario classes remain 0.

## Visual Proof

> Round-11 privacy fix: the three screenshots for this receipt were captured
> against the maintainer's real dev root, so the artifact-metadata row rendered
> the literal absolute home-directory path (username and all) in legible
> text — a leak class the text grep-gate cannot see (PNG pixels). This
> receipt's own Limits section already noted "sensitive text embedded in
> pixels is not inspected," but that wasn't applied to its own screenshots
> before merge. The three files were removed; the network-isolation guarantee
> below is proven mechanically by the live browser check and the e2e test
> (`browser/tests/e2e/smoke.spec.ts`), which need no screenshot.

The live browser check also confirmed no host or frame overflow, the exact `allow-same-origin` sandbox, the no-referrer policy, zero page/console errors, and zero sink requests.

## Independent Review

- **Codex:** found a concrete stale-render race after the new asynchronous base-style fetch. The implementation now rechecks the view revision after that await, and the regression proves a delayed artifact render cannot replace a newer plan selection.
- **Grok:** the bounded read-only review became trapped in local bootstrap and MCP warnings and returned no verdict. Recorded as `sidecar_unavailable`, not a product pass or failure.
- **GLM:** the bounded read-only OpenCode review inspected the scoped source but did not converge before timeout. Recorded as `sidecar_unavailable`, not a product pass or failure.
- **Fable:** not invoked because this slice did not require a hard architecture decision after the threat model and red evidence established the boundary.
- **Skillbox:** the active Vidux mount resolves through the generated runtime home to this checkout, and Vidux hashes are consistent across Claude, Agents, Cursor, Codex, Grok, and OpenCode. Global doctor still reports unrelated shared-skill farm drift, so global runtime health is not claimed clean.

Model opinions are not proof. The concrete Codex objection became a regression; unavailable sidecars did not waive any mechanical gate.

## Limits

- Sensitive text embedded in receipt-image pixels and other binary media is not inspected.
- Symlink and hard-link mutation behavior remains unproved.
- Any future runner or action endpoint still requires its own authorization and threat model.
- This slice does not prove that Vidux beats native Claude or Codex. The external 48-fixture release and paired benchmark remain gated on an independent evaluator.

## Final Verdict

The artifact network boundary is reversible, tested against real browser traffic, visible in the cockpit, and ready to ship as row 6.0.2c. The parent security floor remains active, and the value scorecard remains honestly unproven.

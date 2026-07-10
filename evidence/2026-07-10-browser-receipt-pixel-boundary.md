# Browser Receipt Pixel Boundary

Date: 2026-07-10

Verdict: **SHIPPING for row 6.0.2e only.** Stored receipt-image bytes are now available only to a loopback TCP client. Trusted-LAN viewers retain non-private text metadata but receive an explicit host-only state, and the UI does not request the image route. The parent security floor remains active for authorization of any future action runner. Benchmark v2 remains gated and has zero verified net-win scenario classes.

## Red Proof

A temporary corpus contained one synthetic public receipt row and a 2,048-byte image. With the browser bound to `0.0.0.0`, the same image route was exercised through loopback and the Mac's private LAN address:

```bash
curl -sS -o /tmp/loopback-image -w '%{http_code} %{size_download}\n' \
  "http://127.0.0.1:${PORT}/api/receipts/${ROW_ID}/image"
curl -sS -o /tmp/lan-image -w '%{http_code} %{size_download}\n' \
  "http://${PRIVATE_IP}:${PORT}/api/receipts/${ROW_ID}/image"
curl -sS "http://${PRIVATE_IP}:${PORT}/api/receipts/list"
```

Before the fix, loopback image GET, LAN image GET, and LAN list all returned `200`; both image reads returned 2,048 bytes, and the LAN list exposed the public row's image path. This was a product confidentiality gap, not a harness failure. All data and paths were temporary; no real receipt was used.

## Root Cause And Fix

The existing list route hid private rows from LAN clients, but a non-private row's raw image route had only the general Host allowlist. That protected against DNS rebinding without protecting pixel content from an intentionally connected LAN peer.

- `GET` and `HEAD /api/receipts/<id>/image` now require the actual TCP peer to be loopback before receipt storage is consulted.
- `/api/receipts/list` adds `image_access: { available, policy: "loopback_only" }` based on the TCP peer, without exposing peer details.
- The receipt UI defaults closed, renders the host-only state and placeholder for LAN viewers, and emits no image request while access is unavailable.
- Loopback clients keep the existing stored-photo behavior.
- A real 320px dark-mode review exposed horizontal overflow in the receipt header and upload controls. Receipts-local responsive constraints now keep the exact page width at `320/320` without changing desktop geometry.
- README, skill, and browser reference wording now state that unscanned receipt pixels remain loopback-only.

## Green Runtime Proof

The same temporary row and image produced this post-fix matrix:

| Request | Result |
| --- | --- |
| Loopback image `GET` | `200`, 2,048 bytes |
| LAN receipt list | `200`, `image_access.available=false` |
| LAN image `GET` | `403`, zero image bytes |
| LAN image `HEAD` | `403`, zero image bytes |

Both LAN image verbs returned `receipt image pixels require loopback client`. The focused unit test also proves the rejection happens before `handle_image`, so corpus or image storage is not consulted.

## Mechanical Proof

| Gate | Result |
| --- | --- |
| `python3 -m unittest tests.test_browser_server.BrowserWriteEndpointHTTPTests` | PASS, 54/54 |
| `python3 -m unittest tests.test_browser_server tests.test_vidux_contracts` | PASS, 365 tests (5 skipped) |
| Focused receipt-image Playwright matrix | PASS, 6/6 across desktop, iPad, and iPhone |
| `npm run test:e2e` | PASS, 126/126 journeys |
| `bin/vidux build` | PASS, docs + 11 JavaScript + 838 Python tests (5 skipped) + release package |
| Release package verification | PASS, 186 files, 1,826,647 unpacked bytes, SHA-256 `efec493dfe48980b14c80be7d31d94a1b52bfef45dfde189955492843a8eefb1` |
| `npm audit --audit-level=high` | PASS, 0 vulnerabilities |
| Staged public-ready grep gate | PASS, 394 files |
| `python3 -m compileall -q browser tests scripts` | PASS |
| `git diff --check` | PASS |

The core contract, public-ready, package, and transport gates were rerun after this receipt and PLAN update before commit.

One earlier post-edit core invocation was not counted green after a single worker in the pre-existing cross-process comment-lock test reported a transient `ENOENT` while opening its sidecar lock. The exact stress test then passed 30/30 consecutive runs, and the complete 365-test core suite passed cleanly with no competing Vidux test process. The failure did not reproduce, so no shared filesystem behavior was broadened without a falsifiable root cause.

## Visual Proof

- [Desktop LAN receipt lab](2026-07-10-browser-receipt-pixel-boundary.png)
- [Host-only receipt detail](2026-07-10-browser-receipt-pixel-boundary-detail.png)
- [Exact 320px dark mobile](2026-07-10-browser-receipt-pixel-boundary-mobile-dark.png)

All three receipts were inspected after capture. The access banner and host-only placeholder are legible, controls do not overlap, and the exact mobile viewport reports `scrollWidth=clientWidth=320`.

## Independent Review And Mount Truth

- **Codex:** reproduced the byte leak before implementation, checked the live green matrix, caught and fixed the 320px overflow, inspected all three screenshots, and found no remaining concrete blocker in this slice.
- **GLM:** independently traced GET and HEAD through the real TCP-peer gate, checked alternate static/file/OCR paths, verified the UI's fail-closed default and zero-request contract, and returned `NO_BLOCKER_FOUND`.
- **Grok:** the bounded read-only attempt tried to package a roughly 145 MB workspace, exceeded its 50 MB upload boundary, and did not return the required verdict. Recorded as `sidecar_unavailable`, not a pass or product failure.
- **Fable:** not called; this reversible boundary had no unresolved architecture or adjudication decision after the red proof.
- **Skillbox:** the Vidux skill has one consistent source hash across Claude, Agents, Cursor, Codex, Grok, and OpenCode. Global doctor still reports unrelated shared-skill farm drift.
- **Host routing:** source lane parsing passed, while generated host-runtime mirrors outside this repository lag their source. That ecosystem drift is recorded separately and is not presented as Vidux product proof.

Model opinions are not proof. GLM's claims were adjudicated against disk, tests, and runtime traffic. Unavailable sidecars did not waive a mechanical gate.

## Benchmark Honesty

Readiness remains deliberately negative:

```json
{
  "gates": ["sealed external fixture release is required"],
  "protocol_digest": "0b8da7650ed4274f6c73611e04e700e1a83a099bfda10d8f81aeba3055d33e86",
  "ready": false,
  "status": "protocol_frozen_pending_fixture_seal"
}
```

This security improvement is valuable but does not prove Vidux beats direct Claude or Codex. Verified net-win scenario classes remain 0.

## Limits

- Receipt pixels are not scanned or redacted; they are contained to loopback clients.
- The boundary does not protect against a hostile process already running as the local user.
- No action runner endpoint exists. If one is introduced, explicit authorization and adversarial proof are required before it can ship.
- Benchmark v2 still requires an independently sealed external fixture release and paired direct-native controls.

## Final Verdict

The receipt-pixel slice is reversible, red/green proven, visibly understandable, and ready to ship as row 6.0.2e. The broader product-win claim remains honestly unproven.

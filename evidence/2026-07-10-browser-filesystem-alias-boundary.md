# Browser Filesystem Alias Mutation Boundary

Date: 2026-07-10

Verdict: **SHIPPING for row 6.0.2d only.** Vidux browser mutations now fail closed on filesystem aliases across artifacts, comments, plan notes, receipt images, corpus files, and lock files. The parent security floor, benchmark v2, onboarding, and open-source release rows remain open.

## Claim

A valid Vidux HTTP write can no longer use a final-component symlink, hard link, non-regular target, or symlinked store directory to modify an alias referent. Rewrites use a unique temporary file and descriptor-relative atomic replacement in an already-opened parent directory. This is a local mutation boundary, not a filesystem sandbox or a claim that Vidux beats native Claude or Codex.

## Red Proof

Before the fix, the focused command ran 73 tests and produced 11 product failures plus 2 cleanup errors:

```bash
python3 -m unittest \
  tests.test_browser_server.BrowserWriteEndpointHTTPTests \
  tests.test_receipts_handler.UploadTests \
  tests.test_receipts_storage.CorpusIOTests \
  tests.test_receipts_storage.SafeImageAbsTests
```

The failures proved that accepted writes followed artifact, comment, `INBOX.md`, receipt-image, corpus, and lock aliases. The cleanup errors were fallout from the expected outside-sentinel mutation, not harness defects. Every fixture used a temporary directory; no production file was targeted.

## Implementation

- `browser/safe_files.py` owns the shared no-follow open, regular single-link validation, safe read, and atomic replacement primitives.
- Artifact, comment, plan-note, receipt-image, corpus, and receipt lock mutations route through those primitives.
- Comment rewrites take a safe sidecar `flock` plus an in-process lock. An eight-process regression adds a deliberate delay between read and replace and proves all eight records survive.
- Receipt corpus rewrites retain their cross-process lock while replacing append-in-place behavior with a locked atomic rewrite.
- Receipt image-jail checks reject symlinked, hard-linked, and non-regular image files.
- Existing hard-linked HTML artifacts remain intentional read-only mirrors. The artifact write endpoint refuses to overwrite them.
- Alias errors return bounded generic responses and do not disclose local target paths.

## Sentinel Matrix

| Surface | Adversarial target | Result |
| --- | --- | --- |
| Artifact write | symlink, hard link, symlinked store directory | Rejected; outside bytes unchanged |
| Comment write | symlink, hard link, symlinked store directory | Rejected; outside bytes unchanged |
| Comment lock | symlink, hard link | Rejected; no comment store created |
| Comment concurrency | eight independent Python processes | All eight records preserved |
| Plan note | symlinked or hard-linked `INBOX.md` | Rejected; outside bytes unchanged |
| Receipt upload | symlinked or hard-linked image destination | Rejected; outside bytes unchanged |
| Receipt corpus | symlink, hard link, symlinked corpus directory | Rejected; outside bytes unchanged |
| Receipt lock | symlink, hard link | Rejected; outside bytes unchanged |
| Receipt image read | symlink or hard link in image jail | Rejected |

## Mechanical Proof

| Gate | Result |
| --- | --- |
| Focused alias and write-route matrix | PASS, 79/79 |
| Browser and receipt regression suite | PASS, 199 tests (1 skipped) |
| `python3 -m py_compile browser/server.py browser/safe_files.py browser/receipts/storage.py browser/receipts/handler.py` | PASS |
| `npm run verify` | PASS, 8 JavaScript + 819 Python tests (5 skipped); final staged public-ready scan passed on 381 files |
| `npm run test:e2e` | PASS, 114/114 journeys |
| `npm run docs:build` | PASS |
| `npm audit --audit-level=high` | PASS, 0 vulnerabilities |
| `git diff --check` | PASS |

No UI code changed in this slice, so no new screenshot is used as mutation proof. The unchanged cockpit still passed all 114 desktop, tablet, and phone journeys; the HTTP and outside-sentinel tests are the relevant proof for this boundary.

## Benchmark Honesty

The benchmark readiness command remains deliberately negative:

```json
{
  "fixture_release_digest": null,
  "gates": ["sealed external fixture release is required"],
  "protocol_digest": "0b8da7650ed4274f6c73611e04e700e1a83a099bfda10d8f81aeba3055d33e86",
  "protocol_id": "vidux-cockpit-v2",
  "ready": false,
  "status": "protocol_frozen_pending_fixture_seal"
}
```

This expected gate is not a product failure, but it prevents a superiority claim. Verified net-win scenario classes remain 0.

## Independent Review

- **Codex:** found one concrete regression after the first green run: atomic comment rewrites were serialized only inside one process, unlike the previous append behavior. The final implementation adds a safe cross-process lock and permanent eight-process no-loss regression. No other concrete blocker survived source, test, and runtime adjudication.
- **Fable:** the bounded read-only review ran for about 3.5 minutes and reported approximately $1.96 before ending with `error_during_execution` / `aborted_streaming` and no decision. Recorded as `sidecar_unavailable`, not a pass or product failure.
- **GLM:** the bounded read-only OpenCode review inspected the scoped source and tests but did not return a verdict before the 180-second timeout. Recorded as `sidecar_unavailable`.
- **Grok:** the bounded read-only review made a favorable partial observation, then continued into its own verifier and did not emit the required final answer before the 180-second timeout. Recorded as `sidecar_unavailable`; the partial sentence is not counted as a verdict.
- **Skillbox:** Vidux reports one consistent source hash across Claude, Agents, Cursor, Codex, Grok, and OpenCode. Global doctor still reports unrelated shared-skill farm drift, so global runtime health is not claimed clean.

Model opinions are not proof. The concrete Codex objection became code and a regression test; unavailable sidecars did not waive any mechanical gate.

## Limits

- This boundary rejects aliases at mutation targets and their opened store directory. It is not a general containment system for a hostile same-user process with permission to replace arbitrary ancestor directories.
- Sensitive text embedded in receipt-image pixels and other binary media is not inspected.
- Any future runner or action endpoint still requires an explicit authorization model and threat review before implementation.
- Benchmark v2 still requires an independently sealed external fixture release and paired native controls.

## Final Verdict

The filesystem alias mutation slice is reversible, red/green proven, concurrency-safe for comment and corpus rewrites, and ready to ship as row 6.0.2d. The parent security floor remains active, and Vidux's quantitative product-win claim remains honestly unproven.

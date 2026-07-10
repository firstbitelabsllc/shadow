# Investigation: Browser Security Floor

## Reporter Says

Vidux must be safe enough to act as a local-first multi-project cockpit before any action-oriented expansion. The security floor explicitly covers local HTTP exposure, file allowlists, write endpoints, HTML injection, CSRF/origin checks, secrets, and future runner controls.

## Evidence

- Confirmed red request on 2026-07-10: with `browser/server.py` bound to `0.0.0.0`, `GET /api/plans` carrying `Host: evil.example:7197` and `Origin: http://evil.example:7197` returned `HTTP/1.0 200 OK` with a 13,879-byte plan payload.
- Control request: the same LAN-bound server returned `200` for `Host: 192.168.1.50:7197`, which is the intended trusted-LAN path.
- `browser/server.py:is_allowed_request_host()` returns `True` for every Host whenever the bind host is `0.0.0.0` or `::`; the independent Host allowlist therefore protects loopback mode but not LAN mode.
- `docs/reference/browser.md` and `SKILL.md` claim every request is Host-allowlisted and arbitrary registered domains are rejected, including in LAN mode. Runtime behavior contradicts that contract.
- Existing write routes already require JSON, same-origin metadata, and either a loopback TCP peer or the documented private-LAN comment carve-out. Existing file reads resolve under `DEV_ROOT` or `ARTIFACTS_DIR`, and markdown rendering uses locally vendored DOMPurify.

## Root Cause

The LAN opt-in was implemented as a complete bypass in `is_allowed_request_host()` instead of a different allowlist. A DNS-rebound page can therefore use its own attacker-controlled hostname as both URL origin and Host header, resolve that hostname to the LAN-bound Vidux server, and read plan/proof APIs as a same-origin response.

## Impact Map

- Confirmed confidentiality impact: `/api/plans`, `/api/file`, `/api/ledger`, `/api/health`, `/api/artifacts`, and receipt reads all pass through the same permissive GET gate in LAN mode.
- Write impact is lower: non-comment writes still require a loopback TCP peer; comment writes separately reject a non-loopback peer whose Host is not a private IP literal.
- This slice does not claim the full 6.0.2 security floor. Secret-content policy, artifact network isolation, symlink/hard-link mutation behavior, and future runner authorization remain to be adjudicated and tested. The dependency audit was closed during implementation and is recorded in the evidence receipt.

## Fix Spec

- Change `browser/server.py:is_allowed_request_host()` so wildcard bind mode accepts loopback identities and private-use IP-literal Hosts, but rejects domain Hostnames, missing Hosts, public IPs, and malformed values.
- Keep normal loopback bind behavior unchanged.
- Correct README/SKILL/browser-reference wording so trusted-LAN access explicitly uses the server's private IP address; do not promise arbitrary LAN hostname support without an explicit allowlist.
- Add helper-level and live HTTP regressions proving an attacker domain gets `403` while a private-LAN IP Host still gets `200`.

## Tests

- `python3 -m unittest tests.test_browser_server.BrowserLocalPlanNoteTests tests.test_browser_server.BrowserWriteEndpointHTTPTests`
- Live LAN-bound smoke: attacker-domain Host returns `403`; private-LAN IP Host and loopback Host return `200`.
- Core proof floor: `python3 -m unittest tests.test_browser_server tests.test_vidux_contracts`.

## Gate

- The red request is captured before implementation and turns green against the same route after implementation.
- No write-route relaxation, file-allowlist broadening, runner endpoint, or Resplit edit enters the slice.
- Row 6.0.2 stays active until the remaining security surfaces above receive their own adversarial proof.

## Follow-up: Sensitive Content Boundary

### Reporter Says

Allowed plan/proof paths can still contain credentials even when the path allowlist, Host gate, and origin checks are correct. The browser must not turn local plan state, session excerpts, ledger rows, comments, artifacts, or receipt metadata into a convenient secret-reading surface.

### Red Evidence

- The pre-implementation focused run executed 47 tests and produced 6 failures plus 2 errors on the intended leak paths.
- Raw `/api/file` content and `/api/plans` metadata returned a synthetic provider-shaped value unchanged.
- Claude session excerpts, ledger excerpts, legacy comments, artifact titles, and generic JSON metadata had no common scrubber.
- Artifact, comment, and local plan-note writes accepted the same synthetic value.

All fixtures construct synthetic values at runtime so no token-shaped test value is committed or sent to sidecars.

### Root Cause

The browser correctly restricted which files and routes were reachable, but it treated the contents of an allowed file as implicitly display-safe. Individual extractors and write endpoints therefore had no shared sensitive-value policy, and HTTP error/log backstops were absent.

### Fix

- Add one stdlib-only high-confidence detector for provider prefixes, bearer credentials, JWTs, private-key blocks, explicit secret/key/token/password assignments, and long mixed high-entropy atoms.
- Preserve hex digests and explicit example/redacted/unset placeholders to avoid turning ordinary proof hashes into false alarms.
- Redact before plan parsing and across raw file reads, sessions, ledgers, comments, artifact titles, receipt JSON metadata, plain-text errors, and request logs.
- Mark affected plan payloads with `content_redacted` and `sensitive_redactions`; render a visible warning and navigator marker in the cockpit.
- Omit plans or artifacts with secret-shaped path segments from discovery.
- Reject detector matches on artifact, comment, and local plan-note writes rather than persisting a redacted mutation.

### Remaining Boundary

- Detection is defense in depth, not a credential vault; exposed credentials still require rotation.
- Receipt-image pixels and other binary media are not inspected.
- Artifact network isolation, symlink/hard-link mutation behavior, future runner authorization, and the rest of row 6.0.2 remain open.

### Proof

See `evidence/2026-07-10-browser-sensitive-content-boundary.md` for the exact command, responsive screenshot, sidecar, mount, and benchmark-honesty receipts.

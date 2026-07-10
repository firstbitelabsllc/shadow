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

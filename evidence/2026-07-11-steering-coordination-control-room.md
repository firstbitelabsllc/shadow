# One-shot steering and live-work control room proof

Date: 2026-07-11

## Shipped behavior (PR #10; merge `c47006d35b87cdff3916ef61519d4d5f533a4219`)

- **Steer next turn** persists one bounded, exact-plan intent for an existing
  host goal/loop. The host leases at a safe boundary and acknowledges only
  after its reply is accepted. `usage_exhausted` returns the item to a visible,
  retryable state.
- `vidux coordinate` claims one exact work surface, heartbeats, checkpoints a
  bounded summary/resume/proof pointer, releases explicit handoffs, and permits
  takeover only after release or expiry.
- The loopback-only **Live work** panel shows the selected plan's owners,
  expiry, checkpoints, resume pointers, and recent handoffs. It has no write
  route and exposes no hostname, PID, journal path, provider, token, or secret.
- Authority remains the selected `PLAN.md`; both journals are disposable local
  transport/presence state and never invoke a provider, shell command, goal,
  loop, or scheduler.

## Mechanical proof

- Focused mailbox, claims, and release-package suites — 57 passed.
- `python3 -m unittest tests.test_browser_server -q` — 193 passed, 1 skipped.
- Focused launcher/dispatcher contracts passed for store identity, strict flag
  parsing, completions, and `vidux coordinate` dispatch.
- Focused Playwright desktop journeys passed 3/3: four disjoint live owners +
  usage-exhausted resume; mocked steering lifecycle; real GUI/host CLI shared
  journal with exhaustion, retry, reply-before-ack, and disappearance.
- `npm run test:js` — 20 passed, including unchanged-poll focus preservation.
- The 193-file release-package gate, `npm run docs:build`, Python compile,
  shell syntax, `git diff --check`, and the 426-file public-ready scan passed.
- GitHub secret scans passed and PR #10 was squash-merged to `main` as
  `c47006d35b87cdff3916ef61519d4d5f533a4219`.
- Shared and private host-adapter changes merged on 2026-07-11, keeping
  host/provider execution outside Vidux.

## Reviewed browser receipt

- `evidence/2026-07-11-live-work-steering-control-room.png` — current-source
  desktop cockpit with four live owners, one usage-exhausted resumable handoff,
  and the one-shot steering composer.
- `evidence/2026-07-11-steering-queued-desktop.png`
- `evidence/2026-07-11-steering-usage-retryable-desktop.png`
- `evidence/2026-07-11-steering-queued-mobile-dark.png`

This proves the local engineering journeys. It does not claim lower token cost,
provider availability, a remote deployment, or benchmark superiority.

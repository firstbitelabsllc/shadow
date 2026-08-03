# Pilot Puppy — Plan

This file is the sole plan, proof, and resume authority for Pilot Puppy.

## Outcome

Give one person a calm, portable chief-of-staff view of what their coding work
is trying to achieve, what is happening now, what proof exists, and which A/B/C
decision matters next—then drive bounded work through native Codex, Claude
Code, or Cursor without taking custody of credentials or conversations.

## Operator Brief

- Outcome ID: ship-pilot-puppy
- Outcome Revision: 8
- Outcome Updated At: 2026-08-03T15:57:00Z
- Outcome State: needs_input
- Outcome: Keep one calm, local Pilot Puppy front door usable while cross-host proof is unavailable.
- Next: Use the local CLI and browser now; Python selection no longer depends on a bare 3.9, while cross-host Codex proof remains deferred.
- Decision ID: choose-local-path
- Decision: What should Pilot Puppy do while the remote computer is unavailable?
- Option A ID: local-dogfood
- Option A: Run local dogfood
- Option A Consequence: Use the browser and native local hosts to validate the current brief now.
- Option B ID: local-product-row
- Option B: Take the next local row
- Option B Consequence: Ship the highest reachable product improvement without waiting on remote proof.
- Option C ID: defer-cross-host
- Option C: Defer cross-host proof
- Option C Consequence: Resume when Jump Connect accepts the target or quota resets; no remote work is attempted now.
- Proof ID: pilot-puppy-v2-public-readback
- Proof: tests/
- Proof Summary: v2.0.0 is public and fresh-clone/install/readback passes; real Claude Code and Cursor tasks pass, while Codex execution is quota-blocked.
- Proof Delivery: delivered

## Product boundary

- One product, repository, package, command, skill, configuration boundary,
  local evidence path, and user-facing name: **Pilot Puppy**.
- `PLAN.md` is durable authority. Receipts are bounded evidence, never a second
  queue or source of truth.
- Native coding hosts execute. Pilot Puppy seals scope, invokes one selected
  host, validates its receipt, and leaves final acceptance to the lead.
- The browser reads the same Outcome and renders one status brief plus one
  A/B/C choice. It does not run a cloud executor or store chat transcripts.
- No aliases, hidden products, daemon, scheduler,
  watcher, credential relay, remote database, or background dispatch loop.

## Platform alignment

- The current platform effort is local-first product proof. Cross-host
  portability is a deferred receipt, not a gate on reachable work.
- Existing plan, host, and project-local evidence boundaries are sufficient;
  do not add a router, queue, watcher, relay, or compatibility product to work
  around one unavailable Codex account.
- When the target is available, a usable Codex account there can complete the
  deferred receipt. The local quota reset is the alternate resume predicate,
  not a reason to expand the product.

## Worklane boundary

- Pilot Puppy has its own product plan and proof gap. That gap never blocks an
  unrelated product from shipping the highest-value reachable row in *its* own
  canonical plan.
- “One bounded task” means one reviewable handoff with an exact scope. It does
  not mean only one project may move, nor that a safe, obvious in-scope
  improvement must wait for an unrelated host, quota, or portability check.
- Use Pilot Puppy where its briefing, bounded execution, or resume record helps.
  Otherwise work directly in the product lane and prove the real user-visible
  outcome there. Amp only sharpens that lane's brief; it does not dispatch,
  validate, or become its authority.

## Privacy and safety

- Local by default; loopback browser only.
- Evidence is project-bounded, retention-bounded, and free of credentials,
  prompts, transcripts, provider payloads, and absolute private paths.
- Writes are atomic and idempotent. Host work is limited to an exact worktree
  and explicit allowed paths. Scope escape fails closed.
- Git history is preserved with ordinary forward commits.

## Work

- [completed] Establish the canonical package, command, skill, configuration,
  schemas, browser identity, and local state contract.
- [completed] Fold in the smallest proven native-host driver for Codex, Claude
  Code, and Cursor, with a sealed task and validated bounded receipt.
- [completed] Prove restart/resume, chief-of-staff status, A/B/C choice, privacy,
  packaging, installation, documentation, and full test behavior.
- [completed] Replace shared, private, and installed callers, then remove every
  predecessor command, skill, mount, hook, job, configuration, and active file.
- [completed] Rename the existing GitHub repository in place, merge, release,
  fresh-install, and read back the remote, mounts, command, and real UI.
- [completed] Run the final cold review and zero-surface audit; close only when
  all changed repositories are clean, pushed, and remotely verified.
- [completed] Publish the portable other-computer handoff with bootstrap,
  mounting, proof, privacy, and one exact resume predicate.
- [completed] Keep the local Outcome and A/B/C brief actionable when an
  external host is unavailable; take reachable product work without waiting.
- [completed] Resolve a Python 3.10+ interpreter from PATH or an explicit
  override so local commands and the browser do not fail on a pinned bare
  `python3`.
- [completed] Honor the documented local development-root and browser host/
  port environment defaults while preserving command-line precedence.
- [deferred] Close cross-host portability proof through the other-computer
  route or the local quota-reset fallback; require the same sealed task, exact
  allowed-path change, and lead-reproduced check.

## Mechanical proof required

- Full tests, docs, package, privacy, security, fresh clone, and install pass.
- `pilot-puppy doctor` passes; removed commands fail lookup.
- Codex, Claude Code, and Cursor each complete one sealed task with
  lead-reproduced proof.
- One real Outcome survives restart and renders an accurate brief and A/B/C
  choice.
- Active repositories and installed roots contain no predecessor product
  names, duplicate state, credentials, raw transcripts, or absolute private
  paths.
- The renamed public remote, release artifact, installed skill, command, and UI
  all read back as Pilot Puppy.

## Progress

- 2026-08-03: Made the local-first boundary operational. The unavailable Jump
  route is deferred, while the Outcome now offers three honest local choices:
  dogfood here, take the next reachable product row, or defer cross-host proof.
- 2026-08-02: Established one product authority. Outcome, briefing, decision,
  privacy, and native-host behavior stay; unrelated machinery is removed.
- 2026-08-02: Public core gate passes 79 Python tests, 3 JavaScript tests,
  4 desktop/phone browser tests, docs build, privacy fixtures, and a reproducible
  51-file stranger install. Real host, restart, cross-repository, and remote
  release proof remain open.
- 2026-08-03: Public main `6bd03c3f` passes 79 Python, 3 JavaScript, and
  4 Chromium tests, the 81-file public-ready scan, docs build, zero-vulnerability
  install, and a 51-file release package with SHA-256
  `9827381f6570dac1bf5e66611fae4056e18f3a14c6a914d85a099e5d5643b8cb`.
- 2026-08-03: `pilot-puppy doctor` passes 11/11 with one command and the same
  Pilot Puppy skill mounted in native Claude Code, Codex, and Cursor roots.
  Every predecessor command fails lookup; shared main is `c9efb7fe` and private
  main is `958a6163` after caller and runtime removal.
- 2026-08-03: Real sealed Claude Code and Cursor tasks changed only their exact
  allowed file and passed lead-reproduced checks. The real Codex CLI changed
  nothing and failed because its account usage limit resets after
  2026-08-07 23:52 America/New_York.
- 2026-08-03: A real mobile Chromium brief retained the identical
  `a4bf32b072f933ea2d89535097c3dc157a4c02ef3f2bb4ceec9d821d531f0f3f`
  API hash across a full server stop/restart and rendered the same Outcome and
  A/B/C choices.
- 2026-08-03: The final read-only Fable cold-review attempt returned no review
  payload after 12 internal turns and ended `aborted_streaming`; it is recorded
  as an unavailable sidecar, not approval. The lead Thermo audit found no
  duplicate authority, state store, runtime, compatibility surface, or release
  blocker. A stale unrelated health watcher was retargeted to neutral local
  state, stale Claude cleanup hooks were removed, and the retired state root
  was absent after final configuration validation.
- 2026-08-03: PR #88 merged as `6375c84a`; public release `v2.0.0` points to
  that exact commit and is the only visible release. Its attached 51-file
  package has SHA-256
  `9827381f6570dac1bf5e66611fae4056e18f3a14c6a914d85a099e5d5643b8cb`.
  A fresh public tag clone passed a zero-vulnerability install, 3 JavaScript
  tests, 79 Python tests, the 81-file public-ready scan, docs build, stranger
  package install, version readback, and a real new-repository A/B/C brief.
- 2026-08-03: PR #90 merged as `0c6d8ce1`. Its docs-only handoff makes the
  second-computer route the first unblock attempt for the remaining Codex
  execution proof. No new runtime, queue, router, credential relay, or second
  plan authority is needed.
- 2026-08-03: The read-only Jump Desktop attempt to the other-computer route
  returned `Computer is offline`; no remote UI, install, doctor, skill mount,
  or native-host receipt was produced. This is host availability, not a Pilot
  Puppy code failure.
- 2026-08-03: A fresh public clone at `83a95d3b` passed `npm ci`, rendered a
  working `pilot-puppy status`, and passed the 82-file public-ready scan.
  Its doctor was 8/11 because this computer's existing native skill mounts
  still resolved to the primary checkout; the documented mount commands are
  required on the target computer. This is an environment-boundary receipt,
  not a source defect.
- 2026-08-03: Made the worklane boundary explicit: Pilot Puppy is optional
  support for a project's own plan, not a universal validation gate. One
  bounded task keeps a handoff reviewable; it does not stop other projects
  from shipping safe, high-value reachable work.
- 2026-08-03: PR #98 merged as `a24120ff`. Post-merge `origin/main` readback
  passes 83 Python tests, 3 JavaScript tests, public-ready, docs, desktop and
  phone browser, and release-package verification. This proves merged source
  and CI behavior only; no new release or deployment was performed.
- 2026-08-03: The local Python-floor receipt now records five resolution tests,
  including hermetic override and low-bare-python fallback coverage; the
  84-test Python suite, public scan, docs, package, and browser gates pass
  without claiming remote host readiness.
- 2026-08-03: Configuration behavior now matches the public reference: `status`
  honors `PILOT_PUPPY_DEV_ROOT`, the browser honors `PILOT_PUPPY_DEV_ROOT`,
  `PILOT_PUPPY_BROWSER_HOST`, and `PILOT_PUPPY_BROWSER_PORT`, and explicit flags
  win over environment defaults. Two hermetic tests cover the status path and
  parser precedence; full gates remain the resume proof for this row.

## Deferred proof (not a global blocker)

- The other-computer route is deferred by host availability. Resume only when
  the target Mac is online and Jump Connect accepts the connection; then run
  the documented clone, install, doctor, skill-mount, and Outcome/A/B/C path.
- The public clone/install/status path is proven locally; the three mount
  failures are intentionally not counted as second-computer proof because the
  target host was offline. Do not call that receipt complete until its doctor
  is 11/11 from the target checkout.
- Native Codex execution is also time-bound. If the target has a usable
  account, run the same sealed task there; otherwise resume after 2026-08-07
  23:52 America/New_York. In either route, it must return `status: ok`, change
  only its allowed path, and pass the lead-reproduced check. A binary/version
  probe does not satisfy this deferred receipt.

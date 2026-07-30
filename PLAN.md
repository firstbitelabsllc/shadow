# Vidux — Plan

This is the repository's own working plan, kept in the same shape `vidux init`
scaffolds. It is planning authority for this repo; proof lives in the gates it
names, not in this prose.

## Purpose

Ship and maintain Vidux as a small, local-first plan/proof/resume layer that
complements native coding agents. It records durable planning authority
(`PLAN.md`), linked proof, and a read-mostly local cockpit — and it never routes
models, schedules work, or transports provider traffic.

## Evidence

- `README.md` — public contract and quick start.
- `CHANGELOG.md` — released scope and current corrective work.
- Test suites under `tests/` and `browser/tests/`; CI in `.github/workflows/`.

## Constraints

- Local-first and read-mostly: no new mutation, shell execution, secret
  access, or remote dispatch endpoint without an explicit threat model and a
  regression gate.
- The steering inbox and coordination claims stay loopback-only, plan-scoped,
  provider-neutral, non-executing, and independently auditable.
- Provider selection, worker dispatch, and evaluation belong to the coding
  host, never to Vidux.

## Operator Brief

- Status: 1.1.1 corrective source; release identity requires an exact matching
  tag and GitHub Release. The historical 1.1.0 release is unchanged.
- Outcome: keep the minimal public surface — `init`, `status`, `browse`,
  `checkpoint`, `doctor` — with tests, release-package verification, and the
  public-ready gate wired into CI.
- Next: keep the surface minimal; new capability requires a plan row here
  first, with its gate named before code lands.
- Validation: `npm run verify` (tests + public-ready gate) and
  `npm run release:verify`.

## Outcome Scorecard

| Metric | Current | Target | Proof |
|---|---|---|---|
| Test suites | green | green | `npm test` |
| Package byte-identity | passing | passing | `npm run release:verify` |
| Public-ready gate | passing | passing | `npm run public-ready:grep` |

## Tasks

- [completed] Cut the CLI to the minimal public surface and align docs.
- [completed] Wire CI: tests, release verification, secret scan, public-ready gate.
- [completed] Reduce the root skill and public fleet guidance to the
  plan/proof/resume boundary; remove private material and references to absent
  helpers; add documentation-target and public-data regressions.
- [in_progress] Make the outcome-first operator experience the next Vidux
  product capability. The durable product plan is
  [`plans/outcome-console/PLAN.md`](plans/outcome-console/PLAN.md). This is a
  bounded product hypothesis, not a rename or a claim that execution exists.
- [pending] Triage issues and PRs after the repository is public.

## Decision Log

- [2026-07-21] 1.0.0 is a local source contract, not a published release: no
  npm publication, git tag, or GitHub Release is claimed until one exists.
- [2026-07-21] Internal helpers (steering mailbox, coordination claims, config)
  stay invoked by script path.
- [2026-07-29] `checkpoint` is the fifth public command: an optional plan update
  and local-ledger helper, not a second authority or a publication gate.
  Completion requires explicit proof, and Git commit is opt-in.
- [2026-07-29] Vidux remains the durable plan/proof/cleanup kernel. The Outcome
  Console must make that machinery quiet: one current Outcome, one
  exceptional Ask, a Steer that supersedes stale direction, and proof at the
  end. The coding host still owns provider routing and execution.
- [2026-07-29] The first public slice is an interchange schema plus read-only
  validator. It proves bounded state shape and privacy invariants only; GUI,
  persistence, worker control, and a live stop-stale-work loop remain unproved.
- [2026-07-29] Public source carries product authority, not portfolio
  operations. Provider receipts, private repository links, personal paths,
  costs, and session identifiers are rejected from the maintained surface.

## Progress

- 2026-07-21: 1.0.0 cut — minimal CLI surface, consolidated CI, fresh
  changelog, plan reset to the scaffold shape.
- 2026-07-29: Recorded the Outcome Console opportunity, smallest useful GUI,
  competitor evidence, falsification gates, and bounded first dogfood slice.
  No GUI implementation, rename, or release claim is implied.
- 2026-07-29: Added the `vidux.outcome.v1` schema, synthetic example,
  reference, and deterministic validator as the provider-neutral boundary.
- 2026-07-29: Sanitized the maintained tip and `1.1.1` source package and
  strengthened the public-boundary gate. A release is valid only when its tag
  and GitHub Release resolve to these exact bytes. The historical `v1.1.0` tag
  and repository ancestry remain unchanged under the no-rewrite policy.
- 2026-07-29: Replaced stale host-database, scheduler, private-ledger, and
  nonexistent-helper guidance with the narrow public contract. Vidux owns
  inspectable repository authority; the coding host owns execution.

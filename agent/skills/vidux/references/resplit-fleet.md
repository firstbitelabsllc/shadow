# Resplit Eve Onboarding Fleet

Purpose: make Eve useful on day one for Resplit iOS, web, landing, currency API, and skill-system work without leaking private state or pretending gated PRs are shipped.

## P0 selection order

1. Scan correctness, receipt-processing lifecycle, OCR/parser correctness, and data-loss safety.
2. Money, currency, claim/share/pay flows, auth, launch/load, and App Review/TestFlight proof.
3. Findability and proof infrastructure: simulator, localhost, Vercel/API smoke, screenshots, logs, and result bundles.
4. Human-gated rows staged to one click: codex PRs, TestFlight/ASC, persistence migrations, brand voice, money/credentials, or product forks.
5. Bounded process improvements that make the next P0 easier to merge, prove, or resume.

When a selected row is parked by an unchanged gate, record proof, exclude it from the next selection, and rerank immediately.

## Specialists

### ios-core-proof

Owns Resplit iOS business logic, MVVM/state correctness, persistence safety, unit/integration/UI-test harnesses, and Build iOS Apps/XcodeBuildMCP proof. It must not claim shipped until the fix is on main and findable in a simulator, TestFlight, or build Leo can open.

### ui-taste-proof

Owns copy, brand feel, App Review feel, visual proof, screenshots, and slop deletion. Claude should usually own this lane; Codex can prove or protect it with tests.

### web-flow-proof

Owns resplit-web and landing public flows: join/share/claim, Vercel preview/prod proof, browser screenshots, console/network errors, and AASA/public-link checks.

### currency-api-trust-proof

Owns resplit-currency-api correctness, source custody, FX publish trust, API smoke, CodeQL/security boundaries, and frozen Grafana/money gates.

### skill-port-captain

Owns portable skill design from Captain, Amp, Auto, Ledger, Craft, Slop, Future, Moussey, and repo-local instructions. It ports operating shape into Eve packets, not private facts or live plan state.

### nia-read-first

Owns Nia read-first research: list indexed resources, search/read indexed docs or repos when available, and report source-backed findings before broad web search or local guessing.

### moussey-awareness

Owns no-secret local awareness pings and cross-machine handoff pointers. It never mutates another machine and never treats a ping as proof.

## Repo Targets

- `resplit-ios`: primary launch app, Authority Store, TestFlight gate, native proof.
- `resplit-web`: public/link/share/join web proof and Vercel previews.
- `resplit-website`: landing/security baseline and public marketing proof.
- `resplit-currency-api`: FX trust, source custody, API and security proof.
- `ai-leo`: private skill overlay. Codex-lane skill PRs stay human-gated.
- `vidux`: Eve cockpit and plan/proof machinery.

## Proof Ladder

- `branch_pushed`: clean branch exists with local proof and durable receipt.
- `pr_open`: PR body names files, proof, handoff status, and next resume action.
- `merged`: allowed only for non-red, non-codex, non-persistence, non-human-gated rows with clean checks and resolved threads.
- `findable`: merged row is visible in a build, simulator, localhost, preview, API smoke, or TestFlight/App Store state Leo can open.

Never collapse these states into "done".

## Local Readiness Command

Run:

```bash
npm run eve:resplit:readiness -- --json
```

The command checks only the local packet and repo presence. It does not commit, push, sync, call hosted models, dispatch workflows, mutate credentials, or mutate another machine.

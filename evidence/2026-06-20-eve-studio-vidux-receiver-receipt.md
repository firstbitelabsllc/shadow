# Vidux Eve Studio Receiver Receipt - 2026-06-20

## Scope

Install a local-only Eve cockpit for the Vidux engine from a clean worktree.
Private project plans remain local ignored data and are not committed by this
receiver branch.

## Baseline

- Branch: `codex/eve-studio-vidux-20260620`
- Base: `origin/main@cf46b06`
- Attached working checkout was dirty and ahead; it was not mutated.

## Installed

- Eve agent entrypoint and instructions under `agent/`.
- Local wrapper skills for `auto`, `vidux`, `ledger`, `moussey`, `captain`,
  and `nia`.
- Resplit onboarding packet at
  `agent/skills/vidux/references/resplit-fleet.md`, which is an Eve-supported
  packaged-skill resource path.
- Read-only `plan-readiness` subagent scaffold.
- Read-only `resplit-onboarding` subagent scaffold.
- Local capability checker at `scripts/eve-capability-check.mjs`.
- NPM scripts for `eve:info`, `eve:build`, `eve:dev:local`, and
  `eve:capabilities`; plus `eve:resplit:readiness`.
- Root dev dependencies for `eve`, `ai`, and `zod`.
- `.eve/` and `.output/` ignored as generated local artifacts.

## Proof

Proof passed from the clean receiver worktree:

- `npm install -D --save-exact eve@0.11.5 ai@7.0.0-beta.178 zod@4.4.3` completed and updated the lockfile.
- `npm ci --dry-run` exited 0 with the checked-in lockfile.
- `npm run eve:capabilities -- --json` returned `ok: true`, no errors, and no warnings.
- `npm run eve:info -- --json` returned status `ready`, 0 errors, and 0 warnings.
- `npm run eve:build` built `.output` successfully.
- `node --check scripts/eve-capability-check.mjs` passed.
- `git diff --check` passed.
- `npm run public-ready:grep` passed after removing a board-specific local-state filename from the checker.
- `npm test` passed: Vitest `7/7`; Python unittest `470` tests OK with `1` skipped.

## True-Integration Reproof

Fresh reproof passed from the same clean receiver worktree after hardening the
PR for review:

- Moved the Resplit onboarding packet out of unsupported `agent/onboarding/`
  and into `agent/skills/vidux/references/resplit-fleet.md`, so `eve info`
  discovers the root without warnings.
- Hardened `scripts/eve-capability-check.mjs` to verify installed
  `node_modules/ai/package.json`, `node_modules/eve/package.json`,
  `node_modules/zod/package.json`, and `node_modules/.bin/eve`, not just
  `package.json`.
- `npm ci --dry-run` exited 0 with the checked-in lockfile.
- `npm ls eve ai zod --depth=0` found `eve@0.11.5`,
  `ai@7.0.0-beta.178`, and `zod@4.4.3`.
- `node --check scripts/eve-capability-check.mjs` and
  `node --check scripts/eve-resplit-readiness.mjs` passed.
- `git diff --check` passed.
- `npm run eve:capabilities -- --json` returned `ok: true`, no errors, and
  no warnings.
- `npm run eve:resplit:readiness -- --json` returned
  `resplit_eve_onboarding_packet_ready`.
- `npm run eve:info -- --json` returned status `ready`, 0 errors, and 0
  warnings.
- `npm run eve:build` built `.output` successfully.
- `npm run public-ready:grep` passed.
- `npm test` passed: Vitest `7/7`; Python unittest `470` tests OK with `1`
  skipped.
- Focused PLAN-change contract reproof
  `python3 -m unittest tests.test_vidux_contracts` passed `216/216`.
- Moussey coding handoff `0d859a1e-a7e1-4c63-ae22-251916fd344a` was staged
  and read back from `/api/coding/handoffs` with label
  `vidux-eve-true-integration` and action `codex-verifier`.
- Commit `91a1ebd docs: record Vidux Eve readiness proof` was pushed to
  `codex/eve-studio-vidux-20260620`, and PR `firstbitelabsllc/vidux#149` was
  marked ready for review.
- PR `#149` is `OPEN`, non-draft, `MERGEABLE`/`UNSTABLE`; `Graphite /
  mergeability_check` passed.
- GitHub-hosted CI/check jobs did not start. The check annotations say:
  `The job was not started because recent account payments have failed or your
  spending limit needs to be increased.` Raw job metadata shows empty `steps`
  and `runner_id: 0`, so this is a billing/spending-limit gate rather than a
  local code/test failure.

Install note: the install reports npm audit debt (`7 vulnerabilities`). No
`npm audit fix` was run because the suggested force path could change unrelated
dependencies.

Test note: the clean public worktree did not contain ignored local project-plan
fixtures required by existing contract tests. Those ignored fixtures were copied
locally for proof parity only; they remain git-ignored and are not part of this
receiver branch.

## Non-Claims

- This does not publish Vidux packages, releases, or tags.
- This does not mutate local config, token files, or credentials.
- This does not commit ignored private project plans.
- This does not run live external board syncs.
- This does not dispatch hosted workflows.
- This does not call hosted models or download local model weights.
- This does not mutate other machines.

## Next

Resolve the GitHub Actions billing/spending-limit gate, rerun hosted checks,
then merge/replay and re-prove from trunk before claiming Vidux `origin/main`
is Eve-powered.

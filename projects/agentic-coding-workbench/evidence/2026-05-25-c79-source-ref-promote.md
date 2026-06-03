# C79 Source-Ref Promotion Proof

Date: 2026-05-25

## Summary

Moussey `/coding` moved the reviewed Resplit Web patch from "stored patch replay green" to a real source-ref proof.

- Source patch replay input: `/Users/leokwan/.moussey/coding-patches/9e532045-a3fb-487a-bfab-9adf2e969d33.patch`
- Promotion run: `6ecc9bcc-814d-416d-a689-4e32316ae127`
- Retained worktree: `/Users/leokwan/Development/resplit-web-worktrees/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r`
- Branch: `codex/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r`
- Local-only promoted commit: `65f654f0fbc39ddbdb7e373603ed291d0af3bcd9`
- Changed file: `e2e/landing-smoke.spec.ts`

The promotion lane now blocks broad or empty patches before build. This run emitted `patch-scope-ok` for one changed file, created a local-only commit, and recorded the promoted commit in run history so a later local-CI run can resolve `source_ref` to real git source state instead of replay-only candidate state.

## FirstBite Local-CI Proof

Clean aggregate MCP run:

```text
run_id=mcp-20260525T185412Z-89241
report=/Users/leokwan/.agent-ledger/firstbite-local-ci-mcp/mcp-20260525T185412Z-89241/report.json
source_ref=codex/web-promote-reviewed-patch-current-main-20260525T184547Z-tuug6r
resolved_source_ref=65f654f0fbc39ddbdb7e373603ed291d0af3bcd9
overall=pass
```

Lanes:

```text
resplit_web_unit        pass  npm ci && npm run test:run
resplit_web_integration pass  npm ci && npm run lint && npm run test:e2e:live-local
resplit_web_ui          pass  npm ci && npm run autobot:web
```

All three lanes ran from disposable worktrees with `dirty_count=0`, `ahead_origin_main=1`, and `sync_status=not_origin_main`. The primary checkout stayed dirty and was not used as the execution source.

## Machine Dependency Found

The first aggregate run failed integration because the Mac Studio was missing the Playwright browser revisions required by the promoted branch:

```text
webkit-2248 missing
firefox-1509 missing
```

Installing from the promoted worktree fixed the machine dependency:

```bash
npx playwright install webkit firefox
```

Do this from the same source ref or worktree that local CI will execute. The primary checkout had a newer Playwright version and installed newer browser revisions, which did not satisfy the branch-local Playwright 1.58.2 cache requirement.

## Local KV Answer

Docker is not required for the current Resplit Web local KV E2E path. The integration log confirms:

```text
[LIVE_SPLIT_KV] Using local in-process KV driver (explicit local KV driver).
```

Docker can stay optional future parity work if we later need a Redis/Upstash-compatible service boundary. It is not an MVP blocker for this local-CI proof.

## Remaining Gap

This is source-ref-true local CI on Mac Studio, not remote-main truth yet. The promoted commit is local-only until Leo or an agent chooses the next controlled path:

- push/open a PR from the promoted branch,
- apply the patch to the intended target branch,
- or merge the equivalent change into `origin/main`.

Only after that should the plan call it remote/fresh-main portable.

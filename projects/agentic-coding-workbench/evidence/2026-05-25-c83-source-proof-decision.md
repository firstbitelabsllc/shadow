# C83 Source Proof Decision

## Result

Moussey `/coding` now renders source-state truth as an operator decision panel instead of a small badge. The new `Source Proof Decision` section separates:

- Compared run and proof kind.
- Fresh-main portability.
- Remote-main portability.
- Dirty primary checkout state.
- Per-repo source verdicts.

This is the core local-CI honesty rule in the UI: a passing source-ref or retained-branch run can be useful local proof, but it is not presented as fresh-main or remote-main portability.

## Touched

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c83-source-proof-decision.png`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c83-source-proof-decision-mobile.png`

## Verification

```text
npx tsc --noEmit --pretty false
# pass

node --test --import tsx lib/coding-operating-resume.test.ts lib/coding-artifacts.test.ts app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts
# pass 71/71

npm run build
# pass, with known Turbopack NFT warning traced through app/api/coding/local-ci/artifact/route.ts

git diff --check -- app/coding/page.tsx lib/coding-workbench.ts
# pass
```

Production browser proof:

```text
http://127.0.0.1:4324/coding?fresh=c83-source-proof-decision
http://127.0.0.1:4324/coding?fresh=c83-source-proof-decision-mobile

Desktop:
- SOURCE PROOF DECISION
- Inspect Decision
- Source CI
- no console/page errors
- no horizontal overflow: 1440/1440

Mobile:
- SOURCE PROOF DECISION
- COMPARED RUN
- FRESH MAIN
- REMOTE MAIN
- PRIMARY CHECKOUT
- Inspect Decision
- no console/page errors
- no horizontal overflow: 390/390
```

Screenshots:

```text
projects/agentic-coding-workbench/evidence/2026-05-25-c83-source-proof-decision.png
projects/agentic-coding-workbench/evidence/2026-05-25-c83-source-proof-decision-mobile.png
```

## Remaining

- Add local-CI MCP cancel/resume primitives before exposing real cancel controls for FirstBite MCP reservations.
- Redact run-history args/prompts/output by default in the visible UI, keeping raw inspection explicit.
- Continue reducing disabled-state ambiguity around long-running browser streams.

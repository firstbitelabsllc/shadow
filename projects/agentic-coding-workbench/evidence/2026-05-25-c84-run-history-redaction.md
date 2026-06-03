# C84 Run History Redaction

## Result

Moussey `/coding` now treats run history as a summary-first product surface. Raw args and output tails are hidden by default, with an explicit `Raw Run` action for deliberate inspection. Secret-shaped values still stay redacted even in raw mode.

This closes the product gap where the local coding console looked like a raw agent transcript dump instead of a safe CI/operator history.

## Touched

- `/Users/leokwan/Development/moussey/app/coding/page.tsx`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/PLAN.md`
- `/Users/leokwan/Development/vidux/projects/agentic-coding-workbench/evidence/2026-05-25-c84-run-history-redaction.png`

## Verification

```text
node --test --import tsx app/api/coding/runs/route.test.ts lib/coding-workbench.test.ts
# pass 11/11

node --test --import tsx lib/coding-operating-resume.test.ts lib/coding-artifacts.test.ts app/api/coding/local-ci/run/route.test.ts app/api/coding/workers/route.test.ts app/api/coding/lanes/run/route.test.ts lib/coding-workbench.test.ts lib/local-ci-status.test.ts app/api/coding/local-ci/route.test.ts app/api/coding/runs/route.test.ts
# pass 75/75

npx tsc --noEmit --pretty false
# pass

npm run build
# pass, with known Turbopack NFT warning traced through app/api/coding/local-ci/artifact/route.ts

git diff --check -- app/coding/page.tsx app/api/coding/runs/route.ts lib/coding-workbench.ts app/api/coding/runs/route.test.ts lib/coding-workbench.test.ts
# pass
```

Production browser proof:

```text
http://127.0.0.1:4324/coding?fresh=c84-run-history-redaction

Found:
- Run history hides raw args and output tails by default
- Raw Run
- redaction:
- hidden raw detail:
- Use Raw Run for explicit inspection
- no console/page errors
- no horizontal overflow: 1440/1440
```

Explicit raw click proof:

```text
http://127.0.0.1:4324/coding?fresh=c84-raw-run-click

Found:
- Explicit raw inspection
- secret-shaped values stay redacted
- Raw Run button count: 1
```

Screenshot:

```text
projects/agentic-coding-workbench/evidence/2026-05-25-c84-run-history-redaction.png
```

## Remaining

- Add local-CI MCP cancel/resume primitives before exposing real cancel controls for FirstBite MCP reservations.
- Audit disabled controls so safe read-only work stays available during long-running streams.

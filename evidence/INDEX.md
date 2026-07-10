# Open-source-readiness panel — round index

The 9 readiness-panel rounds run against this repo so far, in true
chronological (first-commit) order — **not** the order their filenames would
suggest. Round-9 panel finding (`evidence-directory-hygiene-recheck` lens):
the file documenting round-4's remediation and round-2's launch was actually
authored before the file documenting round 3, so a reader globbing
`panel-round*` by name alone would reconstruct the wrong sequence. This index
exists to fix exactly that one confusion case — it does not rename or
otherwise touch any of the files below.

| # | Date (first commit) | File | Result |
|---|---|---|---|
| 1 | 2026-07-08 23:24 | [`2026-07-08-20-agent-open-source-readiness-panel.md`](2026-07-08-20-agent-open-source-readiness-panel.md) | Initial 20-agent panel — verdict + remediation log |
| 2 | 2026-07-09 12:04 | [`2026-07-09-round4-remediation-and-panel-round2-launch.md`](2026-07-09-round4-remediation-and-panel-round2-launch.md) | Round-2 launch (this file also documents round-4 remediation, authored later but committed together here) |
| 3 | 2026-07-09 13:52 | [`2026-07-09-panel-round3-and-urgent-remediation.md`](2026-07-09-panel-round3-and-urgent-remediation.md) | Round 3: 7/20 GO + urgent security remediation |
| 4 | 2026-07-09 14:45 | [`2026-07-09-panel-round4-results.md`](2026-07-09-panel-round4-results.md) | Round 4: 5/20 GO |
| 5 | 2026-07-09 15:30 | [`2026-07-09-panel-round5-results.md`](2026-07-09-panel-round5-results.md) | Round 5: 12/20 GO |
| 6 | 2026-07-09 15:57 | [`2026-07-09-panel-round6-results.md`](2026-07-09-panel-round6-results.md) | Round 6: 15/20 GO |
| 7 | 2026-07-09 22:42 | [`2026-07-09-panel-round7-results.md`](2026-07-09-panel-round7-results.md) | Round 7: 6/20 GO |
| 8 | 2026-07-09 23:47 | [`2026-07-09-panel-round8-results.md`](2026-07-09-panel-round8-results.md) | Round 8: 10/18 GO (script constructed 19 of 20 intended lenses; 1 failed outright) |
| 9 | 2026-07-10 01:02 | [`2026-07-10-panel-round9-results.md`](2026-07-10-panel-round9-results.md) | Round 9: 12/20 GO — first round with zero degenerate/failed lenses |

## Standing, unresolved as of round 9

Two items are confirmed, currently-live structural blockers on ever flipping
this repo public, both requiring a maintainer-authorized commit-message-level
git history rewrite (explicitly outside any panel lens's or agent's authority
to execute unilaterally):

1. **`refs/pull/*/head` leak** — 5 permanent GitHub-server-maintained PR refs
   carry a commit with a real internal-endpoint leak in its message,
   independent of any `origin/main` rewrite.
2. **Commit-message employer-PII** — exactly 4 commits (precisely re-scoped
   in round 9 from round 8's "~20" estimate) reachable from `origin/main`'s
   tip carry real employer-machine identity linkage in their commit
   messages, invisible to grep-gate/gitleaks/secret-scan.yml by design.

See round 9's evidence file for the full structural-blocker-impact-assessment
that separates these 2 from 3 other standing, risk-tolerable judgment calls
(private-fleet-ecosystem content scope, `vidux.ai` naming collision,
commit-authorship near-misses).

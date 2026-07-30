# Focused Vidux loop

Use this when the root skill is already understood and one explicit plan row
needs a short verification path.

## Read only what the row needs

1. Read the canonical `PLAN.md`, current revision, and working tree.
2. Resume the active row; otherwise choose the highest unblocked row.
3. Open only the evidence or decision linked by that row.

## Do one bounded change

Make one reversible change, run its named gate, record the result and
uncertainty in the plan, then exit with one cold-resume next move. Do not drain
the queue or invent adjacent work.

## Focused repository gate

```bash
bash scripts/vidux-thin-loop-verify.sh
```

This runs the supported JavaScript checks, focused Python contract tests, and
the public-boundary scan. Use the broader repository gate when runtime or
release-package behavior changed:

```bash
npm run verify
```

Claude Code is the tested skill host. Other hosts may read the same Markdown
contract, but remain untested.

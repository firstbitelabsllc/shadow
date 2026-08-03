# Quick start

```bash
cd /path/to/a/git/project
pilot-puppy init --here
pilot-puppy status --root .
pilot-puppy browse --root .
```

Fill the generated Operator Brief. The browser renders the same Outcome,
briefing, proof, and A/B/C options after every restart because `PLAN.md` is the
source.

For execution, freeze one complete task in a file:

```bash
pilot-puppy host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/task.md \
  --task-id focused-fix \
  --allowed-path src/fix.ts \
  --allowed-path src/fix.test.ts \
  --out .pilot-puppy/evidence/focused-fix.json
```

Review the diff and reproduce the tests before accepting the worker claim.

# Quick start

```bash
cd /path/to/a/git/project
shadow init --here
shadow status --root .
shadow browse --root .
```

Fill the generated Brief. The browser renders the same Outcome,
briefing, proof, and A/B/C options after every restart because `PLAN.md` is the
source.

Write work as tasks — a verifiable state plus a typed proof:

```text
- [in_progress] fix renders on the settings screen ~ab12 | proof: cmd npm test
```

`shadow lint PLAN.md` checks every row against the grammar; it also runs in
the test gate. When a row's `cmd` proof passes, flip it with the only flip
path:

```bash
shadow accept --repo "$PWD" --row ~ab12
```

For a bounded delegation, freeze one complete task in a file and explicitly
run a native host:

```bash
shadow host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/task.md \
  --task-id focused-fix \
  --allowed-path src/fix.ts \
  --allowed-path src/fix.test.ts \
  --out .shadow/evidence/focused-fix.json
```

Review the diff and reproduce the tests before accepting the worker claim.

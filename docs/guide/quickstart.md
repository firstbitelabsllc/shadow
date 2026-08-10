# Quick start

```bash
cd /path/to/a/git/project
shadow init --here
shadow status --by "your-seat"                # same computer board from anywhere
shadow throw --repo . --task '~a1b2' --by "your-seat" # atomic claim + packet
shadow browse --root .
```

Fill the generated Brief. The root board stores only that plan pointer, row id,
priority, and owner. The browser renders the same Outcome,
briefing, proof, and A/B/C options after every restart because `PLAN.md` is the
source.

Write work as tasks—a verifiable state plus a typed proof:

```text
- [pending] fix renders on the settings screen ~ab12 | proof: cmd npm test
```

`shadow lint PLAN.md` checks every row against the grammar; it also runs in
the test gate. When a row's `cmd` proof passes, flip it with the only flip
path:

```bash
shadow accept --repo "$PWD" --row '~ab12' --by "your-seat"
```

For delegation, freeze each complete claimed task in a file and explicitly run
native hosts over path-disjoint work:

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

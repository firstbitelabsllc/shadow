# Quick start

```bash
cd /path/to/a/git/project
shadow init --here
shadow roster init
shadow roster show
shadow status --root .
shadow browse --root .
```

Fill the generated Operator Brief. The browser renders the same Outcome,
briefing, proof, and A/B/C options after every restart because `PLAN.md` is the
source.

`roster init` makes a generic local list of `lead`, `planner`, `dev`, `debug`,
`review`, and `hard-dev`. It does not pick a model or start work. Match the
generic labels to your own native tools privately; no roster mapping is copied
into project status, the browser, or receipts.

For a bounded delegation, freeze one complete task in a file and choose a
declared local role first:

```bash
shadow route \
  --repo "$PWD" \
  --task-id focused-fix \
  --task-file /tmp/task.md \
  --task-kind dev \
  --out .shadow/evidence/focused-fix.route.json
```

Read the role/host choice, alternatives, and escalation. Then explicitly run
the selected host:

```bash
shadow host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/task.md \
  --task-id focused-fix \
  --allowed-path src/fix.ts \
  --allowed-path src/fix.test.ts \
  --route-file .shadow/evidence/focused-fix.route.json \
  --out .shadow/evidence/focused-fix.json
```

Review the diff and reproduce the tests before accepting the worker claim.

# Architecture

Vidux has three layers:

1. **Doctrine**: the rules in `SKILL.md`, `DOCTRINE.md`, and `LOOP.md`.
2. **Cycle**: READ -> ASSESS -> ACT -> VERIFY -> CHECKPOINT.
3. **Store**: `PLAN.md`, `evidence/`, `investigations/`, `INBOX.md`, and git history.

```text
+---------------------------+
|         DOCTRINE          |
| principles + constraints  |
+-------------+-------------+
              |
              v
+-------------+-------------+
|           CYCLE           |
| READ -> ASSESS -> ACT ->  |
| VERIFY -> CHECKPOINT      |
+-------------+-------------+
              |
              v
+-------------+-------------+
|           STORE           |
| PLAN.md + evidence + git  |
+---------------------------+
```

## Repo Layout

```text
vidux/
├── SKILL.md
├── README.md
├── DOCTRINE.md
├── LOOP.md
├── ENFORCEMENT.md
├── commands/
│   ├── vidux.md
│   └── vidux-status.md
├── docs/
│   ├── guide/
│   ├── concepts/
│   ├── fleet/
│   ├── reference/
│   └── examples/
├── guides/
│   ├── automation.md
│   ├── draft-pr-flow.md
│   ├── evidence-format.md
│   ├── fleet-ops.md
│   ├── harness.md
│   ├── investigation.md
│   └── recipes/
├── references/
│   └── automation.md
├── scripts/
│   ├── vidux-loop.sh
│   ├── vidux-checkpoint.sh
│   ├── vidux-status.py
│   ├── vidux-plan-gc.py
│   ├── vidux-doctor.sh
│   └── lib/
├── hooks/
│   ├── hooks.json
│   ├── pre-commit-plan-check.sh
│   ├── post-commit-checkpoint.sh
│   └── three-strike-gate.sh
├── tests/
│   ├── test_plan_gc.py
│   └── test_vidux_contracts.py
└── examples/
    ├── bug-fix-lifecycle/
    └── fleet-reference/
```

## How the Layers Connect

- `commands/vidux.md` defines the interactive orchestration contract.
- `commands/vidux-status.md` defines the read-only plan board contract.
- `scripts/vidux-loop.sh` and `scripts/vidux-checkpoint.sh` provide the mechanical helpers behind the cycle.
- `vidux.config.json` controls plan-store discovery and operational defaults.
- `docs/` mirrors the durable repo guidance in a VitePress site.

## Hook Enforcement

The repo ships three optional git hooks:

| Hook | Behavior |
|---|---|
| `pre-commit-plan-check.sh` | Blocks code commits when the repo has no active or pending task in `PLAN.md` |
| `post-commit-checkpoint.sh` | Prints a reminder when `PLAN.md` has no progress entry for today |
| `three-strike-gate.sh` | Prints escalation guidance after repeated `fix` / `retry` style commits |

Install them by copying the files into the target repo's `.git/hooks/` directory:

```bash
cp hooks/pre-commit-plan-check.sh /path/to/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/project/.git/hooks/
```

## Design Notes

- **One plan per project** keeps the queue authoritative and searchable.
- **Stateless cycles** assume sessions die and force durable checkpoints.
- **Evidence-first tasks** reduce rework by making decisions citeable.
- **Docs and guides stay separate**: `docs/` is the site, `guides/` and `references/` are the deeper source material it summarizes.

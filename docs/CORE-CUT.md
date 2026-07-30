# Vidux core boundary

Vidux is the public plan/proof/resume layer. It keeps one repository-owned
`PLAN.md`, records bounded proof, and makes interrupted work understandable to
the next person or agent.

## What belongs here

| Surface | Purpose |
|---|---|
| `bin/` | Small command-line entry points |
| `browser/` | Read-mostly local cockpit |
| `SKILL.md` | Agent entry point |
| `schemas/` and `examples/` | Provider-neutral interchange contracts |
| `scripts/` | Deterministic validation and release gates |
| `docs/`, `guides/`, `references/` | Public operating guidance |
| `PLAN.md` | Authority for work on Vidux itself |

## What does not belong here

- provider credentials, account state, quotas, costs, or session identifiers
- private repository links or private portfolio decisions
- personal filesystem paths or machine-specific ownership instructions
- raw worker transcripts, prompts, or model receipts
- execution, scheduling, or routing engines presented as Vidux capability

## Product boundary

Vidux can describe current work, validate a bounded status contract, and expose
local proof. The coding host still owns model selection, worker dispatch,
execution, authentication, and durable workflow infrastructure.

That separation is intentional: an orchestration engine may run the work while
Vidux remains the repository-owned source of truth that a human can inspect,
edit, commit, and resume without adopting a particular agent framework.

## Release boundary

A public release must pass:

1. unit and browser tests;
2. package-content verification;
3. secret and public-boundary scans;
4. exact-tag identity checks; and
5. a stranger-readable review of every shipped plan, guide, and example.

Historical releases are never silently moved. If a release claim or public
surface is wrong, publish a corrected successor and mark the earlier release as
superseded.

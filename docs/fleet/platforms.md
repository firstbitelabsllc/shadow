# Runtime Portability

Vidux is a runtime-neutral plan, proof, and resume discipline. A coding host may
provide chat, local, worktree, scheduled, or subagent execution; those
capabilities do not change the repository authority.

## Compare capabilities, not brands

Before choosing a host, verify its current official documentation and answer:

| Question | Why it matters |
|---|---|
| Can the run read the owning `PLAN.md` at a named revision? | Prevents stale or chat-only orientation |
| Can access be limited to read-only or selected repository paths? | Keeps authority proportional to the task |
| Can a child worker receive an exact file boundary? | Makes parallel work reviewable |
| Are missed, failed, and cancelled runs visible? | Prevents silence from reading as success |
| Can a recurring run be disabled through a supported control? | Gives every automation a clean retirement path |
| Can the lead reproduce the reported checks? | Keeps provider output separate from proof |

Do not select a runtime from undocumented model, account, cost, capacity, or
session assumptions. Those details can change independently of Vidux.

## Shared lifecycle contract

Every host follows the same sequence:

1. Read the owning plan and current revision.
2. Claim one bounded row or return a cited blocker.
3. Change only authorized paths.
4. Run the named verification.
5. Record the accepted proof and next move in repo-owned state.

Scheduler metadata and runtime logs may help diagnose a run, but they are not
planning authority and do not belong in a public proof packet.

## Execution modes

| Mode | Appropriate use | Default authority |
|---|---|---|
| Chat or read-only | research, review, status | no repository writes |
| Local | host-specific tools or UI proof | named working directory |
| Worktree | isolated implementation | named branch and file set |
| Scheduled | repeatable maintenance | one plan and retirement rule |
| Subagent | independent bounded slice | explicit output contract |

Choose the least-powerful mode that can produce the required proof. External
messages, deployment, publication, destructive changes, and secrets need
separate explicit authority.

## Integration boundary

Use the host's supported UI, CLI, or API. Do not modify undocumented databases,
session stores, caches, or account records to register or recover an
automation. Keep provider-specific setup outside public plans, and link to
official runtime documentation where setup is required.

## See also

- [Host-owned execution](operations.md)
- [Codex integration boundary](codex-lifecycle.md)
- [Small coordination recipes](recipes.md)

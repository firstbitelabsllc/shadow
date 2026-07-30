# Enforcement

Vidux does not install or manage coding-host hooks. The repository ships small,
optional examples that teams may inspect and adapt:

- `hooks/pre-commit-plan-check.sh` checks that code changes have an active or
  pending plan row.
- `hooks/post-commit-checkpoint.sh` prints a non-blocking reminder when the
  plan has no progress entry for the current day.
- `hooks/three-strike-gate.sh` warns after repeated retry-shaped commits.
- `hooks/hooks-reference.json` is a reference manifest, not an installer.

## Safe use

1. Read the script before copying it.
2. Install it only in a repository you own.
3. Keep the hook non-destructive and repository-scoped.
4. Test both its pass and fail paths in a disposable repository.
5. Record the installed path and removal procedure in that repository.

The hooks do not route providers, dispatch workers, inspect account state,
grant publication authority, or make a task complete. A coding host owns its
own lifecycle and configuration.

## Session guidance

A host-native start or stop prompt may remind an agent to:

- read `PLAN.md`, the current revision, and the working tree;
- resume the active row or take the highest unblocked row;
- run the row's named gate;
- record result, proof, uncertainty, and one cold-resume next move; and
- exit after one bounded row.

That prompt is guidance, not enforcement. Repository tests and review remain
the mechanical gates.

## Optional checkpoint helper

`vidux checkpoint` can update a plan and optionally append a local ledger row.
Completion requires `--proof`; blocked rows require `--blocker`; edits stay
uncommitted unless `--commit` is explicit. The plan remains authority, and a
ledger row never authorizes push, merge, deploy, spend, or communication.

## Limits

No hook can prove semantic plan alignment, safe publication, or product
correctness by itself. Use the repository's real tests and release gates.

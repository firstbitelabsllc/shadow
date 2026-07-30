# Enforcement

Vidux prefers mechanical checks over prompt promises, but it does not install
or control a coding host.

## Shipped checks

- `hooks/pre-commit-plan-check.sh` warns when a change lacks plan context.
- `hooks/post-commit-checkpoint.sh` records a local checkpoint when explicitly
  installed.
- `hooks/three-strike-gate.sh` helps surface repeated blocked attempts.
- `scripts/vidux-plan-guard.sh` detects unexpected task loss.
- `scripts/vidux-public-ready-grep-gate.py` checks the maintained public
  surface and commit metadata.
- `scripts/vidux-release-package.py` verifies exact package contents.

Hooks are optional and repository-local. Review them before installation.
Vidux does not modify host configuration, spawn review agents, or turn a prompt
into a security boundary.

## What a gate can prove

A gate proves only what it observes. A unit test does not prove deployment; a
pull request does not prove merge; a tag does not prove a GitHub Release; and a
content scan does not erase history.

Use the cheapest gate that observes the requested outcome, and state the
weakest truthful claim when a stronger surface is unavailable.

# Coordination recipes

These recipes are provider-neutral. They describe evidence and ownership, not
model routing or scheduling.

## Read-only research

- Outcome: answer one decision-relevant question.
- Scope: named sources; no writes.
- Return: facts, conflicts, uncertainty, and source links.
- Gate: the owner verifies the claims that change a decision.

## Bounded implementation

- Outcome: one observable behavior change.
- Scope: exact writable paths.
- Return: changed paths, tests, risks, and next move.
- Gate: the owner reviews the diff and reruns the important test.

## Adversarial review

- Outcome: find release-blocking failures at an exact revision.
- Scope: named failure classes such as privacy, security, truth, or usability.
- Return: reproducible findings ordered by severity.
- Gate: each blocker is reproduced or dismissed with evidence.

## Release review

- Outcome: prove source, tag, release, and checks identify the same revision.
- Scope: repository metadata and the clean release candidate.
- Return: identity receipt, required checks, alerts, package contents, and
  honest limitations.
- Gate: no release claim before its exact tag and hosted state exist.

## Cold resume

- Outcome: continue an interrupted row without retelling the project.
- Read: plan, revision, working tree, named proof.
- Return: current state and one next move.
- Gate: never reconstruct authority from a raw conversation.

Keep credentials, account data, billing data, runtime identifiers, raw
conversation logs, and private machine paths out of public plans.

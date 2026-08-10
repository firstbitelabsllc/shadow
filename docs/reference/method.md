# The Shadow Method

Shadow repeats one bounded cycle: read the computer board, resume or claim one
reachable checkpoint, do the work in its owning entity, reproduce its proof,
then accept or return the claim. [The grammar](grammar.md) owns the exact plan,
claim, proof, and lifecycle rules; this page owns the review step inside that
cycle.

## Attack, then refute

Before a checkpoint is accepted, attack the pinned change through every named
review lens. An attack must state a concrete failure, counterexample, or smaller
owner; vague concern is not a finding. Then try to refute each attack against
fresh source and the smallest discriminating check.

- A refuted attack is recorded as no action. Do not manufacture a rewrite.
- A surviving attack is fixed in the current checkpoint when it invalidates the
  contract. Otherwise it becomes one follow-up row with an exact wake or proof.
- Re-run the checkpoint proof after the surviving fixes. Review output alone is
  never completion.

The built-in lens set is:

- `thermo` — attack duplicate ownership, branches, wrappers, and abstractions
  that can be deleted or folded into an existing boundary.
- `ponytail` — refute the proposed remedy, then choose `delete`, `reuse`, `keep`,
  or `defer` and state whether the technical mechanism works.

A repository may declare a different bounded set without creating runtime
state:

```yaml
version: 1
adversarial-lenses: thermo, ponytail, taste
```

`shadow config --explain` prints the active set. These names are review
perspectives for the native host. Shadow does not install them, route work to
them, turn them into seats, or make a claim depend on their availability. A
repository with no `shadow.yaml` uses the built-in set and remains fully
functional.

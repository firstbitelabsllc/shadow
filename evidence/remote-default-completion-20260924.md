# Remote default completion fallback

Date: 2026-09-24
Row: `~rle2`
Seat: `Codex-Shadow-Trust`

## Source boundary

The normal `published_plan_snapshot` ancestor guard remains unchanged. The
completion retry path now has a separate fallback that:

- authenticates the remote default ref twice around the fetch;
- stays on the verified default ref and rejects feature-only upstreams;
- requires the default `PLAN.md` Git blob to equal the exact completion claim
  blob and verifies that blob against the claim head;
- materializes `shadow.plan-tree.v1` roots through the same bounded, digest
  checked `PLAN.d` reader used by the normal path;
- lets the existing row/proof/observation checks decide whether the completed
  row is present; and
- refuses a divergent default with a different or forged PLAN blob instead of
  pushing a stale completion branch over it.

## Focused falsifiers

Initial RED: before the fallback, two divergent-default tests reached the
ordinary publication push and failed with `push was REJECTED` rather than
reconciling the exact completion or retaining the claim safely.

Current GREEN:

```text
python3 -m unittest tests.test_shadow_accept.ARemoteManagedAcceptClosesOnlyAfterPublication.test_completed_retry_accepts_divergent_default_with_exact_claim_plan_blob tests.test_shadow_accept.ARemoteManagedAcceptClosesOnlyAfterPublication.test_completed_retry_refuses_divergent_default_with_forged_completion_tail tests.test_shadow_accept.ARemoteManagedAcceptClosesOnlyAfterPublication.test_completion_only_snapshot_materializes_sharded_claim_plan_and_rejects_forgery
...
Ran 3 tests in 21.932s
OK
```

The sharded test runs against a real `PLAN.md` root plus `PLAN.d` objects on a
rebuilt remote default. It accepts the exact root and materialized bytes, then
rejects a forged root. The managed acceptance class also passed after the
change: 18 tests in 132.889s, `OK`. The published-plan-tree regression class
passed: 14 tests in 61.067s, `OK`.

The sibling-history regression also passed: a separately committed default
shares the original claim base but has no completion-child ancestry; the
remote claim completed, the local completed checkout and bytes stayed fixed,
and the local board claim was released.

The native Git race regression passed as well. It force-pushes the remote
default after the fallback snapshot and immediately before remote claim CAS;
the guard refuses the transition, leaves the local board claim acquired, keeps
the local completed checkout unchanged, and leaves the remote journal acquired.

The same-tip identity-swap regression passed: changing the symbolic default
from `refs/heads/stable` to `refs/heads/main` at the identical commit is
rejected because the authenticated `(default_ref, default_tip)` pair changed.

## Boundary

This receipt covers source and focused test evidence only. No remote default
branch, primary checkout, release, installation, or publication was changed by
this worktree.

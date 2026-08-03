# Foreground routing

`pilot-puppy route` makes one local, explicit choice before a bounded native
handoff. It is the delegation decision, not another execution system.

```bash
pilot-puppy route \
  --repo "$PWD" \
  --task-id focused-fix \
  --task-file /tmp/focused-fix.md \
  --task-kind dev \
  --out .pilot-puppy/evidence/focused-fix.route.json
```

Task kinds map deterministically to generic work roles:

| Task kind | Role | Use it for |
|---|---|---|
| `plan` | `planner` | Bound a consequential or ambiguous decision. |
| `hard-dev` | `hard-ic` | Deliver a difficult implementation slice with proof. |
| `dev` | `bulk` | Make an ordinary, well-scoped product change. |
| `debug` | `debug` | Investigate one reproducible failure or unknown. |
| `review` | `critic` | Independently challenge a change or proof claim. |
| `lead` | `lead` | Own split, acceptance, and next move. |

The command reads the local roster, tries only a short local `--version` probe
when asked, and prints the selected generic role/host, same-role alternatives,
and one escalation condition. It does not start a host, create a worktree,
retry, queue, fetch, contact a service, inspect authentication, or silently
switch providers.

`--host` is a hard constraint. If that host is unavailable, Pilot Puppy blocks
instead of choosing a different one. `--availability assume` skips the version
probe and marks a native slot `unprobed`; it is useful when an operator has
already checked the host.

## Bind a route to a host run

Write a route only in the project-local evidence directory, then pass it back
to the selected native host explicitly:

```bash
pilot-puppy host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/focused-fix.md \
  --task-id focused-fix \
  --allowed-path src/fix.ts \
  --route-file .pilot-puppy/evidence/focused-fix.route.json \
  --out .pilot-puppy/evidence/focused-fix.attempt.json
```

Before launching the host, Pilot Puppy verifies that the route packet is a
regular direct evidence file and that its frozen task hash, task ID, local
roster revision/route-safe hash, and selected enabled role/host slot still
match. Any mismatch blocks before a native coding process starts.

The route packet deliberately contains only generic roles, native host
surfaces, hashes, state, alternatives, and escalation. It excludes task text,
paths, roster slot IDs, models, accounts, quota, commands, credentials,
provider payloads, and transcripts.

## What stays separate

The lead owns the `PLAN.md`, task split, proof review, merge, publishing, and
acceptance. Thermo and Ponytail are independent review disciplines, invoked as
needed; neither is a router role or a background service. Local private seat
preferences may inform the local roster, but must never enter browser status,
project evidence, or public source claims.

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
| `hard-dev` | `hard-dev` | Deliver a difficult implementation slice with proof. |
| `dev` | `dev` | Make an ordinary, well-scoped product change. |
| `debug` | `debug` | Investigate one reproducible failure or unknown. |
| `review` | `review` | Independently challenge a change or proof claim. |
| `lead` | `lead` | Own split, acceptance, and next move. |

The command reads the local roster, tries only a short local `--version` probe
when asked, and prints the selected generic role/host, same-role alternatives,
and one escalation condition. It does not start a host, create a worktree,
retry, queue, fetch, contact a service, inspect authentication, or silently
switch providers.

The current route vocabulary is `planner`, `dev`, `debug`, `review`,
`hard-dev`, and `lead`. Existing local roster aliases (`bulk`, `critic`, and
`hard-ic`) are accepted only for compatibility and are normalized before a
route packet is emitted.

`--host` is a hard constraint. If that host is unavailable, Pilot Puppy blocks
instead of choosing a different one. `--availability assume` skips the version
probe and marks a native slot `unprobed`; it is useful when an operator has
already checked the host.

## Calibration boundary

The router is a local policy tool, not a model or billing optimizer. Its useful
default is simple: send ordinary bounded implementation to the `dev` role,
reserve `hard-dev` for difficult implementation, and keep planning, review, and
lead acceptance explicit. The local roster priority makes that policy
deterministic without collecting an account, quota, token, or price signal.

Do not compare different roles on one coding task. A planner, debugger, and
builder have intentionally different outcomes. A valid optional calibration is
one role, one frozen task hash, separate clean worktrees, and two declared
native-host slots for that same role. Review only the mechanical facts: route,
allowed-scope result, proof result, lead reproduction, and elapsed local time.
Usage, tokens, cost, proprietary model, and provider-quality claims are **not
collected**.

The lead may use a real calibration to change local roster priorities with
`pilot-puppy roster prefer --role ROLE --host HOST`. Pilot Puppy never changes
them automatically, silently retries, or turns the result into a score database.

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

## Optional private native selector

If the native CLI on your own machine requires a specific selector, configure
it locally after the generic roster exists:

```bash
pilot-puppy seat init
pilot-puppy seat set --slot dev-cursor --model MODEL
```

The route command never reads this overlay. It still makes the same generic
role/host choice and writes the same public-safe packet. Only an explicit
sealed handoff can consume it:

```bash
pilot-puppy host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/focused-fix.md \
  --task-id focused-fix \
  --allowed-path src/fix.ts \
  --route-file .pilot-puppy/evidence/focused-fix.route.json \
  --use-seat \
  --out .pilot-puppy/evidence/focused-fix.attempt.json
```

`--use-seat` requires a ready route and one matching enabled native roster slot.
It fails before the native process begins when the local overlay is missing,
stale, malformed, or mismatched. It adds only a model selector for Codex,
Claude Code, or Cursor, or a profile selector for Codex. It does not query
available models, inspect auth/quota/billing, retry/fallback, or promise model
quality. The selector value and local config path never enter the route packet,
browser or status output, `PLAN.md`, or host attempt receipt.

## What stays separate

The lead owns the `PLAN.md`, task split, proof review, merge, publishing, and
acceptance. Thermo and Ponytail are independent review disciplines, invoked as
needed; neither is a router role or a background service. Local private seat
preferences may inform the local roster, but must never enter browser status,
project evidence, or public source claims.

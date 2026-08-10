# The Method

Shadow works one claimed checkpoint at a time: change the world, run the
checkpoint's declared proof, and record the result in its owning `PLAN.md`.
The adversarial pass is part of that loop. It tests whether a result is false;
it does not create another workflow or a second place to record truth.

## Attack, then refute

After a usable change and its focused falsifier exist, attack the claim through
distinct lenses. State each finding as a falsifiable claim with the affected
contract and a reproducible observation. Then try to refute that finding from
an independent path before repairing it.

```text
claim + focused proof
        ↓
attack through distinct lenses
        ↓
finding with contract + observation
        ↓
independent refutation, or repair
        ↓
re-run the original proof and record the result in PLAN.md
```

A finding is **killed** only when repeatable evidence disproves its stated
failure: for example, a fresh reproduction shows the alleged precondition is
false, or a focused test demonstrates the required behavior at the named
surface. An opinion, an unrelated green suite, or inability to reproduce once
does not kill it. A finding that reproduces, has an inconclusive refutation, or
reveals a missing proof survives as ordinary checkpoint work with its evidence
and proof in the owning plan.

## Default lenses

Use the smallest distinct set that can challenge the change. Unless a
checkpoint names a narrower relevant set, the defaults are:

| Lens | Attack question |
|---|---|
| `assumptions` | Is the claimed authority, premise, or source revision actually true? |
| `correctness` | Does the stated behavior violate its direct contract? |
| `integration` | Does a caller, boundary, or dependency fail with the change? |
| `crash_recovery` | Does interruption, retry, rollback, or stale local state break it? |
| `privacy` | Can the change expose secrets, private paths, or unapproved payloads? |
| `stranger_install` | Does a fresh, ordinary installation behave differently? |

Lenses overlap only when their attack evidence is genuinely independent. A
large change can add a domain-specific lens; a small change may use fewer
defaults when a named lens cannot apply. The record names the lenses actually
used and why an otherwise relevant one was omitted.

## Declaring preferences

`.shadow/local.yaml` names the machine-local repository default at
`method.adversarial_lenses`; a `leads` entry may name its own default lens set.
The repository set is the method default; a lead's set is a preference for
work signed by that lead. `shadow config --explain` prints the effective set
and where each value came from.

```yaml
method:
  adversarial_lenses:
    - assumptions
    - correctness
    - integration
    - crash_recovery
```

Those declarations select questions, not executors. They contain no resolved
state, do not decide whether a lead may claim, and do not bind a provider,
model, account, credential, host, task, or plan state. An absent configuration
uses the defaults above. A milestone or checkpoint may still name the smaller
set its risk needs.

## No runtime roles

A lens is a review question, not a seat, queue, worker type, or service.
Native Codex, Claude Code, and Cursor sessions remain the executors; the
computer board remains coordination; entity `PLAN.md` files remain the only
checkpoint and proof authority. Thermo and Ponytail remain review disciplines,
not runtime roles.

Do not add a roster that decides legal ownership, a router, daemon, scheduler,
credential relay, transcript store, cloud executor, or parallel status
database to perform an adversarial pass. Fan-out stays bounded and
path-disjoint; its evidence returns to the same claimed checkpoint.

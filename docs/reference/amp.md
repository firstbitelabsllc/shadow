# shadow amp — the goal is a pointer

`shadow amp` projects a paste-ready resume block for a checkpoint already
claimed by the named seat in an entity-owned `PLAN.md`. New work enters only
through `shadow throw`, which atomically claims it before returning the same
kind of packet. The pointer exists because a real goal may iterate
over ten projects and hundreds of plan rows, and no goal prompt — bounded to
one paste, default 4,000 characters — can carry that detail. The durable
detail lives in the plan; the goal block MUST be a pointer to it, plus what a
seat needs to warm-start without re-deriving state. The selected row is a
starting pointer, never the Outcome's scope or stopping condition.

## The contract

1. **Pointer first.** The block names the plan path, the ref
   (`branch@sha`), the origin, and the exact `### <milestone>` section. The
   computer board owns priority, claims, owners, and resume; the project plan
   owns task detail and proof. The block owns neither. First move is always
   fetch + read + state your ref.
2. **Owned pointer, never scope.** `--by <seat>` is required for executable
   projection. The selected checkpoint must have one root-board claim owned by
   that seat; `--task '~hash'` may narrow among that seat's claims but can never
   bypass ownership. After it is proven, reread the board, claim the next
   reachable checkpoint through `shadow throw`, and fan out path-disjoint
   claims when useful. A projected checkpoint never implies "do this and stop."
3. **Proof rides along.** The resume row's `proof:` field is in the block —
   a seat should know the bar before writing a line.
4. **Capabilities from the milestone, not a store.** The optional milestone
   `- tools:` line (see grammar § Milestone law) records applicable
   capabilities. Shadow selects the smallest relevant installed capability or
   records a native fallback in a bounded `CAPABILITIES` block. Each entry
   carries the local resolution (`present`, `absent`, `stale`, `off`, or an
   advisory `warning`), the
   selected capability, version/detail when available, the milestone reason,
   and the native fallback. Resolution is read-only and never gates the packet;
   invoking a capability never counts as proof.
5. **Person-gated rows are named** so a seat never claims one.
6. **Budget is enforced, not hoped.** Optional parts drop from the bottom
   (rails → contradictions → gates → DoD → capabilities → tools) until the block fits;
   the pointer and the resume never drop; a resume row that alone exceeds
   the budget is a hard error pointing back at READ-FIT. The char count
   prints to stderr on every run.
7. **Deterministic.** No LLM, no network, no resolved-state write. Same plan,
   local board revision, capability mounts, slot bindings, and PATH produce
   the same block. Model
   judgment stays in the native hosts, per the platform boundary.
8. **The pointer never lies about the ref.** amp reads the working tree, so
   when the plan has uncommitted edits the pointer is marked
   `+UNCOMMITTED` and the block says the named ref serves different content:
   commit and push before handing the goal to a seat. Repository metadata
   (the origin URL, the branch) is control-character-stripped and bounded —
   repo-owned data can never append its own instruction line to a block a
   person pastes into an agent.
9. **An unreadable plan is never called finished.** Row-shaped lines the
   grammar rejects are counted, and blocking `shadow lint` findings are read;
   a plan carrying either reports *the plan does not read clean* instead of
   *every task complete* (also on `shadow status`, as `Plan health:`), so no
   one chains a successor over work that merely failed to parse.

## Usage

```bash
shadow amp --entity <board-entity-id> --by codex-mac
shadow amp --repo ~/Development/resplit-ios --by codex-mac
shadow amp --repo . --task '~dd44' --by codex-mac
shadow amp --repo . --by codex-mac --max-chars 2000
```

Exit codes: `0` owned block printed; `1` no matching live claim, the claimed
checkpoint needs recovery rather than work, or the checkpoint exceeds the
budget; `2` no plan/entity or invalid usage.

## What amp deliberately does not do

- It does not copy the plan into the goal. A block that tries to be the
  plan goes stale the moment any seat writes a Progress row.
- It does not invent tooling advice. If a milestone has no `- tools:` line,
  the block has no TOOLS line — writing one is the working seat's job, in
  the plan, where the next projection picks it up.
- It does not call a model. Sharpening prose is a host's job; amp's job is
  that the pointer, resume, proof, and rails are exact.
- It does not hand planning, delegation, or review dispatch to an extension
  pack. Because one packet can resume on Claude, Codex, or Cursor, a leaf
  found only in Claude's plugin cache is source evidence, not a cross-host
  invocation. The complete pack-leaf law — compatible set, refusals,
  fallback, pack-root configuration — is the section below, stated once.
- It never repeats an unsafe pack invocation from `- tools:`. `/superpowers`
  and every non-compatible Superpowers leaf are projected as Shadow Method
  intent or fallback; ordinary project tools such as `/craft` remain byte-for-
  byte intact.

## The pack-leaf law (amp core, relocated from the retired superpowers slot)

The delegation guard never lived in a slot declaration; it is amp core and
survives the 2026-08-15 slot-set change. Amp may name only a concrete
installed whole leaf from the compatible set: `verification-before-completion`,
`test-driven-development`, `systematic-debugging`, `receiving-code-review`.
`writing-plans`, `executing-plans`, `dispatching-parallel-agents`,
`subagent-driven-development`, `using-superpowers`, `brainstorming`, and
`requesting-code-review` are refused even when explicitly requested, and the
same default-deny covers every uncatalogued leaf: the computer board, entity
plan, and Shadow host-run keep those jobs. A pack with no compatible whole
leaf falls back to the native host plus Shadow Method, and raw `/superpowers`
or refused-leaf invocations are removed from the projected `TOOLS:` line.

The pack root is configured by `SHADOW_AMP_PACK_ROOT` (an absolute path, or
`off` to disable pack inspection). This is amp-core configuration, not a slot
binding: no slot named superpowers exists. The legacy names
`SHADOW_SLOT_SUPERPOWERS` and `SHADOW_BUCKET_SUPERPOWERS` are honored behind
it for one release train, then die.

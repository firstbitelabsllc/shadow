# shadow amp — the goal is a pointer

`shadow amp` projects one paste-ready goal block from a repository-owned
`PLAN.md`. It exists because of a hard size truth: a real goal may iterate
over ten projects and hundreds of plan rows, and no goal prompt — bounded to
one paste, default 4,000 characters — can carry that detail. The durable
detail lives in the plan; the goal block MUST be a pointer to it, plus the
minimum a seat needs to warm-start without re-deriving state.

## The contract

1. **Pointer first.** The block names the plan path, the ref
   (`branch@sha`), the origin, and the exact `### <milestone>` section. Its
   standing instruction: *the plan wins* — when block and plan disagree, the
   block is stale, never the plan. First move is always fetch + read + state
   your ref.
2. **One resume row.** Selection is the cycle law: the `in_progress` row
   first, else the first `pending` row whose `needs:` are all completed,
   milestone order. `--task ~hash` targets one row explicitly.
3. **Proof rides along.** The resume row's `proof:` field is in the block —
   a seat should know the bar before writing a line.
4. **Tooling from the milestone, not a store.** The optional milestone
   `- tools:` line (see grammar § Milestone law) is projected verbatim.
   Whoever works a milestone writes down what it actually needs; the next
   seat inherits it. Pattern, not store.
5. **Person-gated rows are named** so a seat never claims one.
6. **Budget is enforced, not hoped.** Optional parts drop from the bottom
   (rails → contradictions → gates → DoD → tools) until the block fits;
   the pointer and the resume never drop; a resume row that alone exceeds
   the budget is a hard error pointing back at READ-FIT. The char count
   prints to stderr on every run.
7. **Deterministic.** No LLM, no network. Same plan, same block. Model
   judgment stays in the native hosts, per the platform boundary.

## Usage

```bash
shadow amp                       # goal block for the cwd repo's PLAN.md
shadow amp --repo ~/Development/resplit-ios
shadow amp --task ~dd44          # target one row
shadow amp --max-chars 2000      # tighter paste budget
```

Exit codes: `0` block printed; `1` no open task (mint the successor — goal
chaining) or the resume row itself exceeds the budget; `2` no plan or
invalid usage.

## What amp deliberately does not do

- It does not copy the plan into the goal. A block that tries to be the
  plan goes stale the moment any seat writes a Progress row.
- It does not invent tooling advice. If a milestone has no `- tools:` line,
  the block has no TOOLS line — writing one is the working seat's job, in
  the plan, where the next projection picks it up.
- It does not call a model. Sharpening prose is a host's job; amp's job is
  that the pointer, resume, proof, and rails are exact.

# Resplit Swappable Persistence — Planning Prompt

Authority Store: /Users/leokwan/Development/vidux/projects/resplit-swappable-persistence/PLAN.md
Target: the whole project — **PLANNING + ADDITIVE PREWORK** (no behavior-changing code)

## DECISION (2026-06-13, unanimous 8/8) — read PLAN "SHIP-TIMING DECISION"
Additive prework ships in 2.0; the SOOC/@Query **cutover is DEFERRED post-2.0**
behind an ASK-LEO-MANDATORY lane. Do NOT repoint @Query sites, build the
remote-change bridge, wire Records into any production read/write path, swap the
default ModelContainer, or flip Swift 5->6 in this lane. Records are READ-ONLY
projections; all mutation/deletion stays on the @MainActor ModelContext. SQLiteData
stays out (bug #418 open). Allowed here: more Phase-0 characterization tests, the
Tuist module boundary + protocol/in-memory-adapter interfaces with NO production
consumer.

## Operating Prompt

You are deepening the PLAN for ripping Resplit's domain layer free of SwiftData,
behind a swappable Tuist persistence module (SwiftData today; SQLiteData and
in-memory as adapters). This is the architecture Leo wants to build with an
Opus-4.8 fleet — but **NOT tonight**.

**SCOPE (updated 2026-06-13 — authority expanded).** This is a PLANNING +
PREWORK goal. You MAY do everything EXCEPT introduce SQLite/SQLiteData (the
Point-Free dependency) into the build. Allowed prework, all ADDITIVE and
dependency-free: Phase-0 safety-net tests (characterization / regression / UI),
the `ResplitPersistenceContract` protocols + plain `Record` value types, the
in-memory adapter, and wiring the existing SwiftData behind the contract.
**HARD NO: do not add the SQLiteData/SQLite SwiftPM dependency, do not import
it, keep its adapter a stub.** Reason: product dev is happening in a PARALLEL
chat/lane on resplit-ios — keep the blast radius low so the shock isn't high.
**ISOLATION (mandatory):** do prework in a git WORKTREE off resplit-ios, prefer
NEW additive files, never edit hot files the other lane is touching, never
killall xcodebuild/sims (per /bigapple swarm safety). If a change isn't
additive + collision-free, it stays a PLAN row, not a commit.
**MORE ADVERSARIAL (updated 2026-06-13):** every plan artifact AND every prework
slice gets an adversarial red-team pass — agents that try to BREAK the test
stories, the migration order, the pre-mortem, and any prework before it's
trusted. Default skeptical.

**ABOVE ALL — test-case stories are the north star.** Before and above the
architecture, the PLAN must carry concrete **Test Case Stories**: scenarios this
swappable-persistence feature unlocks with the *current* Resplit product
(receipt splitting, Live Split, folders, CloudKit private sync, the CKShare
sharing endgame). Each story states: what the user/test does → which adapter
capability it proves (in-memory determinism, SwiftData parity, SQLiteData
CKShare) → explicit pass/fail criteria. The design exists to serve these
stories; if a design choice doesn't make a story testable, it's wrong. Ground
stories in real Resplit features, not hypotheticals.

**Keep deepening until there is ≥8h of execution runway.** Planning is not done
until the PLAN queue holds rows whose summed ETA is **at least 8 hours**, each
row carrying acceptance criteria, a disjoint write scope (files/modules), an ETA
estimate, and dependency order. If the queue is thinner than 8h, the next action
is always "decompose the next coarse row / add the next missing story or design
slice," never stop.

**Coverage the PLAN must reach** (each grounded in real resplit-ios paths/modules):
- Test Case Stories (TOP — see above), with an adapter-capability matrix.
- Tuist module graph + `Project.swift` best-practices for the contract +
  adapter modules (dependency edges, composition root wiring one adapter).
- The observation layer that replaces `@Query` in the 7 view sites — the
  highest-risk piece that killed the prior big-bang attempt.
- Strangler-fig incremental migration (first vertical slice, parallel-run,
  per-step shippable/green gates) — never big-bang.
- Pre-mortem guardrail table: prior-failure-mode → concrete guardrail.
- CKShare / SQLiteData adapter fit + the fork-tracking strategy for the
  SQLiteData dependency (fork + upstream remote + rebased patch branch, SwiftPM
  pinned to the fork).
- Risk register.

## Skill Bindings
- `/vidux` — Harness Contract + PLAN/queue semantics (owns loop mechanics).
- `/auto` — fleet policy, zero-ask operational autonomy.
- `/amp` — this prompt's shape + Agentic Closeout Gate.
- `/tuist` — Tuist CLI + module/Project.swift best-practices.
- `/bigapple` — Resplit module/build context.
- `/groundtruth` — test-story realism: prove it's a REAL test, not a green-washed one.

## Mutation Rule
Update PLAN.md first (rows, sections, ETA ledger, Progress log). Mutate THIS
file only when the standing instruction changes (e.g., the planning→execution
handoff, when Leo says build it). Never put task state, branches, PRs, ETAs, or
snapshots in this file — those live in the PLAN.

## Done-State (agent-checkable; PLANNING only — no human gate)
Planning is COMPLETE when ALL are true:
1. **Test Case Stories** section holds ≥8 concrete stories grounded in current
   Resplit, each with adapter-capability mapping + pass/fail criteria.
2. Queue rows' summed ETA ≥ **8h**, each row with acceptance criteria, disjoint
   write scope, ETA, and dependency order.
3. All coverage sections above are present and concrete (real paths/modules).
4. No SQLite/SQLiteData dependency introduced; any prework done is additive,
   worktree-isolated, and collision-free with the parallel product-dev lane.
**Prework track (authorized 2026-06-13):** once the plan is solid, the loop MAY
execute dependency-free prework (Phase-0 safety net, contract protocols + Record
types, in-memory adapter) in a worktree, each slice adversarially reviewed
before trust. Introducing SQLiteData remains GATED on Leo.
**Exit-on-refire:** if a cycle finds the plan done-state met AND no further
agent-reachable prework that stays within the SQLite-exclusion + isolation
rules, exit — do not loop. Introducing SQLiteData / disruptive migration is a
separate goal Leo launches deliberately.

## Closeout
Run a final draft pass (cut proof-theater; keep what helps the next reader
decide), then end every cycle with:
`[METER ▓░N] [ETA Xh] [N pending, M in_progress, K done]`

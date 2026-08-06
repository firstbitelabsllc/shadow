# ROUND 2 RULING — Cluster: Product Surfaces

Files read: chair-position.md, r1-seat-01 through r1-seat-10, the installed `@firstbitelabs/shadow` package's `docs/reference/method.md`, and the pre-rename `agent-md-ship-20260806` worktree's `AGENT.md`.

---

## 1. Drive Packet — lanes, sessions, packet grammar, `ready|paused|blocked|done` vocabulary, `shadow-checkpoint.py`'s third vocabulary

**VERDICT: DELETE.**

Rent failed on every axis. It is a second coordination grammar for the identical subject — "bounded work item with a proof, claimed by a seat, accepted mechanically" — and the two mechanisms never touch: r1-seat-05.md verified by grep that 1,421 lines of Drive code contain zero references to CLAIM/PROOF/DONE or checkpoint rows, and that `drive accept` merges work while flipping no row, violating method.md's own claiming law ("only a seat holding a PROOF line may flip"). The packet is JSON inside an HTML comment inside the markdown-authority file — invisible to PLAN-LINT, so the product's own lint cannot see 54% of its own coordination surface (r1-seat-05.md B). The board question kills it independently: mid-flight lane state exists only in session JSON, so the board either renders a non-derivable rollup (banned by method.md line 20) or shows half the truth at exactly the moments Leo watches (r1-seat-05.md Q1). Three state vocabularies for one product is not a concept; it is drift with a version number. Path-disjoint batching demotes to one docs sentence: "accept up to three rows whose touched paths are disjoint."

## 2. Clean-checkout mechanical acceptance (the ~150-line engine inside Drive)

**VERDICT: FOLD — into core #6 (a flip requires a proof line).** Exact sentence: *"`shadow accept --row <id>` reruns that row's `proof:` in a clean checkout and, on green, flips the row with its proof line in the same commit — the only code path that may flip a row."*

This is the one thing Drive earns: code that *refuses*, where the Method's "acceptance is mechanical, never a claim" is prose an LLM can rationalize around (r1-seat-05.md position). Today's C3~w5d9 lie is the proof of need — a DoD row sat Verified while the shipped package lacked AGENT.md, because the proof asserted plumbing, not world-state, and nothing mechanical ever re-checked it (r1-seat-10.md A, r1-seat-07.md A). Folding acceptance into the row grammar makes the claiming law enforced for the first time and gives PLAN-LINT sight of everything, per r1-seat-05.md's proposal. Worded to depend only on core-7: it survives whether or not the concurrency appendix (hash addressing, CLAIM bookkeeping) stays deferred. Acceptance remains lead-seat-only — r1-seat-09.md Q2 is right that no cheap lane may run destructive-adjacent accept/merge, and r1-seat-02.md's fold-throughput ceiling is a real cost this tribunal accepts rather than weakening the clean-checkout reproof (the alternative reinstates the false-green disease the memory index documents).

## 3. Roster / route / seat subsystem (1,777 lines, six role definitions)

**VERDICT: DELETE.**

It refuses to answer the only routing question Leo actually has. roster.md's own text: "does not choose a provider or model, measure account quota... " — while provider/cost choice is the entire point of the cheap-workforce steer, and it already lives outside Shadow in `~/.config/leo/routing.json` (r1-seat-05.md C). What route emits — a role label plus host that "prints the choice and then stops" — is already encoded for free in the CLAIM line's `seat=` token. It is a second router in a product whose preamble law bans second routers. It also routes wrong: no `ui` task-kind means it will hand a hero-image row to a worker that cannot see its own output and return a receipt the Method counts as proof (r1-seat-01.md Q1), and its roles are meaningless for the non-code work in Leo's #1 entity (r1-seat-08.md B). Two working fragments survive as demotions: **docs sentence** — "a CLAIM's `seat=` names provider and host (`seat=codex-dev-1`); provider selection lives outside Shadow" — and **one flag**: the frozen-task-file/revision preflight stays on `shadow host run`. That is a preflight check, not a subsystem.

## 4. The board

**VERDICT: KEEP-CORE (chair #7 confirmed) — as a product feature, with two contract amendments and one ambition deleted.**

Rent paid: it is the only surface where Leo sees derived truth without reading a 566KB file. But as shipped it renders the prettiest possible view of corrupt data: it would show "Mode: Close" over the plan whose DoD proof was false today, and it best-effort-parses plans whose grammar has drifted, making drift invisible (r1-seat-10.md Q2, r1-seat-06.md C). Amendments, each one sentence in method.md §Board:

- *"A card renders the plan's mechanical-lint verdict (GRAMMAR chip with finding count) and the age of the oldest CLAIM without a PROOF; a plan that fails to parse renders as a red card, never as best-effort counts."* This is the stress seat's demand granted — these are the only two signals that would have caught the C3 lie, and they are derived-at-read from the same files, so no second store is created.
- *"A card projects only the file carrying the `- Entity:` line; a stamped plan whose body disclaims its own authority renders its `## Contradictions` count on the existing decision-waiting chip."* This answers r1-seat-04.md Q1 mechanically, with zero write surface.

**Deleted ambition:** the board as anyone-but-Leo's GUI. r1-seat-08.md Q2 forced the choice and the answer is: the board is the Method's mirror. Nicole's surfaces remain `/nicole-desk` and Reminders; no chip-translation layer gets built. The Drive-packet rendering dilemma (r1-seat-05.md Q1) dissolves with ruling 1. Sequencing caveat stands as a docs note, not a concept: the board renders nothing until plans carry the Entity line, so board work behind the entity-stamping migration is polish-before-P0 during the launch window (r1-seat-09.md Q1).

## 5. Steering shape

**VERDICT: FOLD (chair confirmed) — into one behavior sentence, with the `- Priority:` field folding into the Entity-line concept (#7), not minted as a new concept.** Exact sentence: *"Steering is one multiple-choice prompt with a default — offered at session start, on a DoD-row flip, or when asked, never per checkpoint; default-if-silent is the highest-`Priority:` entity's ready row, and a silent default is logged as one Progress line."*

The chair's fold ("it's a multiple-choice question with a default") is right but incomplete: r1-seat-02.md proved two live defects the fold sentence must carry or the fold is a lie. First, per-checkpoint cadence at portfolio scale is the heartbeat ledger reborn (70.4%-heartbeat precedent) — an unread stream where every unanswered steer silently executes Default A. Second, "ranks by entity priority" references a priority defined nowhere greppable, so under the letter of the current law a StrongYes `(S, Close)` row legally outranks a Snowcubes `(M, Spike)` row — the ranking function steers into the one entity Leo put on HOLD (r1-seat-02.md B). One optional brief line in the existing `Entity:`/`Mode:` grammar family fixes it at zero new surface; the pending steer renders on the board's existing decision-waiting chip. Steering stays what method.md already claims it is — a prompt shape, not a system — and nothing about it remains a product feature.

## 6. Langfuse seam

**VERDICT: DELETE.**

The stress seat's cross-examination question answers itself and no seat defended the other side. privacy.md's closed schema — random IDs, role/host family, terminal state, duration bucket, nullable booleans; never row hashes, filenames, modes, or plan text, with events firing only on route/host receipts — can *attribute* none of the three real failure classes: double-flips invisible (no hash), bloat invisible (no filename/size), mode races completely dark (no mode field, no chief-chat events) (r1-seat-10.md C, Q1). It could only ever see "Drive lane fevers," and rulings 1 and 3 delete both of its event sources — a telemetry seam whose emitters no longer exist is a second status store in waiting. Widening the schema to make it useful would break the metadata-only privacy promise that justified it. Diagnosis instrumentation goes where the stress seat put it: in-repo (git history, grep, the deterministic crash rig), and any future cross-host fleet telemetry belongs to the OTel substrate that already exists outside Shadow. Not DEFER — a deferred seam invites schema creep at reactivation; if telemetry is ever needed, it re-enters as a fresh proposal against the thin-surface law. privacy.md's field-vocabulary gate survives only as the board sentence already in method.md ("closed vocabularies or the same privacy gates as plan titles").

---

## Cluster summary

Product features remaining: **the read-only board (with lint chip + stale-CLAIM age + red-card refusal)**, **`shadow accept --row`**, **one preflight flag on `shadow host run`**. Demoted to docs: path-disjoint batching, seat-naming convention, card-projection rule, board sequencing note. Dead: Drive Packet lifecycle and all three extra state vocabularies, roster/route/seat, the Langfuse seam, the board-as-household-GUI ambition. Net: roughly −2,500 lines of coordination code and my cluster contributes zero new concepts to the core-7 — two folds land as single sentences inside existing core items.

## Dissent risk

If Drive's session/lock machinery was silently load-bearing for parallel native-host runs on one Mac (xcodebuild/SWBBuildService contention), deleting the packet before the path-disjoint preflight lands on `shadow accept` reinstates the build collisions the fences currently prevent. If the mechanical lint behind the board's red-card rule is itself buggy, every plan renders red and Leo's only GUI goes dark — the refusal rule makes the read-only board a de facto enforcer, which is exactly the trap r1-seat-06.md Q1 warned both directions about. And if a genuine cross-host failure class emerges after Langfuse dies, in-repo grep cannot see cross-repo patterns and telemetry will be re-litigated from zero during an incident rather than in a tribunal.
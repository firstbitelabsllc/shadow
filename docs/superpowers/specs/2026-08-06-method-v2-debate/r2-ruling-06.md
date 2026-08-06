# CHIEF JUDGE — FINAL VERDICT (Shadow Method Simplification Tribunal, Round 2)

Basis: the debate scratchpad's `chair-position.md`, `r1-seat-01.md` through `r1-seat-10.md`, and the five cluster rulings. Chair's Approach A (core rewrite) is adopted. One binding condition carried from the gates ruling: **every DELETE of prose law is void unless `scripts/shadow-lint.py` lands in the same commit** — Shadow is 0-for-1 on shipping the file it points at (AGENT.md missing from the v3.0.0 npm package, found independently by all ten seats).

---

## 1. THE VERDICT TABLE

| # | Concept | Ruling | Rent — why it lives or died |
|---|---|---|---|
| 1 | Plan file = markdown authority | **KEEP-CORE** | Only store that survived every attack; everything else derives from it. |
| 2 | Checkpoint row + `proof:` | **KEEP-CORE** | Kills "agent claims done" — the 70.4%-unverifiable ledger and today's C3 lie are the counterfactual. |
| 3 | `~hash4` row IDs | **KEEP-CORE** (recipe folded) | The row's address — `needs:`, proof lines, archive tombstones all dereference it. |
| 4 | sha256 mint recipe | **DELETE** | Nobody runs it; "4 base36 chars, unique, lint-checked, re-mint on collision" is the honest core. |
| 5 | `needs:` | **KEEP-CORE** | Sole definition of "ready"; makes P0-before-polish executable law, not vibes. |
| 6 | `from:` | **FOLD** | Gates nothing; lineage is an event — one Progress line naming the origin row. |
| 7 | `size:` | **DELETE** | No decision ever consumed it; "a checkpoint fits one cycle, bigger = milestone" says it all. |
| 8 | `CLAIM` lines | **DELETE** | Can't detect the collision it exists for (identical edits merge silently); flagship count = 0. Replaced by single-writer law. |
| 9 | `PROOF` lines | **KEEP-CORE** | Highest-rent token in the product; the only thing that exposed today's shipping lie. |
| 10 | `DONE` lines | **FOLD** | Flip IS done: "a row flips completed only in the same commit as its PROOF line." |
| 11 | One-claim-per-loop | **FOLD** | "A cycle drives one checkpoint to a recorded result before starting the next" — finish-before-start, Leo's #1 pain. |
| 12 | Four-mode vocabulary (Spike/Defer/Challenge/Close) | **DELETE** | Unwritten in the wild, race-blind, and its one ranking use steered into a HOLD entity. |
| 13 | Spike | **FOLD** | Broad exploration is boxed and must end in a written keep/kill/promote verdict. |
| 14 | Defer-as-mode | **FOLD** | Defer is a write: row + wake predicate; no predicate = deletion in denial. |
| 15 | Challenge | **FOLD** | Interrogation + written demotion survive verbatim under Broad; the noun dies. |
| 16 | 4×4 transition table | **FOLD** | Two postures = two edges: paired Progress line in the flip's commit + re-read posture before it. |
| 17 | Close / "Jordan" | **KEEP-CORE** | The crown jewel — the only concept with a checkable entry (named harness) and exit (proof per DoD clause). Word "Close" stays on every surface. |
| 18 | Two postures Broad/Close | **KEEP-CORE** | Leo's own fragment ("broad vs closing time") returned to him. |
| 19 | PLAN-LINT six lettered passes | **FOLD+SPLIT** | Prose law enforced by the defendant; mechanical checks go to `shadow-lint.py`, judgment residue is one sentence. |
| 20 | Close coverage matrix + 6 gates + status vocabulary | **FOLD** | The Verified matrix passed today's false close; one sentence (proof line per clause, re-observed, or owner handoff) does the real work. |
| 21 | Lesson delta | **FOLD** | The fold-out valve works (Leo's memory corpus is proof); the stop-the-close machinery never fired once. |
| 22 | Adversarial gate pair | **KEEP-CORE** | Only write-time check in the product; killed two midnight ideas tonight; absorbs old pass D. |
| 23 | `- Entity:` line | **KEEP-CORE** | The entire entity mechanism and the board's only data source; its absence let a web proof flip an ios row unlinked. |
| 24 | `- Loop:` line | **FOLD** | Derivable from Entity; write only when it differs. |
| 25 | `- Milestone:` brief line | **FOLD** | Stored rollup, already caught lying live; derive from first open DoD. |
| 26 | Milestone law (### + 2–7 rows + one DoD) | **KEEP-CORE** (one sentence) | Close is undefined without a DoD anchor; caught M1 shipping without one. |
| 27 | M-id machinery (`M2a` splits, never-reuse) | **DEFER** | Nothing references milestones by M-id today; the heading is the id. |
| 28 | `## Deferred` + wake | **KEEP-CORE** | How the Method says no without losing work; deletes a whole mode. |
| 29 | `## Contradictions` | **KEEP-CORE** | Pays rent today (dual-authority resplit mess); demotions and gate hits need a home. |
| 30 | Append-only `## Progress` | **KEEP-CORE** | The audit substrate; the rule-writer's own violations convict enforcement, not the law. |
| 31 | Archive-on-Close | **KEEP** (rides Close) | A finished version whose receipts squat in the working file is not finished; moves only, never regenerate. |
| 32 | Mass thresholds (64KB/96KB, line caps) | **DEFER** | Archive-on-Close is the live drain; blocking thresholds wake at the truncation cliff. |
| 33 | Drive packet / lanes / 3 state vocabularies | **DELETE** | Zero code contact with the row grammar; invisible to lint; third vocabulary for the same subject. |
| 34 | Clean-checkout mechanical acceptance | **FOLD** | The one thing Drive earns: `shadow accept --row` — code that refuses, the only path that flips a row. |
| 35 | Roster / route / seat (1,777 lines) | **DELETE** | Refuses to answer the only routing question Leo has (provider/cost, which lives in routing.json). |
| 36 | The board | **KEEP-CORE** | Leo's one derived-truth surface — amended: lint chip, red card on parse failure, never best-effort; not Nicole's GUI. |
| 37 | Steering system | **FOLD** | One multiple-choice prompt with a default, 3 triggers, silent default logged; `- Priority:` line fixes the HOLD-entity misroute. |
| 38 | Langfuse telemetry seam | **DELETE** | Cannot attribute any of the three real failure classes; its event sources are deleted above. |
| 39 | Typed proof classes (`cmd`/`read`/`gate`) | **KEEP** (inside core #2) | Makes honest UI/ops/external proof legal and prose proof a regex finding; `gate <owner>` replaces LEO-GATED. |

**Net: ~28 shipped concepts → 8 core + 12 fold-sentences + 3 deferred + everything else dead.** Roughly −2,500 lines of coordination code.

---

## 2. THE CORE COUNT: 8 (target ≤9 — met)

1. **The plan file** — one markdown authority per repo, one writer at a time.
2. **The checkpoint row** — verifiable state + typed `proof:`, addressed by `~hash4`, ordered by `needs:`, flipped only with its PROOF line in the same commit.
3. **Two postures** — Broad and Close; flips are written, paired, same-commit.
4. **Defer is a write** — row + wake predicate, never a state.
5. **The gate pair** — "why vs just exploring" + "what does this contradict," with the contradiction auto-block; lands in `## Contradictions`.
6. **Close** — the harness defines done; proof line per DoD clause, lesson folded, receipts archived, `shadow accept` as the mechanical flip.
7. **The milestone** — `###` heading, 2–7 rows, exactly one DoD that flips last.
8. **Entity line + read-only board** — entity is a grep result; the board derives, lints, and refuses to prettify.

---

## 3. AGENT.md v2 — FULL DRAFT

```markdown
# AGENT.md — the Method, v2

One plan file per repo. One writer at a time. Everything below is checked by
`shadow lint` or it does not count.

## The core

1. **The plan file.** `PLAN.md` at the repo root is the only authority —
   markdown, greppable, no second store. One seat writes a plan at a time;
   a second writer is a Contradictions row, not a merge.

2. **The checkpoint row.** A row is a state the world reaches, with a `proof:`
   that can refuse bad work — `cmd <runnable>`, `read <artifact/url +
   expected observation>`, or `gate <owner> resume: <predicate>`. No proof,
   no completed, ever. A checkpoint fits in one cycle; anything larger is a
   milestone. A cycle drives one checkpoint to a recorded result before
   starting the next. A row flips completed only in the same commit as its
   PROOF Progress line; `shadow accept --row` reruns the proof in a clean
   checkout and is the only code path that flips a row.

3. **Two postures.** `Mode: Broad` or `Mode: Close`. Broad is thinking time:
   exploration is boxed up front and ends with a written keep / kill / promote
   verdict — a box past its end with no verdict is a lint finding; questions
   and contradictions get named, and the decision each resolved into gets
   written. Close is finishing time: entered only with a named harness. The
   posture changes only via a paired Progress line landing in the same commit
   as the flip, and the flipping seat re-reads the posture line immediately
   before that commit. A surfaced contradiction demotes Close to Broad in
   writing — never silently; repair the proof there, re-enter Close. The
   closer never rewrites the exam mid-sitting.

4. **Defer is a write, never a state.** One row: what | why-not-now |
   wake: <predicate>. A row without a wake predicate is deletion in denial.

5. **The gate pair.** Before any row lands: "is this needed, or am I just
   exploring?" and "what does this contradict?" A row that contradicts a
   MUST/NEVER in standing knowledge, or treats a person-gated item as
   agent-completable, blocks until the plan is edited — never the knowledge
   diluted. Contradictions live in `## Contradictions` and leave only via a
   Progress line citing evidence.

6. **Close = the harness defines done.** Closing appends one proof line per
   DoD clause: named check + observed result, re-observed from fresh state
   (commands rerun; artifacts and external verdicts re-read — actually
   looked at, not the caption), or a named owner handoff with a resume
   predicate. A clause unaccounted means the plan does not close. Close's
   commit folds one lesson into standing knowledge (or `LESSON none — why`)
   and moves the milestone's receipts to the archive. When every agent-side
   row is proven and the DoD sits owner-gated with a handoff, the plan
   closes on the agent side and the successor goal is minted — never hang
   waiting on a human click.

7. **The milestone.** A `###` heading over 2–7 rows plus exactly one `(DoD)`
   row, which flips only after every sibling. The current milestone is
   derived at read time — never stamped. Any structural edit lands with a
   paired Progress line naming its trigger.

8. **Entity + board.** Every plan carries `- Entity:` (optionally
   `- Priority: 1-5`). An entity is a grep result, not a file. The board is
   read-only, derives everything at read time, renders the lint verdict on
   every card, and shows an unparseable plan as a red card — never
   best-effort counts.

## Folded behavior — one sentence each
- Steering is one multiple-choice prompt with a default — at session start,
  on a DoD flip, or when asked, never per checkpoint; default-if-silent is
  the highest-Priority entity's ready row, logged as one Progress line.
- Discovered work becomes a new row in the same cycle; its paired Progress
  line names the row it came from.
- Before honoring a posture flip, run `shadow lint`, then ask of the diff:
  does any row duplicate another, and can each proof refuse bad work?
- The loop skill is `/<entity>-loop` by derivation; write `- Loop:` only
  when the real loop differs.
- Row IDs are four base36 chars, unique in the plan, checked by lint; on
  collision, re-mint.

## Appendix
Same-plan concurrency is unsupported until `shadow accept` is the only flip
path; hash-mint hardening, M-ids, CLAIM bookkeeping, and mass thresholds
sleep in `docs/appendix-deferred.md`, each with a named wake trigger.
```

---

## 4. GRAMMAR v2 — THE FILE CONTRACT

```
PLAN.md sections, in this order:

## Operator Brief
- Entity: <name>              required; the entity is the grep across plans
- Mode: Broad | Close         required; only legal values
- Priority: 1-5               optional; steering-default rank
- Loop: /<skill>              only when it differs from /<entity>-loop

## Checkpoints
### <milestone heading>       2–7 rows + exactly one (DoD)
- [pending|in_progress|blocked|completed] <state the world reaches> ~ab12
    | proof: cmd <runnable>  | needs: ~cd34
- [pending] <...> ~ef56 (DoD) | proof: read <artifact/url> -> <observation>
  Proof classes: cmd | read | gate <owner> resume: <predicate>.
  Bare prose proof = lint finding. IDs: 4 base36 chars, unique in plan.

## Deferred
- <what> | <why not now> | wake: <predicate>

## Contradictions
- <what contradicts what> | provisional winner | opened <ts>

## Progress          append-only, newest at bottom, timestamps monotonic
- <ts> ~ab12 PROOF <check> -> <observed result>     same commit as the flip
- <ts> POSTURE Broad->Close | harness: <name>       same commit as Mode edit
- <ts> STRUCT <edit> | trigger: <why>
- <ts> STEER auto <option> | <reason>

ARCHIVE — the closing commit moves the milestone's ### block, its Close
proof lines, and its Progress lines to docs/plan-archive/<slug>.md, leaving
one tombstone row. Moves only. Deletion and regeneration are banned.

LINT — scripts/shadow-lint.py, exit non-zero; runs in the test gate and
before any posture flip is honored. Checks: IDs unique, needs: resolve,
proof present and legally classed, one DoD per milestone, DoD never flips
before siblings, Deferred rows have wake:, Mode value legal, Progress
timestamps monotonic, changed core files map to a row, no secrets in proof
lines, read-fit warning on any line >2,000 chars.

BOARD — read-only projection of Entity: greps. Card = counts + lint chip +
Contradictions count + age of oldest unproven flip. No parse = red card.
```

---

## 5. OPEN DISSENTS — the three rulings most likely wrong

**D1 — Deleting CLAIM (tokens ruling #5).** If the portfolio genuinely goes multi-seat on one plan before `shadow accept --row` ships, we deleted the only — however leaky — intent marker, and double-work returns with no trace at all. **Reactivation trigger:** the first verified double-work incident (two seats commit against the same row), or any decision to run a second writer on one plan. The fix is mechanical, not prose: ship `shadow accept` as the flip path first; never reinstate CLAIM as a verb agents can rationalize around.

**D2 — Deferring mass thresholds (sections ruling #9).** Archive-on-Close only drains plans that close; the moussey/umbrella pattern (566KB, 133 lines silently truncated by Read) is a plan that never closes, and the deferred trigger depends on a reader noticing silent truncation — exactly what readers don't notice. **Reactivation trigger:** any plan with a line >2,000 chars or a file that no longer fits one untruncated Read while no milestone is closable — that day, the mass checks flip from lint warning to blocking finding, no debate needed.

**D3 — Folding Spike into Broad (modes ruling #2).** Under one Broad posture, exploration and interrogation blur, and an agent can spike forever while calling it "broad work" unless the box-verdict sentence has real teeth in the lint script. **Reactivation trigger:** two consecutive Close entries on any entity where Broad-time exploration produced no written keep/kill/promote verdict — reinstate the explicit exploration box (bounded end + forced verdict) as a first-class grammar item. Cheap revert: the folded sentences ARE the old modes.
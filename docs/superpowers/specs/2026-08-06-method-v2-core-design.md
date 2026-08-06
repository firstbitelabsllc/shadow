# The Method v2 — core design (tribunal spec, awaiting operator review)

Status: **DESIGN — complete, awaiting operator review.** Produced by a
three-round adversarial debate (2026-08-05→06): ten Round 1 seats across
/thermo /ponytail /brand-resplit /shadow lenses, a five-judge simplification
tribunal plus chief judge in Round 2, and four Round 3 cross-examiners (all
completed; the session-limit interruption was resumed from cache). Full
records: `2026-08-06-method-v2-debate/`. Binding operator steer: *"this
method shouldn't bake TOO many concepts."*

Nothing in this spec changes shipped behavior until the operator approves it
and an implementation plan lands. One Round 1 finding was urgent enough to
ship immediately and already did: AGENT.md was missing from the npm package
(v3.0.1, PR #252).

## Verdict

The shipped Method carries ~28 named concepts. The tribunal ruling, adopted
from the chair's Approach A: **8 core concepts + 12 folded behavior
sentences + 3 deferred items; everything else deleted** (~2,500 lines of
coordination code). One binding condition from the gates ruling: **no
deletion of prose law lands without `scripts/shadow-lint.py` landing in the
same commit** — prose enforcement is proven aspirational (the flagship plan
violated its own lint on day one).

### The core eight

1. **The plan file** — one markdown authority per repo, one writer at a time.
2. **The checkpoint row** — verifiable state + typed `proof:` (`cmd` |
   `read` | `gate <owner> resume:`), addressed by `~hash4`, ordered by
   `needs:`, flipped only in the same commit as its PROOF line.
3. **Two postures** — `Mode: Broad | Close`; flips are written, paired,
   same-commit ("broad vs closing time" was the operator's original phrase).
4. **Defer is a write** — row + wake predicate, never a state.
5. **The gate pair** — "why vs just exploring" + "what does this
   contradict," landing in `## Contradictions`.
6. **Close** — the harness defines done: proof line per DoD clause,
   re-observed from fresh state; lesson folded or `LESSON none`; receipts
   archived; owner-gated DoD closes agent-side with a handoff.
7. **The milestone** — `###` heading, 2–7 rows, exactly one `(DoD)` row that
   flips last; status derived, never stored.
8. **Entity line + read-only board** — entity is a grep result; the board
   derives at read time, renders the lint verdict per card, and shows
   unparseable plans as red cards, never best-effort counts.

The full per-concept verdict table, the complete AGENT.md v2 draft, and the
grammar v2 file contract are in
`2026-08-06-method-v2-debate/r2-ruling-06.md` (chief judge). Cluster
rationale: r2-ruling-01 (verification), -02 (modes), -03 (surfaces),
-04 (structure), -05 (row tokens).

### Round 3 amendments now folded into the ruling

- **Postures** (`r3-crossexam-postures.md`): the two-posture collapse stands,
  amended — the exploration box becomes enforceable grammar: two typed
  Progress heads (`BOX ~hash … | ends: <date>` and
  `VERDICT ~hash keep|kill|promote -> <line>`) plus four named lint checks
  (BOX-NO-END and BOX-EXPIRED-NO-VERDICT blocking; CLOSE-OVER-OPEN-BOX
  refusing the posture flip; ORPHAN-VERDICT warning). This discharges
  dissent D3 mechanically.
- **Roster** (`r3-crossexam-roster.md`): deletion affirmed; two surviving
  demotion fragments reworded so they no longer dereference deleted grammar
  (provider/model/cost selection lives outside Shadow; the frozen-task
  SHA-256 preflight survives roster-free; bare `shadow host run --host X`
  is already the complete sealed path — zero new code required).

### Notable deletions (with their reactivation triggers)

- **CLAIM/DONE bookkeeping** — deleted; git merges identical edits silently,
  so CLAIM cannot detect the collision it exists for. Reactivates on the
  first verified double-work incident; the fix is `shadow accept --row` as
  the only flip path, never prose.
- **Four-mode vocabulary + 4×4 transition law** — collapsed to the two
  postures; Spike/Challenge survive as folded sentences (boxed exploration
  with a forced keep/kill/promote verdict; written demotion).
- **Drive packet/lane vocabulary** (#33/#34) — DELETE, **amended with two
  binding conditions** (`r3-crossexam-drive.md`): the deletion is void unless
  the same release ships `shadow accept --row` carrying Drive's
  `create_lead_review_worktree` + `lead_review_passes` engine verbatim, and
  the same closeout rewrites PLAN.md's pending multi-lane successor row to
  the composed path. The cross-exam also corrected the record: Drive is
  serial (a for-loop over ≤3 lanes), zero real packets exist in the wild,
  and v2.2.1's hardening was Drive defending against its own bookkeeping —
  a spike ending in kill-with-lesson, not churn.
- **roster/route/seat (1,777 lines)** (#35) — DELETE **as amended by the
  completed Round 3 cross-exam** (`r3-crossexam-roster.md`): the deletion is
  affirmed but must land in the same commit as the Drive change with the
  full excision manifest (bin dispatch, release manifest, host.py route
  plumbing); bare `shadow host run --host <name>` is already the shipped
  roster-free sealed path, so zero new code is required.
- **Langfuse seam** (#38) — DELETE **AFFIRMED** (`r3-crossexam-langfuse.md`):
  the seam has emitted zero events in its entire life (off by default, never
  configured, and its emitters die with #33/#35); non-attribution is
  constitutional (privacy.md bans every field the failure classes need).
  The stress-test observability story is the deterministic crash rig
  (`tests/test_method_stress.py`), git history as the attributed trace
  store, and the existing Grafana/Phoenix substrate for any future fleet
  telemetry as a fresh proposal.
- **`size:` tokens, sha256 mint recipe, M-id machinery, mass thresholds,
  stored `- Milestone:` line, `- Loop:` line (when derivable)** — deleted,
  folded, or deferred per the table.

## Operator decisions (default-if-silent stated)

- **D-1 Account pinning:** A (default) — no account/profile surface in
  Shadow; provider/model/account selection lives in delegate/routing.json/
  env. B — keep one dumb `--profile` passthrough (~15 lines). Flip to B only
  when a sealed run needs a pin env config cannot express.
- **D-2 Langfuse:** A (default, per the affirmed cross-exam) — accept the
  deletion; observability = the deterministic stress rig + git history +
  the existing Grafana/Phoenix substrate. B — keep the seam anyway.
- **D-3 Drive's last outing:** A (default) — delete now under the binding
  conditions; zero real packets exist and the evidence is sufficient. B —
  run one bounded 2–3-lane Drive session on a real repo first and fold the
  receipts; reopen #33 only if the batch measurably beats the composed
  path. Silence = A.
- *(resolved)* Two postures vs four modes: stands as amended — the BOX/
  VERDICT grammar and lint checks make the collapse enforceable.

## Next step — the operator gate

The debate is complete. Remaining sequence:

1. **Operator reviews this spec** (the brainstorming user-review gate) and
   rules D-1 (account pinning; default: none in Shadow), D-2 (Langfuse;
   default: delete), D-3 (Drive's last outing; default: delete now).
2. On approval: superpowers:writing-plans → one implementation plan for the
   v2 rewrite — AGENT.md v2 + grammar v2 (with BOX/VERDICT heads) +
   scripts/shadow-lint.py (the binding condition) + `shadow accept --row`
   carrying Drive's clean-checkout engine + the amended deletions with
   their excision manifests — executed as Method-shaped checkpoints under
   `Mode: Close`.

# Chief-of-staff briefing

The v4 Briefs view is a pure, safe projection of the active milestone. It
shows exactly four calm fields in this order:

- **Outcome** — the explicitly human `Milestone` field, or legacy `Outcome`.
- **Now** — the human `Next` field, or a fixed sentence derived from state.
- **Risk** — the human `Risk` field, otherwise only blocked/risk counts.
- **Decision** — the human `Decision` field only while the active milestone
  has a current or next gate; otherwise a fixed sentence.

Only those explicit `## Brief` fields cross into Briefs; arbitrary milestone,
checkpoint, proof, and progress prose never does. Row ids, paths, hashes,
refs, commands, and known provider/model labels in a human field are withheld.
Plan authors keep all other provider/model choices in detailed task or proof
text; the explicitly human fields are the semantic publication boundary.
The detailed Board keeps milestone, checkpoint, state, count, and proof detail.
Neither view is authority: the computer board owns coordination and each
entity `PLAN.md` owns milestone and proof meaning.

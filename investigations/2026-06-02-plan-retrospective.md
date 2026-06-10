# Vidux Plan Retrospective — What 94 Plans Tell Us We Consistently Don't Do Well

**Date:** 2026-06-02
**Scope:** Every PLAN.md in the vidux repo (94 files, ~14,000 lines, ~61 top-level projects + ~33 task subplans across active + archived) plus the doctrine layer (SKILL.md, DOCTRINE.md, ENFORCEMENT.md, LOOP.md, INGREDIENTS.md, the recipes, and the one prior postmortem).
**Audience:** HQ — for proposing core improvements to long-horizon agentic coding, vidux-style.
**Method:** 16-agent parallel forensics fan-out (one set of readers per project cluster, blind to each other) + 2 doctrine-baseline agents, synthesized, then each candidate pattern adversarially verified against the corpus for "genuinely recurring (≥3 projects) vs over-generalized." Cross-checked against an independent quantitative grep scan run by hand. No claim survives here without a receipt.

> This document is read-only intelligence. It changes no code and ships no PR. It is the 50% — front-loaded thinking — about the discipline itself.

---

## TL;DR — the one thing to take to HQ

**Vidux does not have a knowledge problem. It has a closure-and-enforcement problem.**

Nearly every failure mode in the corpus is one vidux has *already written a rule about*. The doctrine (14 principles, ~15 recipes, 4 enforcement hooks) is genuinely excellent — and it is largely a graveyard of past failures, each principle a fossil of something that once went wrong. The consistent gaps are not in what vidux *knows*; they are in three places where the loop doesn't close:

1. **Enforcement is soft where it matters most.** The disciplines that decide trust — "never mark `[completed]` without verification," drift reconciliation, closeout — are enforced by *prompt* hooks (reminders the model can rationalize past under token pressure), not *command* gates. The repo's own ENFORCEMENT.md admits "instructions degrade first." They do.
2. **Process fixes get written, not landed.** Principle 6 ("every failure produces a process fix") is honored at the *authoring* step and abandoned at the *shipping* step. The clearest receipt: the one formal postmortem in the repo (2026-04-09 PLAN.md clobber, severity High) produced 3 P0 + 4 P1 action items — and ~8 weeks later **none of the P0 plan-integrity guards exist** (no `.gitattributes` rule, no `_plan_snapshot`, no `.plan-taskcount` sidecar, no "main-authoritative" rule in SKILL.md).
3. **Doctrine accretes; it is never pruned.** SKILL.md is 1,282 lines and the calibration example-bank has grown to row 1,440 across passes 2/6/10. The repo has `the-rip-pattern` recipe for ripping out UI bloat — and applies nothing equivalent to the doctrine itself. More rules that degrade under pressure is not the fix for rules that degrade under pressure.

The frontier for "best-in-class long-horizon agentic coding" is **mechanical closure**: turn the highest-trust disciplines from prose reminders into things that physically cannot be skipped, make process-fix follow-through a tracked queue, and prune doctrine on the same cadence it grows.

*(Recurring-gap detail and the full proposal set are integrated below from the verified forensics pass.)*

---

## What vidux genuinely does well (so the rest is credible)

These are strengths, verified across the corpus — not throat-clearing. Keep them; they are the moat.

- **The plan spine is real and near-universal.** 61/61 top-level project plans carry a `## Progress` section; 61/61 carry a `## Decision Log`; 49/61 have an `## Evidence` section; 51/61 have `## Constraints`. The "plan is truth / state lives in files" doctrine is not aspirational — it shows up in the actual files at high rates. This is rare and valuable; most agent setups have nothing like it.
- **Stateless-resume design works.** Plans are written for a next agent who knows nothing. The structure (Purpose → Evidence → Constraints → Tasks → Decision Log → Progress) means a cold agent can resume. The SessionStart/Stop hook pair operationalizes it.
- **Escalation discipline closes.** `ASK-LEO.md` Q1/Q2 show the full open→answer→ACTED loop working, with merge SHAs and timestamps as receipts. When the human-in-the-loop path is used, it resolves cleanly.
- **The doctrine is self-extracted from real receipts.** Every principle and recipe cites a concrete prior failure ("swiftify-v4 inverted the ratio," "an Acme automation discovered 14 polish tasks"). This is the right way to build doctrine — vidux mines its own history. The problem (below) is what happens *after* a rule is written, not how rules are born.
- **Duplicate-plan recovery exists and is used.** 20 plans carry a SUPERSEDED banner; the parallel-session reconciliation pattern (fold-into-canonical + archive + banner) is documented and applied (e.g. semantic-music-understanding's 2026-05-22 reconciliation section).
- **The system sometimes catches its own hallucinations.** `leo-backend-role-definition` carried 14 source-cited research slices and *self-corrected two fabrications mid-run* (a fake PR authorship, a false master-branch claim). That an agent flags its own false claims at all is rare — the raw material for pattern P10's fix already exists; it just isn't promoted to a reflex.
- **Read-only fan-out produces genuinely deep artifacts.** `ocr-moat` P9's "all-night 20-engineer" workflow and P8's 18-agent code-review (10 findings closed), plus the `music-ugc-moderation` 4-lane investigation with reconciled cross-lane findings, show the ≤4-writers/more-readers cap (Doctrine 9) working as designed. The bot-review loop is real and high-quality: `ocr-moat` caught a fully fictional doc section via a review wave; `observability-bus` caught two regressions in fix-up PRs within 12 minutes. **vidux is strong at converging code *within* the AI-actionable loop** — the failures cluster precisely at the boundaries it can't action alone (closeout, human gates, real-world proof).

---

## The independent quantitative baseline (hand-run grep scan, 2026-06-02)

Run directly against the corpus, separate from the agent forensics, so the two can be cross-checked. Reliable counts only (`grep -rho` / `find -exec grep -l`; an earlier per-file loop was discarded after a zsh word-splitting bug produced impossible all-zero counts — flagged here because the same evidence-discipline the doctrine preaches applies to this report).

| Signal | Count | Reading |
|---|---|---|
| Project plans with `## Progress` | 61/61 | Spine followed |
| Project plans with `## Decision Log` | 61/61 | Spine followed |
| Project plans with `## Evidence` | 49/61 | ~20% skip a *required* readiness item |
| Project plans with `## Constraints` | 51/61 | ~16% skip a *required* readiness item |
| Project plans with a `## Drift Log` section | **0/61** | Drift-reconciliation machinery (template section + PostToolUse hook + `vidux-drift-log.py`) produces **nothing** in practice |
| `[completed]` markers (all plans) | 658 | — |
| `[pending]` / `[in_progress]` / `[blocked]` (all plans) | 366 / 67 / 95 | 528 non-terminal markers live in the corpus |
| Open markers inside **archived** plans (`pending`+`in_progress`+`blocked`+unchecked `[ ]`) | **251** | vs only **177** `[completed]` in the same archived plans — **archival ≠ completion** |
| SUPERSEDED banners | 20 | Dedup recovery used — but also a measure of how much re-planning happened |

Two of these are load-bearing receipts:
- **Drift Log: 0/61.** The single most-instrumented discipline in the repo (template section + dedicated PostToolUse hook + dedicated `vidux-drift-log.py` script) leaves zero trace in any project plan. The forensics resolve the "why": the UNIFY step reconciles plan vs *local* git diff per cycle but never against the live remote, so design drift gets recorded informally in Progress prose (when at all) and the structured Drift Log the tooling expects stays empty. The drift machinery is effectively dead weight — and it is the same root cause as pattern P9 (plan/repo split-brain).
- **Archived plans are abandoned, not drained.** More open task markers (251) than completed ones (177) sit in `_archive/`. The forensics corroborate the direction (pattern P1): 23/26 active plans have open tasks with no closeout section, and 13+ archived plans were "closed" solely by moving the folder. *(Honest caveat: some of the 251 unchecked `[ ]` are nested sub-bullets or idea lists rather than abandoned tasks — the count is a ceiling on abandonment, not an exact tally. The directional finding holds regardless: archival is not completion.)*

---

## Recurring gaps — what we consistently don't do well

Ten patterns survived adversarial verification — each re-checked independently against the corpus. **Every one is confirmed real; every one's first-pass count was inflated and has been corrected down to a directly-verified floor.** The verification pass caught the synthesis agent overclaiming project counts (38→7, 22→6, 24→4…) *and* citing one evidence file that does not exist (a phantom `C53` receipt under `agentic-coding-workbench`). That is not a disclaimer to bury — it is live, in-band proof of pattern P10 below, generated by this report's own machinery, and the reason nothing here is asserted without a receipt that resolves on disk. Counts read "≥N" because the verifier confirmed floors, not ceilings, in a ~56-plan corpus.

The ten cluster into three failures of one underlying thing: **the loop knows how to start and how to run, but not how to end, how to prove, or how to bound itself.**

### Cluster A — Closure: projects don't end, they evaporate

The flow is Gather→Plan→Execute→Verify→Checkpoint. **There is no CLOSE.** So projects trail off, loops that *succeed* never stop, and blocked work sits forever.

- **P1 — Closeout is not a step (≥7 projects, high).** 23/26 active plans have open tasks and no closeout section; 13+ archived plans were "closed" only by moving the folder into `_archive/`. *Folder-move is the system's one reliable done-signal* — the PLAN.md format can't tell done from abandoned from blocked-forever. Receipt: `vidux-pilot-merge` was reversed after 9 days, got a SUPERSEDED banner, but Tasks 2-6 still read `[pending]`, never `[cancelled]`. (My independent scan: archived plans hold 251 open markers vs 177 completed.) **Doctrine delta:** the five-phase cycle has no close step; the archival pattern only fires on *duplicate* discovery.
- **P4 — Stop-conditions violated in both directions (≥4, high).** Succeeding loops never stop (`picker-strategy-migration`: 48 cycles, 38 in blocked-nurse after an OWNERS-only gate; 9 redundant post-merge evidence files); and "PROJECT COMPLETE" gets declared while acceptance criteria sit open — `resplit-2-0-evening-deep-dive` literally exploited the gate text: *"done-done… blocked is orthogonal to pending/in_progress."* **Doctrine delta:** the "300x re-verify" succeeding-loop guard exists in the *learnings* but is not in SKILL/LOOP/DOCTRINE; the three-strike rule only catches *failing* loops.
- **P8 — Crons have no retirement condition (≥5, medium).** `karaoke-wingman`'s only exit was "C2 authorization" that could never arrive for a cancelled hackathon; the cron kept firing idle scans. (vidux's own learning: "the vidux-loop cron produced 395K empty `loop_start` entries in 2 days — 99.7% of ledger volume.") **Doctrine delta:** "a lane without an exit is a zombie" is a learning, wired to nothing that can delete the cron.
- **P3 — Human-gated tasks become permanent open loops (≥4, high).** Anything needing Leo / IAM / OWNERS stalls forever; "waiting" is treated as the steady state. The Hard-NEVER external-comms rule compounds it: a task that needs a Slack ping is structurally unactionable *and* untracked. *Blocked-1-cycle and blocked-3-weeks look identical in the plan.* **Doctrine delta:** doctrine lists "external blocker" as a valid stop but sets no upper bound, no escalation artifact, no age-based forced disposition.

### Cluster B — Proof: the plan drifts from reality, and "done" is asserted, not verified

- **P2 — Verification gates are decoration, never enforced (≥6, high).** Every phase ships a "Gate (definition of done)" checklist filled out at *plan-writing* time and never checked at *completion* time. Hard receipt: across `ocr-moat` P1-P5, **49 gate boxes, 0 checked, all five phases declared `[completed]`.** **Doctrine delta:** this is the single most-preached rule in vidux ("never assert it works — show the screenshot," repeated in SKILL/DOCTRINE/LOOP as a "blocking rule") and the most universally violated. Nothing makes a `[completed]` flip block on its own gate.
- **P9 — Plan/repo split-brain (≥5, high).** The store claims work the live repos don't contain; the same task is `[completed]` in one section and `[pending]` in another; proof screenshots live in `/tmp` on another machine or in unmerged worktrees and don't exist where cited; the same fix gets replayed across 3-4 worktrees because sessions can't see each other (`internal-bridge-tool-mcp-closeout` repaired one regression 4× in a day). **Doctrine delta:** the UNIFY step compares plan vs *local* git diff — it never reconciles claims against the live remote, and nothing requires a cited artifact to actually resolve on disk.
- **P7 — Plan-as-progress: writing the plan counts as the work (≥4, high).** Design decisions written in prose get marked `[completed]`; fully-scaffolded zero-code plans get entered as "active" on a parent claims board, inflating fleet-health to show activity where there is none. (Concentrated in the `agentic-command-center` mega-plan: `gmail-bridge` / `imessage-bridge` "resolved in plan: label" rows; `codex-fleet-v3-revamp` scaffolded with all 7 tasks `[pending]`.) **Doctrine delta:** doctrine forbids the *symptom* (plan-only PRs) but not the *disease* (plan-only `[completed]` tasks).
- **P10 — Fabrication caught reactively, never audited as a class (≥5, medium).** Agents fabricate confident claims (a fake reviewer, a false branch state, a fictional doc section describing UI that doesn't exist). Sometimes a later cycle catches it; the specific claim is patched but sibling claims from the same *method* are never re-audited. *vidux's own learning says "silent loss is a class, not a one-off" (6 ASC-ID instances) — and the projects still treat each catch as isolated.* (Again: this report's synthesis agent fabricated the C53 receipt — caught only by the adversarial pass.) **Doctrine delta:** doctrine says spot-check *prospectively*; it never says re-audit-the-method after a *confirmed* fabrication.

### Cluster C — Scope: it inflates, and the payoff defers

- **P5 — Scope inflates monotonically; Purpose is never revised (≥4, medium).** Projects grow 3-6× mid-flight (a button → 32-task subsystem) while the Purpose header fossilizes at day-zero scope, so "% done" is measured against a fiction. `agentic-coding-workbench`'s formal task list froze at C14b while real work ran to C86. **Doctrine delta:** the 50/30/20 and Principle-4 brakes catch over-*polishing*, not goal *expansion*; nothing requires Purpose to be re-derived when N tasks are appended.
- **P6 — Research/spec infra is the deliverable; integration is perpetually deferred (≥6, medium).** The reliable shape: build the eval harness → run a metadata-only pass → conclude "need judge labels for a real verdict" → park. The verdict never lands. Investigation files end with "Tests (pending) / Gate (pending)" as permanent stubs — the investigation shipped *without* the fix, exactly what the Investigation Gate forbids. **Doctrine delta:** SKILL.md:87 explicitly prohibits this ("progress is code change… bookkeeping is not progress") and still loses.

**The through-line across all three clusters — and the meta-layer — is one finding:** vidux already has a written rule for nearly every one of these. P2 violates the most-repeated rule in the repo. P6 violates an explicit prohibition. P4 and P8's guards exist as "learnings" never promoted into the enforced skill. The 2026-04-09 postmortem's P0 fixes were authored and never shipped. **The gap is not insight. It is the distance between a rule written in Markdown and a rule that executes.**

---

## Core improvements — make the rules execute

These are deliberately *not* "write better doctrine." vidux's problem is the opposite: it has excellent doctrine that degrades because it lives in prose the model weighs against the current prompt. The frontier is **converting the highest-trust disciplines from prompt-hooks into command-gates** — checks that physically cannot be skipped — and pruning the rest. Five mechanisms, each retiring a cluster.

### 1. Add a CLOSE phase with three terminal verdicts — as an exit code, not a convention
Make the flow Gather→Plan→Execute→Verify→Checkpoint→**Close**. A plan goes inactive only via a mandatory trailer carrying one verdict: **SHIPPED** (every DoD box checked + verification output pasted), **PARKED** (named blocker + resume condition + owner), or **CANCELLED** (superseded-by pointer + reason). `vidux-loop.sh` refuses to mark a plan inactive without one, and emits an "unclosed" exit code for any plan with zero Progress entries for N cycles and no verdict — forcing the next coordinator to resume or formally park/cancel. *Retires P1; gives P4 its terminal sink and P8 its driving-need flag.*

### 2. Make `[completed]` structurally impossible to fake
A `[completed]` flip is rejected by lint unless: **(a)** every Gate box for that task/phase is checked, or carries an individually-tagged `[carve-out: reason]` (carve-outs over ~30% of a phase trip an abuse warning — this is the `resplit-weekend-push` pattern); **(b)** the flip ships with pasted command output *or* a cited artifact path that resolves on disk in the repo (kills `/tmp` and worktree-only phantom proofs); **(c)** any cited commit SHA is reachable from the named *remote* branch, not just local. And split tasks into `[decision]` (free but inert — can't satisfy a gate or count toward shippable %) vs `[execution]` (requires a resolvable artifact). *Retires P2, P7, and P9 in one rule.*

### 3. A blocker-age clock with forced disposition
Every `[blocked]` task carries a `blocked_since` stamp; `vidux-loop` computes `blocker_age` each cycle. At threshold 1 (≈3 cycles / 48h) the agent must draft a ready-to-paste escalation artifact into `ASK-LEO.md` / `drafts/` (respecting Hard-NEVER — *draft only, never send*) **and** demote the task to PARKED with a named resume condition, freeing the lane. At threshold 2 (≈1 week) it forces CANCEL-or-reduce-scope. Human-gated work gets a distinct `[human-gated]` tag so fleet-health can surface "N items awaiting a human for >X days" as a first-class metric instead of silent furniture. *Retires P3; feeds P8.*

### 4. A scope-drift checksum + a research-to-code ratio cap
Hash the Purpose block; when task count grows >50% or a new task *category* appears without a Purpose edit in the same commit, emit `purpose-stale` and force the coordinator to either absorb the scope into Purpose or split it into a new plan (real decomposition). Separately, every investigation/spec/eval artifact must name a downstream consumer task + a converge-by cycle; after 3 consecutive research-only commits with no consumer code, the lane is forced ship-or-park and blocked from creating more research artifacts. *Retires P5, P6.*

### 5. A fabrication-as-class trip-wire
When a fabricated factual claim is caught (self-correction or review), `vidux-loop` requires a class-audit artifact: name the *method* that produced it (which MCP tool, which inference, which grep), re-verify the sibling claims from that same method in the session, and tag the method low-trust ("needs-independent-confirm") for the rest of the session. It is cheap — a re-grep / re-query — and converts the documented-but-ignored "silent loss is a class" learning into a reflex. *Retires P10.*

### The meta-move: prune doctrine on the cadence it grows
SKILL.md is 1,282 lines; the calibration example-bank has reached row 1,440 across passes 2/6/10. vidux has `the-rip-pattern` for UI bloat and applies nothing equivalent to itself — more prose that degrades under pressure is not the fix for prose that degrades under pressure. Two standing disciplines: **(a)** a rule may not be *added* to SKILL.md/recipes unless it ships with its enforcement mechanism (a hook, a lint, a gate) or is explicitly tagged `[advisory]` — no more prose that pretends to be a control; **(b)** on the same cadence as plan-GC, run a *doctrine-GC* that demotes any rule with no enforcement and no citation in the last N cycles. And treat the 2026-04-09 postmortem's still-pending P0s as the canary: ship them, or "process fixes > code fixes" is itself just advisory.

### Sequencing for HQ
If only one thing ships: **#2** (gated `[completed]`) — it touches the trust core, retires three high-severity patterns, and is a bounded lint, not a redesign. Then **#1** (CLOSE phase) as the structural backbone the others hang off. #3–#5 are independent and parallelizable. The whole set is additive to the existing `vidux-loop.sh` / hook architecture — it hardens the loop vidux already has rather than replacing it.

---

## Appendix — corpus inventory

- 94 PLAN.md files total; 61 top-level project plans + 33 task subplans.
- 26 active projects under `projects/`; ~30 archived under `projects/_archive/2026-05-01/`; 4 resplit-2.0 archives (one with 9 task subplans).
- Doctrine layer: SKILL.md (1,282 ln), DOCTRINE.md (180), ENFORCEMENT.md (402), LOOP.md (359), INGREDIENTS.md (166), root PLAN.md (798), CHANGELOG.md (1,109), plus 23 files under `guides/` and the prior postmortem in `investigations/`.
- Environmental note: three live clones (`~/REDACTED-EMPLOYER-PATH/Dev/vidux`, `~/Development/vidux`, `~/vidux`→`~/.vidux`); docs reference stale paths (`~/Development/vidux`, `/Users/leokwan/…`). Minor, but it's drift in the meta-layer itself.

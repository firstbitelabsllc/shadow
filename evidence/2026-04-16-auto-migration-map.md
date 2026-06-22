# vidux-auto Migration Map

Generated 2026-04-16 for Phase 8.0 — the merge of three companion skills (`vidux-claude`, `vidux-codex`, `vidux-fleet`) into a single `/vidux-auto`. This is the archived planning artifact; condensed to the durable decisions.

Cross-reference files: `vidux/SKILL.md` (core discipline), `vidux/guides/agent-config-rules.md` (T1-T4 + 3 rules), `vidux/guides/recipes.md` (8 recipes).

---

## DEAD content (dropped in the merge)

| Source | Lines | Reason |
|---|---|---|
| vidux-claude | 1-5, 591-619 | Frontmatter / Activation / Related Skills — replaced by vidux-auto |
| vidux-claude | 63-74 | Routines comparison — superseded by Decision Log 2026-04-15 ("delete Routines, it's cloudbase") |
| vidux-claude | 77-87 | vidux-claude-specific subcommands |
| vidux-claude | 391-418 | Legacy Codex fleet scan + A/B testing with /codex — Codex deprecated (Phase 6.3.1) |
| vidux-codex | 1-4, 441-455, 610-622 | Frontmatter / Activation / Related Skills |
| vidux-codex | 12-37 | Scheduling primitive — overlap summary; keep claude's full version |
| vidux-codex | 600-608 | skills-as-commands meta — Claude Code v2.1.1-specific |
| vidux-fleet | 1-4, 248-253 | Frontmatter (vidux-loop + vidux-recipes merge) |
| vidux-fleet | 6-10, 37-38 | Routines priority note + `/schedule list` discovery — DEAD per Decision Log |
| vidux-fleet | 111-121, 131-155, 489-491, 603-609 | Routine config gen, Codex automation.toml, `--target routine`/`codex-legacy` paths — DEAD |

Total DEAD: ~280 lines (~14% of the 1,998 across three files).

**Routines, condensed replacement note:** Cloud Routines are rejected for this fleet (per-account binding, 1h min cadence, no local file access, no memory.md cross-reads).

---

## OVERLAP resolution

| Topic | Keep | Drop / merge |
|---|---|---|
| 24/7 Fleet Model | claude L28-75 (full) | codex L12-37 (summary) |
| Coordinator pattern | claude L143-156 (rationale) + fleet L91-107 (template) | — |
| Observer pairs | codex L396-430 (full: T8b/T14 evidence, setup recipe) | claude L158-167 heuristic merged in; fleet L224-250 |
| Delegation modes | codex L39-97 (full Mode A/B) | claude L249-280 summary |
| Prompt structure | claude L230-247 (8-block spec) + fleet L50-107 (templates) | — |
| Recipe catalog | fleet L278-389 as quick-ref → guides/recipes.md; codex qa-iterator as Recipe 6 | — |
| Memory.md format | claude L336-362 (full) + codex L432-439 (checkpoint) | — |
| CronCreate cadence | claude L301-311 (table) | fleet L47-49 defaults (redundant) |
| Worktree / Session GC / Lean dispatch | claude only (single source) | — |

CORE topics already in `vidux/SKILL.md` (skip, don't duplicate): live-state-from-PLAN.md anti-pattern, integration-with-/vidux, authority paths, "one PLAN.md per project," automation-is-platform-specific.

---

## Proposed vidux-auto TOC

```
# /vidux-auto

1.  What This Is — single automation companion to vidux core; replaces
    /vidux-claude, /vidux-codex, /vidux-fleet; cross-ref vidux SKILL.md.
2.  The 24/7 Fleet Operating Model — claude L28-75: lanes persist on disk,
    sessions cycle, session-gc mandatory, hot/cold storage, Routines-rejected note.
3.  Session Management — claude L486-563, L54-61: JSONL growth, 3 GC levels,
    session-gc lane spec, cycle signal, current-session-never-pruned.
4.  Lane Management — claude L117-220: decision tree, coordinator pattern
    (1 beats N), observer intro (→§9), 6-lane hard cap, anti-patterns,
    polish-brake trigger, ghost lane detection.
5.  Delegation (Mode A + Mode B) — codex L39-97, L136-186, L207-341:
    compression contract, 5-block prompt, diff-review checklist, when-to-delegate
    tree, T15 tier table, invocation flags, temp-file workaround.
6.  Fleet Operations — fleet L22-247, L392-740: slot map, stagger, prompt
    templates (writer/radar/coordinator/specialist), bimodal quality, validation
    rubric (9 checks), audit scoring, recipe selection → guides/recipes.md.
7.  PR Lifecycle (NEW — closes PR #338 gap) — claude L444-448 + PR Nurse:
    mandatory cycle-start triage, PR Nurse (scan, fix one P1/P2, push, verify,
    READY_FOR_MERGE), local CI for no-remote-CI repos.
8.  Concurrent-Cycle Hazards — claude L456-483: lint-staged stash, branch-switch
    data loss, CI review window, 4-line prevention checklist.
9.  Observer Pairs — codex L396-430 + claude L158-167: what they catch
    (T8b/T14), setup recipe, cadence offset, authority discipline, verdict format.
10. Worktree Discipline — claude L420-442: fresh per-cycle worktree, symlink deps,
    commit-then-merge, lint-staged branch-hijack gotcha, investigation-only skip.
11. Prompt File Structure — claude L230-247 + fleet L50-107: 8-block structure,
    ≤15-line harness rule, doctrine avoidance.
12. Composition Recipes — codex L476-598: 6 recipes (vidux→codex, codex+amp,
    codex+nia, Agent parallelism, Agent wrapper for long crons, qa-iterator).
13. Creating/Updating/Deleting Lanes — claude L282-334: CronCreate workflow,
    cadence table, stagger rule, memory seeding.
14. Memory Files — claude L336-362: append-only log, entry format, reset markers,
    last-10 visibility.
15. Lean Fleet Dispatch Rules — claude L565-577: 7 rules (hard cap, max 3-4
    parallel, fire-and-forget, trust memory.md, don't bloat parent, absorb
    duplicate fires, prefer coordinator).
16. Deferred Tool Loading — claude L16-26: ToolSearch for Cron*, TaskCreate, WebFetch.
17. External Tool Pairing — codex L343-374: nia (package source 16.5x), nia
    deep-mode warning (T14), amp amplification.
18. Recommended Agent Config Rules — guides/agent-config-rules.md: 3 rules
    (re-read before edit, re-read after fail, proportional response) + T1-T4.
19. Activation — combined triggers.
20. Related Skills — trimmed: vidux (core), captain, pilot, amp, nia, ledger.
```

---

## Personal-reference scrub (72 found)

Rules applied across all three files:

- **"Leo" name (22)** → "the operator/human"
- **Project names — leojkwan, strongyes, resplit, snowcubes (18)** → `<project-a/b/c>`
- **Lane names — leojkwan-coordinator, strongyes-coordinator, etc. (9)** → `<project>-coordinator`
- **File paths — ~/Development/strongyes-web/, Resplit/ paths (8)** → `<project>/`
- **Attributions — "Leo direct", dated Leo quotes (6)** → strip
- **Account-rotation details — "4 accounts" (5)** → "multi-account rotation"
- **Experiment paths — ~/Development/vidux-codex-experiment/ (2)** → "the experiment directory"
- **Keep as-is (already generic):** acme, beacon, Acme 2.0; dated evidence ("verified overnight 2026-04-13"), experiment names ("Frankenstein 2026-04-10/11", T73), `acme-ios`.

Drop (not genericize): claude L227 "A/B against Codex" paragraph (Codex deprecated).

---

## Estimated size

| Source | After dedup + scrub |
|---|---|
| vidux-claude (619) | ~350 |
| vidux-codex (626) | ~350 |
| vidux-fleet (753) | ~400 |
| NEW (PR Nurse, intro, activation) | +80 |
| **Total** | **~1,180** |

The 1,180 estimate exceeds the ~800-1000 PLAN.md target. Close the gap during section writing (8.2-8.5): fleet recipes → quick-ref table pointing to guides/recipes.md; condense cadence/measured-data tables; cut experiment backstory to 1-2 sentences. Target 900-1000 achievable with aggressive editing.

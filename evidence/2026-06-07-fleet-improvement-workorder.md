All paths confirmed. I have everything I need. Producing the work order.

---

# FLEET-TOOLING WORK ORDER

## (1) DEDUPED, PRIORITIZED IMPROVEMENT BACKLOG

Across the 10 lenses, the same 7 frictions recur. The dedup collapses ~40 raw proposals into **canonical edits** — each friction gets ONE source-of-truth rule in core (vidux/pilot-leo/auto) plus reference pointers elsewhere. Ranked by friction-impact.

### TIER 1 — HIGH IMPACT (ship first)

**B1 · Worktree isolation = MANDATORY + node_modules-before-commit (friction #1)**
The most-cited friction (5 lenses, 2 concrete incidents: shared-tree rebase clobber + husky revert in deps-less worktree).
- `~/Development/vidux/SKILL.md` → Trunk-First Rule (~line 207): tighten "worktrees only when isolation is useful" → "when 2+ agents may touch the repo, isolated worktree off origin/main is MANDATORY; never edit/commit/rebase/reset the shared trunk a sibling holds." *(one-liner edit)*
- `~/Development/vidux/SKILL.md` → Worktree lifecycle paragraph: append "fresh worktree has no node_modules/vendor — run repo's install (`npm ci`/`bundle install`) BEFORE the first commit or husky/lint-staged reverts it. Never `--no-verify` to dodge." *(one-liner)*
- `~/Development/ai-leo/skills/pilot-leo/SKILL.md` → NEW `### Isolated worktree per agent (canonical, all lanes)` under §Hard limits (after ~line 196): the full canonical 6-step recipe (`fetch --prune` → `worktree add -b <lane>/<slug> ... origin/main` → cd → `npm ci` → commit/push → `worktree remove --force`). This is the single recipe all other skills reference. *(structural — ~12 lines, but it's the keystone)*
- `~/Development/ai-leo/skills/amp/SKILL.md` → Harness Mode: NEW `## Fleet Safety Boilerplate` block with a worktree bullet that points at `/pilot-leo § Isolated worktree per agent` by REFERENCE (don't restate recipe). *(structural — see B7)*

**B2 · Verify-the-live-surface before "done" (friction #4)**
PR #75 couldn't be verified; M4 blocked. Discipline exists nowhere as one surface-keyed recipe.
- `~/Development/ai-leo/skills/auto/SKILL.md` → NEW `### Deploy-serves-new-code gate` at end of Decision tables: the canonical per-surface recipe — WEB: `curl /api/health | jq -r .release` == merged short SHA; WORKER: fresh 200 from live endpoint + new version-id atop `wrangler deployments list`; iOS: build NUMBER reaches ASC `Ready to Test`. "A merge is not a deploy; an upload is not a release." *(structural — this is the canonical source the others cite)*
- `~/Development/vidux/SKILL.md` → §5 Prove it mechanically (~line 95): one stack-neutral sentence — "if the change reaches a deployed surface, proof = hitting the LIVE surface, not the merge/upload/ledger row; else leave `[in_review]` + record `deploy unverified` with the check command. (Leo recipes: /auto §Deploy-serves-new-code gate.)" *(one-liner)*
- `~/Development/ai-leo/skills/pilot-leo/SKILL.md` → §1 after Graphite-ack block (~line 211): NEW `### Post-merge deploy confirmation` — cite /auto gate; don't mark PLAN row `[completed]` until live surface serves merged SHA. *(one-liner + cross-ref)*
- `~/Development/ai-leo/skills/amp/SKILL.md` → Harness rule 13 "Verify-before-done gate" + one checklist row in BOTH Harness & Goal pre-finalization checklists. *(structural — checklist gate)*

**B3 · Machine-checkable canon gate — Joe/Nikki → Fin/Coco (friction #2)**
Build agents repeatedly drifted; only frontmatter `author:` was scanned, never body prose. 39 stale Joe/Nikki PLAN files still live in sy-ai.
- `~/Development/ai-leo/skills/blog-builder/scripts/validate_blog_frontmatter.sh` → after author `case` (~line 148): scan body below `---` fence, `grep -qwE '(Joe|Nikki)'` → fail. Catches drift at WRITE/EDIT, the cheapest point. *(structural — actual code, highest-leverage because it's an executable gate not a prose rule)*
- `~/Development/ai-leo/skills/blog-builder/scripts/audit_blog_builder_quality.sh` → NEW SL-14 after SL-13 (~line 326): blocking body scan for retired names across promoted posts. *(structural — code)*
- `~/Development/vidux/SKILL.md` → VERIFY step: one line — "if repo declares canon names (vidux.config.json canon_terms / CANON.md), grep diff + touched plan rows for retired aliases before CHECKPOINT; a hit blocks completion." *(one-liner)*
- `~/Development/ai-leo/skills/brand-strongyes/SKILL.md` → Animina Canon section: one pointer line naming validate_blog_frontmatter.sh as the shared gate; tells rehoboam/content-engine to run it before marking pages done. *(one-liner — no new binary)*

**B4 · Destructive-op guardrails (friction #3)**
`.next` nuke broke a standalone build; wiped imagegen venv broke renders. disk-clean is only 44 lines and lists no in-use check.
- `~/Development/ai/skills/disk-clean/SKILL.md` → Rules: NEW first rule — in-use check before ANY cache/venv delete: `lsof +D <path>` + `pgrep -fl "next build|next start|tuist|xcodebuild|imagegen"`; non-empty → skip. Plus dry-run-print-first rule. Plus add `.next/`, `dist/`, framework build dirs, and skill venvs to Do-Not-Auto-Delete. *(structural — small file, ~3 bullets)*
- `~/Development/ai-leo/skills/auto/SKILL.md` → Hard NEVERs: one wall bullet — "Wipe a build cache/venv an active build or render needs (`.next`/DerivedData mid-build, imagegen venv mid-render) without the disk-clean in-use check + dry-run." *(one-liner)*
- `~/Development/ai/skills/fleet-cleanup/SKILL.md` → safe-cache rule (~line 195): bind auto-clean to "SAFE-regenerable AND idle-only"; cron never touches `.next`/venvs. *(one-liner)*

### TIER 2 — MEDIUM IMPACT

**B5 · Standby-loop / report-only-on-state-change (friction #5)**
Dozens of near-identical "Standing by" messages + endless Stop-hook re-spawn. Note: vidux *core* is already covered (Anti-Loop #2 + Nursing cadence); the gap is pilot-leo's cron-output mandate that FORCES per-cycle output.
- `~/Development/ai-leo/skills/pilot-leo/SKILL.md` → Operational-hook paragraph (~line 733): split output mandate by cron CLASS — code-shipping lanes keep `[APPENDED N]/[NO NEW WORK]`; OBSERVER/*-watch crons EXEMPT, silent on unchanged state, absence = heartbeat. *(structural — the highest-value #5 edit)*
- `~/Development/ai-leo/skills/pilot-leo/SKILL.md` → Lane memory no-noise rule (~line 507): generalize trigger beyond `[WAIT]`/`[ASK-LEO]`-only to "nothing watched/owned changed → skip entry regardless of prior entry." *(one-liner)*
- `~/Development/ai-leo/skills/pilot-leo/SKILL.md` → Codex heartbeat bullets (~lines 524-526): "do-not-self-retire ≠ post-every-fire; silent re-arm is correct." *(one-liner)*

**B6 · Match-requested-scope / anti-over-engineering (friction #7)**
Over-built "strategy lecture" drew pushback toward a simpler board.
- `~/Development/ai-leo/skills/auto/SKILL.md` → §F decision table (~line 215): NEW row — "board request gets a board, not a strategy lecture; match scope; see a bigger issue → name in ONE line and stop." *(one-liner)*
- `~/Development/ai-leo/skills/amp/SKILL.md` → Behavior Rules near "No meta-commentary" (~line 374): "Match requested scope — amplify to be SPECIFIC, never BIGGER." *(one-liner)*
- `~/Development/vidux/SKILL.md` → Working Defaults / Smallest vertical slice: "match the artifact to the request; over-producing the artifact = same waste as over-polishing a done surface." *(one-liner)*

**B7 · amp Fleet Safety Boilerplate block + blocking checklist rows (cross-cutting enforcement)**
The mechanism that makes #1-#6 non-optional in amp output. Friction recurred *because guardrails were implicit*.
- `~/Development/ai-leo/skills/amp/SKILL.md` → NEW `## Fleet Safety Boilerplate` (~6 lines, by reference): worktree isolation, dry-run destructive ops, verify-live-before-done, canon grep gate, report-on-change, shell quoting. + ONE blocking checklist row in BOTH pre-finalization checklists. *(structural — but the single edit that operationalizes everything above for spawned fleets)*

**B8 · Bash quoting / word-splitting (friction #6)**
ollama model names passed as one string; unquoted array args; empty-var `rm -rf $X/` → `rm -rf /`.
- `~/Development/ai/skills/disk-clean/SKILL.md` → Commands: quoting-discipline note — `rm -rf "$X"` with `[ -n "$X" ]` guard; pass multi-word args as `"${arr[@]}"`. *(one-liner)*
- `~/Development/ai-leo/skills/auto/SKILL.md` → Hard NEVERs: "Never `rm -rf` with unquoted/possibly-empty var." *(one-liner)*
- Folded into amp Boilerplate (B7) as one bullet.

### TIER 3 — LOW (vidux-drift hardening; do after Tier 1-2)
- `~/Development/vidux/SKILL.md` ASSESS: promote `vidux drift suggest` from soft advice to a blocking pre-flight gate. *(one-liner)*
- `~/Development/vidux/tests/test_drift_log.py` (or new `test_argv_contract.py`): repo-wide test asserting no `scripts/*.py` contains `argv or sys\.argv` — the executable canon gate the closeout grep should have become. *(structural — code)*
- `~/Development/vidux/ENFORCEMENT.md`: codify ONE canonical entrypoint idiom `args = parse_args(sys.argv[1:] if argv is None else argv)`. *(one-liner)*

**Quick-vs-structural tally:** 14 one-liner appends to existing sections; 7 structural (amp Boilerplate block + checklist, pilot-leo worktree recipe, auto deploy-gate, 2 blog-builder script edits, vidux argv test, pilot-leo cron-class split). Ship the one-liners in a single sweep PR per repo (ai-leo, vidux, ai); the structural ones get focused PRs.

---

## (2) TOP 5 NEXT GOALS ACROSS THE VIDUX FLEET (ranked by impact)

1. **Resplit 2.0 — clear iOS-RECON-1 (TestFlight upload of post-2626 fix train).** `resplit-web/vidux/resplit-2.0-launch/PLAN.md`. P0 launch-window blocker, cutoff already past. origin/main is ~6 commits ahead of build 2626 with merged ASC fixes (PRs #784-#793); deploy watcher self-skips on dirty attached checkout. **Mechanical, not code** — ship from clean checkout `/Users/leokwan/Development/resplit-ios-deploy-clean` after the 11pm-8am ET night gate. Unblocks iOS-RECON-3/4/5.

2. **StrongYes Gate-0 reclaim — BLOG-DELETE + FRONT-DOOR-FABRICATION.** `strongyes-web/vidux/launch-validation/PLAN.md`. The two biggest agent-doable rows: delete 101 slop `content/learn/companies/*.mdx` + 410 Gone redirect; fix 28 `app/companies` pages shipping fabricated "Top 10 Problems" lists that break the grounded-truth moat. Everything else is LEO-GATED behind the 2026-06-10 filmed cold rep.

3. **resplit-currency-api GCP scaffold — Cloud Run + Terraform IaC for the FX read path.** `resplit-currency-api/vidux/pre-launch-architecture/PLAN.md`. Clean pre-2.0 rebuild, no migration loss, Snap-career learning vehicle. Pick the simplest GCP-native primitive proving scale-to-zero→millions. Constraint: "scalable but NOT over-engineered" (maps to friction #7).

4. **StrongYes live-mode Stripe rotation — agent runs T1-T3 + stages T6.** `sy-ai/vidux/stripe-live-rotation/PLAN.md`. Create live-mode Pro product + $180 quarterly + $350 annual via Stripe MCP, stage Vercel Production price-ID swap; hand webhook/secret rotation to Leo. **Caveat:** confirm this plan against canonical strongyes-web before executing so it isn't lost in the sy-ai sprawl.

5. **fcp-workflow uae-with-nicole-reel reconciliation.** `fcp-workflow/vidux/uae-with-nicole-reel/PLAN.md`. Closest-to-done media plan (5 pending/10 done) but stale since 2026-05-01. Leo-hands editing, not agent-shipping — agents reconcile the 5 pending rows against existing footage/FCPXML, mark already-done rows `[completed]` with evidence, surface the true remaining cut list (or `[blocked: awaiting Leo ingest]`).

**Two hygiene archives that block fleet-survey accuracy (do alongside):** ARCHIVE the entire `mobiledevcombine-web/vidux/` tree (old name for strongyes-web, frozen 2026-04-18) and ARCHIVE the `sy-ai/vidux/` pre-pivot sprawl down to launch-validation + stripe-live-rotation (kills the 39-file Joe/Nikki stale-canon corpus build agents keep re-reading — friction #2 at the source).

---

## (3) RECOMMENDATION — "Do we need to improve /pilot-leo /vidux core?"

**YES — but surgically, not a rewrite.** Both skills are sound; the recurring frictions are gaps where existing rules are too soft, too narrowly-scoped, or implicit. The fix is one-line tightenings of EXISTING sections plus two structural keystones. Resist adding machinery — over-building the guardrails is itself friction #7.

**The 3 highest-value edits (do these even if you do nothing else):**

1. **pilot-leo: add `### Isolated worktree per agent (canonical, all lanes)` with the 6-step recipe incl. `npm ci`-before-commit.** This is the single most-cited friction (#1, 5 lenses, 2 incidents). Today worktree discipline is scoped only to gen-lanes and Graphite-fixes; the universal rule and the node_modules-revert recipe exist nowhere. This one block becomes the reference every other skill cites.

2. **auto: add `### Deploy-serves-new-code gate` (the per-surface verify recipe: web `/api/health`==SHA, worker version-id, iOS ASC build number).** Friction #4 (PR #75 unverifiable) has no canonical home — "a deploy is verified right now with no rule to cite." vidux core and pilot-leo then both reference it in one line each. Turns "merged = done" into "live surface serves the SHA = done."

3. **vidux core: tighten VERIFY (canon grep gate) + Trunk-First (worktree MANDATORY) + §5 (deploy = live-surface proof) — three one-liners.** These make the canon gate (#2), worktree mandate (#1), and live-proof (#4) bind fleet-wide and stack-neutral, so the discipline holds in repos without a Leo overlay.

Everything else in the backlog is incremental hardening. Ship the 3 above first — they close the two frictions that caused actual rework (shared-tree reverts, unverifiable deploys) and the one that needs an executable gate (canon drift).

---
## Applied 2026-06-07 (this session)
- ✅ vidux core (this repo): §5 deploy=live-surface proof; Trunk-First worktree-MANDATORY + npm-ci-before-commit; VERIFY canon-grep gate. (work-order recommendation #3, items B1/B2/B3 stack-neutral half.)
- ⏸️ ai-leo edits (amp Fleet-Safety-Boilerplate, pilot-leo Isolated-worktree recipe + Deploy-confirmation, auto Deploy-serves-new-code gate + Hard NEVERs) — BLOCKED: ai-leo is mid cross-machine divergence (behind 5, staged amp/auto WIP, 3 stashes). Needs Leo reconciliation before these land cleanly. See [[project_ai_leo_cross_machine_divergence]].
- ⏸️ blog-builder canon body-grep gate (B3 structural) + disk-clean in-use check (B4) — pending.

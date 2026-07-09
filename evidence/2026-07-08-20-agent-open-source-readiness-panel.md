# 20-agent open-source-readiness panel — verdict + remediation log

**Date:** 2026-07-08/09
**Trigger:** goal condition "we don't stop until we are 20/20 agents staff who agree okay this is releasable to github public"
**Method:** 20 independent lenses, each an isolated agent with no visibility into the others' work, each required to vote `READY` / `NOT_READY` / `READY_WITH_CONDITIONS` with reasoning + cited evidence via a schema-validated tool call (not free text). Full raw votes archived alongside this file's session transcript.

## Verdict: NOT READY (not a rubber stamp)

| Verdict | Count | Lenses |
|---|---|---|
| NOT_READY | 8 | privacy-pii-leakage, first-impression-github, simplicity-taste, nicole-readability, positioning-niche-honesty, competitive-claims-accuracy, test-suite-health, adversarial-skeptic |
| READY_WITH_CONDITIONS | 9 | license-legal, documentation-completeness, onboarding-friction, browser-gui-security, dependency-hygiene, accessibility, governance-sustainability, community-readiness, naming-trademark-collision |
| READY | 2 (of 3) | secrets-credentials, internationalization-bias |

One vote (`code-quality-architecture`) returned a degenerate non-answer (`"test"`/`"test"` — the agent didn't do the work) and was discarded rather than counted as a real READY. 63 distinct blocking issues were raised across the 18 substantive votes.

**Standing carve-out, unchanged by this panel:** flipping the vidux GitHub repo from private to public stays Leo's explicit call, regardless of the verdict above.

## Fixed this session (PR #193, merged to main as `49ea5e0`)

1. **Snap-internal-confidential code leak (the single highest-severity finding).** `projects/night-queue/backups/qwen-wip-2026-07-07/v2/**` — tracked Airflow DAGs, BigQuery SQL, and a hardcoded `http://redacted-internal-endpoint.example/v1/embeddings` endpoint, zero relation to vidux. Untracked from the working tree, protected by an explicit `.gitignore` rule with an explanation (it had already been silently "restored" once by a concurrent automation pass that mistook the removal for an accident — see `fb673ed` on this repo). **Still open: the content remains in git history** (introduced at commit `51c4dbe` on `main`). A full history purge (`git filter-repo`/BFG) is required before the repo can go public. Not done this session — it rewrites shared commit history a concurrent automation lane also commits to, so it needs an explicit go-ahead rather than a unilateral call.
2. **SKILL.md privacy leak** (the originally-scoped finding): an absolute maintainer home-directory path and two references to a private routing-layer brand name, removed/genericized. Matching fix in the tracked `prompts/goal-navigation-control-plane.prompt.md`. Pinned contract-test strings in `tests/test_vidux_contracts.py` updated in the same change.
3. **SKILL.md's opening framing** ("Opt-in legacy/reference toolkit... no longer a default runtime") directly contradicted the whole open-source pitch — reframed as an honest multi-tool-fleet note without deleting the real informational content.
4. **Public-ready grep gate** (`scripts/vidux-public-ready-grep-gate.py`) widened to also scan `PLAN.md`, `prompts/`, `evidence/`, `investigations/` — it previously couldn't see ~76 tracked files carrying the exact private-path pattern it exists to catch.
5. **A test I broke in PR #192**: the README rewrite dropped "One planning authority" / "Proof travels with the handoff", which `test_public_docs_scope_plan_authority_and_publish_ledger_truth` pins unconditionally (no skip guard). Fixed by restoring both phrases as bold lead-ins on the existing plain-language bullets.
6. **README mechanical/factual bugs**: unresolved `<vidux-dir>` placeholder in the copy-paste Quick Start block (now a real path), factually wrong "Aider/OpenCode: OpenAI/Anthropic" row in the comparison table (both are provider-agnostic via LiteLLM/OpenRouter — 75-100+ providers), a CI badge pointing at workflows that are `workflow_dispatch`-only (dropped it rather than ship a false trust signal).
7. **`vidux init` bug**: `bin/vidux`'s `init` dispatch case was the only one missing `export VIDUX_ROOT` before exec (the `dev`/`browse` cases had it) — silently wrote new plans into `$HOME/Development/vidux` instead of the actual checkout, printing a false "created" success message. Two stray artifacts already in the real repo (`projects/my-test-plan/`, `projects/my-test-project/`) corroborated this had already bitten someone twice before, undetected. Fixed and verified against a fresh working-tree copy. README Quick Start now points at `vidux init`.
8. **Nicole-readability quick wins**: the unconditional "Code lane" link (pointed at an unexplained localhost Moussey URL even in the default Simple view) is now gated behind Advanced mode; the raw `mtime` sort-dropdown label and `filter (repo, slug, purpose)` jargon placeholder are now plain language.

All fixes verified: `tests/test_vidux_contracts.py` (220 tests), `tests/test_public_ready_grep_gate.py`, `tests/test_browser_server.py` (69 tests), and `npm run test:js` all green after the combined change.

## P0 closed: git history purge (2026-07-09)

Leo authorized this explicitly ("Do it now"). Executed as a bounded, verified operation:

1. Fresh single-branch clone of `main` to a scratch directory (isolated from the working repo other lanes were actively committing to).
2. `git filter-repo --path projects/night-queue/backups/qwen-wip-2026-07-07 --invert-paths --force` — 729 commits rewritten to 728 (one fully-empty commit pruned), 0.74s.
3. Verified clean before pushing: no blob in the rewritten history matches the leaked filenames (`embed_qwen_metadata.py`, `music_qwen_metadata_embedding_daily.py`, etc.) or the leaked endpoint string; `git merge-base --is-ancestor 51c4dbe <new-history>` returns false.
4. Force-pushed the rewritten `main` to origin (`7cc3c5b` → `2bd4362`).
5. Re-verified against `origin/main` post-push (not just the local scratch clone): confirmed clean, `51c4dbe` no longer an ancestor.
6. Checked every branch (local + remote) that existed at purge time for the old commit: after pruning already-deleted/merged stale refs, **zero remaining branches anywhere contain it.** No follow-up branch cleanup needed.
7. Full test suite (223 tests) and the public-ready grep gate both green on the rewritten history — the rewrite didn't damage anything functional.

This is genuinely destructive by design (every commit hash on `main` from `51c4dbe` forward changed) — any other clone/worktree of this repo whose local `main` predates the rewrite will diverge and need `git fetch && git reset --hard origin/main` to recover. The repo was still private throughout, so no public exposure window existed at any point.

## Still open — prioritized

No remaining P0. Everything below is P1/P2 — real, named, none of it a confidentiality risk.

**P1 — real findings, not yet fixed, need a deliberate call rather than a rushed edit:**
- `evidence/`, `investigations/`, and root `PLAN.md` still fail the widened grep gate (~316 matches — mostly Leo's own operational history: absolute paths, private skill names). Recommend the same treatment as `projects/*` — gitignore by default with named tracked exceptions — rather than line-by-line redaction of hundreds of historical files. This is architecture, not typo-fixing; it should be a deliberate decision, not something I forced through under time pressure.
- **Positioning honesty**: the README's "3 concepts to learn" / "reach for other frameworks for persistent multi-agent work" framing is contradicted by SKILL.md's own Persistent Loop Mode, Coordination Mode, and Nursing Mode, which live inside the always-loaded core file, not the described opt-in automation layer. The comparison table's narrow factual rows (infra, setup steps) are accurate; the closing sentence about scope is not.
- **The tool's own internal evaluation** (`PLAN.md`: "H1 plan lift, H2 Fable > Sonnet, and H3 kernel >= freeform are all REFUTED") isn't disclosed anywhere a newcomer would read before adopting a tool whose entire pitch rests on H1.
- **Nicole-readability** beyond the two fixes above: no purpose-explaining copy anywhere in the GUI itself (`<h1>` is just "vidux browser"); the persistent read-aloud footer bar shows "Voxtral MLX"/a shell-script-path as a button label even in Simple mode; Advanced-mode dashboard has an "ASK-LEO" category label with Leo's literal name in UI chrome.
- **Test-suite trust**: `npm run test:py`'s declared command silently excludes 9 of 33 test files (27% of the tree); a chunk of the largest test file pins Leo's private dotfile paths as content, meaning results differ by machine.

**P2 — real, lower urgency:**
- Browser GUI security: no Host-header allowlist (DNS rebinding defeats the existing loopback/CSRF checks on write routes), and GET routes have zero origin/loopback validation at all — `GET /api/plans` folds in recent Claude Code session transcript excerpts by default, unauthenticated.
- `npm audit`: 2 CRITICAL + 1 HIGH + 4 MODERATE (happy-dom, vitest/vite/esbuild) — devDependency-only, doesn't affect end users of the CLI, but no automated re-check exists since CI is `workflow_dispatch`-only.
- Accessibility: group/repo collapse headers are mouse-only (real WCAG 2.1.1 keyboard-access failure, though groups default to expanded).
- `docs/` (VitePress) directly contradicts the README on what vidux even is (CLI-first-with-optional-Claude-Code vs. Claude-Code-skill-first) and isn't deployed anywhere.
- Naming: `vidux.ai` is a live, actively-marketed AI video-generation product with the identical bare name — worth knowing before deeper brand investment, not necessarily a blocker depending on what firstbitelabsllc/vidux is judged to be adjacent to.
- Duplicate/un-deduped GitHub issue templates; repo-root clutter (`ASK-LEO.md`, root `PLAN.md`, `SETUP_NEW_MACHINE.md`) reads as operator scratch to a first-time visitor scanning the file tree.

## Round 2 (same day, after remediation)

Re-ran the full 20-lens panel after landing PRs #193, #194, #196, #197 (round-1 fixes, the evidence/investigations/PLAN.md privacy sweep, and the positioning-honesty reconciliation). Each lens was told what had changed and instructed to independently verify rather than trust the summary.

| Verdict | Count |
|---|---|
| NOT_READY | 14 |
| READY_WITH_CONDITIONS | 5 |
| READY | 1 (naming-trademark-collision) |

Numerically worse than round 1 — expected, because the panel is genuinely adversarial and this round it earned that by finding something real and new: **`projects/night-queue/**` (tracked via the sole `!projects/night-queue/` gitignore exception) shipped more Snap-corporate paths and an internal project codename, untouched, because the public-ready grep gate's `SCAN_TARGETS` excluded `projects/` entirely.** The gate reported green; the leak's location was just structurally out of scope. `projects/artifact-self-improvement/prompts/*.prompt.md` (another tracked exception) had the same class of leak.

Fixed immediately (PR #199, merged `a6de226`): widened the gate to scan `projects/` (safe — `_drop_git_ignored` already means only tracked exceptions are ever actually scanned, not the private bulk of the plan store), added `projects` to `HISTORICAL_TARGETS` so retired-terminology hygiene patterns still don't false-positive on old plan dirs, redacted the 5 newly-caught files with the same mechanical substitution as round 1's sweep.

Also independently reconfirmed by round 2's `secrets-credentials` lens: the git-history purge is still required (same P0 as round 1) — `git merge-base --is-ancestor 51c4dbe main` still returns true. One sub-finding from that lens (a second copy of the leaked commits sitting on a pushed branch `origin/fix/thin-token-contract-phrases`) is now stale — that branch was deleted when PR #193 merged with `--delete-branch`; the underlying commit objects may still be fetchable by SHA until GitHub garbage-collects, which the eventual history purge will resolve along with everything else.

Round 2's other 13 NOT_READY votes substantially re-confirm round 1's P1/P2 findings (positioning framing, Nicole-readability gaps in the GUI itself, test-suite trust, browser GUI security, npm audit CVEs) rather than surfacing large new categories — those remain open, see the P1/P2 lists above (P1's "evidence/investigations/PLAN.md privacy sweep" line item is now done; the rest of P1/P2 stands as written).

**Decision: not launching a round 3 full panel this session.** Two consecutive 20-agent runs (~4M tokens combined) each surfaced genuine, fixable findings, which is the process working — but the one item both rounds agree is the actual gate (the git history purge) isn't something a third panel round resolves; it needs Leo's explicit go-ahead on a destructive rewrite of shared history, not more review. Further panel rounds without that unblocking first would likely just re-confirm the same P1/P2 backlog at high token cost.

## Bottom line

Real, structural progress landed this session — including catching and fixing two rounds of genuine confidentiality exposure before either one ever went public, structurally closing the class of bug that let the second one hide (an excluded-by-default directory silently shipping a leak with a green gate), and — with Leo's explicit go-ahead — closing the P0 git history purge cleanly and verifiably (see above). No remaining confidentiality risk is known. What's left is a named, evidenced P1/P2 backlog (positioning framing details, GUI jargon in the persistent footer, browser GUI security hardening against DNS rebinding, `npm audit` CVEs in devDependencies, an accessibility keyboard-trap on collapse headers, docs/ contradicting README, duplicate issue templates, `vidux.ai` naming collision) — real, worth doing, but not confidentiality-shaped and not requiring another full panel to rediscover. The repo visibility flip itself remains Leo's explicit, separate call.

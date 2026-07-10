# 2026-07-07 Kernel-Cut Pivot Evidence

## Local Receipts

*(2026-07-09 clarification, not a revision of the original record: every
`~/Development/vidux/evaluations/vidux-vs-native-bakeoff/...` path below is
the maintainer's own local, untracked evaluation harness -- it was never
shipped, is explicitly excluded from the public repo, and will not exist in
a fresh clone. These lines record what was actually checked at the time, not
a citation an external reader can independently open. See the summarized
numbers inline below and in `PLAN.md`'s Decision Log, which are the durable,
shipped record of the result.)*

- Planner-executor authority: `~/Development/vidux/evaluations/vidux-vs-native-bakeoff/PE-HANDOFF.md` and `~/Development/vidux/evaluations/vidux-vs-native-bakeoff/PLANNER-EXECUTOR-PROTOCOL.md`.
- Run receipt: `~/Development/vidux/evaluations/vidux-vs-native-bakeoff/results/pe/RUN-SUMMARY.md`.
- Decision receipt: `~/Development/vidux/evaluations/vidux-vs-native-bakeoff/results/pe/decision.md`.
- The full matrix wrote 119 rows; `pe_decision.py` scored 117 clean rows after excluding 2 final Grok infra rows under the protocol.
- Frozen thresholds all refuted the kernel bet: H1 plan lift, H2 Fable over Sonnet, and H3 kernel over freeform.
- The strongest comparison for the handoff format is direct: `fable_freeform_glm` resolved 13/17 (76%) while `fable_kernel_glm` resolved 10/17 (59%).

## Official Guidance Inputs

- OpenAI Codex best practices: https://developers.openai.com/codex/learn/best-practices
  - Use planning for difficult work, keep reusable guidance practical, and add rules after repeated mistakes instead of front-loading ceremony.
- OpenAI Codex goals: https://developers.openai.com/codex/prompting and https://developers.openai.com/codex/use-cases/follow-goals
  - Long-running goals need measurable outcomes and test criteria; goals should not become vague orchestration loops.
- OpenAI Codex subagents and skills: https://developers.openai.com/codex/subagents and https://developers.openai.com/codex/skills
  - Specialized agents and skills are useful, but the lead owns integration, proof, and stopping criteria.
- Anthropic Claude Code subagents/workflows/hooks: https://docs.anthropic.com/en/docs/claude-code/sub-agents, https://docs.anthropic.com/en/docs/claude-code/common-workflows, and https://docs.anthropic.com/en/docs/claude-code/hooks-guide
  - Delegate bounded side work, preserve lead context, and use deterministic checks for rules that matter.
- Cursor agent best practices and Customize/Marketplace direction: https://cursor.com/blog/agent-best-practices, https://cursor.com/changelog, and https://cursor.com/blog/marketplace
  - Keep rules focused, reference canonical files instead of duplicating them, and package tools/rules/hooks/skills only where they earn their keep.

## Decision

Freeze current kernel/planner-executor handoff as the default Vidux route. Keep the bakeoff harness for measurement and regression checks. Keep Vidux as a thin local discipline plus read-only plan/proof/decision cockpit. Treat GLM, Grok, Codex, Claude, and Fable as bounded workers or eval subjects, not as a new control plane.

## Doctrine Shrink Receipt

- `SKILL.md` now states that Vidux is the thin plan/proof control plane, not the runner-selection kernel.
- Vidux owns the schema and lifecycle for plan state, decisions, proof packets, checkpoints, resume semantics, and browser projection.
- The host router owns model/runner selection and leader/follower foldback.
- Contracts reject stale kernel-ownership wording and require the thin-control-plane boundary.
- Proof 2026-07-07:
  - `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_goal_navigation_and_deleted_auto_contract tests.test_vidux_contracts.ViduxContractTests.test_model_worker_delegation_contract_covers_glm_grok_and_codex tests.test_vidux_contracts.ViduxContractTests.test_core_skill_scopes_plan_authority_and_publish_ledger_truth` PASS (3 tests).
  - `rg -n "Vidux is the kernel|planner-executor kernel|default kernel handoff|current kernel|Vidux owns the full nursing loop|Vidux owns model-specific" SKILL.md README.md docs guides prompts tests -S` found no stale source prose outside contract fixtures.
  - `python3 -m unittest tests.test_browser_server` PASS (68 tests, skipped=1).
  - `python3 -m unittest tests.test_vidux_contracts` PASS (219 tests, skipped=3).
  - `git diff --check` PASS.

## PE Verdict Cockpit Receipt

- `browser/server.py` now extracts planner-executor verdict receipts from `PLAN.md` Evidence into a read-only dashboard `verdicts` category.
- `browser/static/app.js` renders a Verdicts dashboard card, Recent Verdicts list, sidebar verdict count, and proof-path metadata on verdict rows.
- The extraction reads existing markdown evidence only. It does not import, run, or depend on the planner-executor evaluation harness at browser runtime.
- Live dashboard extraction 2026-07-07: 289 plans, 25 repos, 1 verdict. The verdict came from `vidux-main-active/PLAN.md:16`, status `refuted`, proof path `vidux/evaluations/vidux-vs-native-bakeoff/results/pe/RUN-SUMMARY.md`.
- Proof 2026-07-07:
  - `python3 -m unittest tests.test_browser_server.BrowserDashboardTests.test_dashboard_surfaces_pe_verdict_receipts tests.test_browser_server.BrowserDashboardTests.test_dashboard_static_contract` PASS (2 tests).
  - `python3 -m py_compile browser/server.py` PASS.
  - `python3 -m unittest tests.test_browser_server` PASS (69 tests, skipped=1).
  - `python3 -m unittest tests.test_vidux_contracts` PASS (219 tests, skipped=3).
  - `rg -n "Vidux is the kernel|planner-executor kernel|default kernel handoff|current kernel|Vidux owns the full nursing loop|Vidux owns model-specific" SKILL.md README.md docs guides prompts tests -S` found only contract fixture strings.
  - `git diff --check` PASS.

## Guide/Reference Cleanup Receipt

- README and published docs now call Vidux a thin plan/proof control plane or recovery packet, not a lightweight orchestration system.
- `SKILL.md` no longer teaches ORCHESTRATED mode, default discipline swarms, or release-role rosters. It keeps a smaller coordinated mode: Vidux coordinates plan/proof state; host tools or Flow dispatch workers.
- `guides/automation.md`, `references/automation.md`, and `docs/fleet/*` now carry explicit boundary notes: automation details are opt-in operator reference, while runner/model selection, subagent dispatch, and foldback belong to the host runtime or Flow.
- Contract coverage now rejects public/core regressions such as `Vidux orchestrates`, `ORCHESTRATED`, `Orchestration Mode`, `Default Discipline Swarm`, `Release Swarm`, and the old `lightweight orchestration system` framing.
- Proof 2026-07-07:
  - `python3 -m unittest tests.test_vidux_contracts.ViduxContractTests.test_loop_and_guide_scope_plan_authority_and_publish_ledger_truth tests.test_vidux_contracts.ViduxContractTests.test_kernel_cut_public_docs_scope_vidux_to_plan_proof_control_plane` PASS (2 tests).
  - `rg -n "lightweight orchestration system|Vidux orchestrates|Documentation is the control plane|planning control plane|Fleet Intelligence|ORCHESTRATED|Orchestration Mode|Default Discipline Swarm|Release Swarm|Vidux orchestrates — decompose, delegate, track" README.md docs guides references SKILL.md -S` returned no matches.
  - `python3 -m unittest tests.test_vidux_contracts` PASS (220 tests, skipped=3).
  - `git diff --check` PASS.

## Browser Visual Smoke Receipt

- Local browser URL: `http://127.0.0.1:7192` with `--root ~/Development`.
- `/api/plans` reports 289 plans, 25 repos, and dashboard `verdicts` with `proof_rel: vidux/evaluations/vidux-vs-native-bakeoff/results/pe/RUN-SUMMARY.md`.
- Chrome/Playwright rendered the Fleet dashboard and confirmed:
  - Verdict card text: `VERDICTS 1 1 total`.
  - Recent Verdicts text includes `H1/H2/H3 all refuted` and the PE proof path.
  - Sidebar text includes `1 verdicts`.
- Visual smoke found and fixed a dashboard usability bug: large decision/inbox lists made dashboard panels unbounded, pushing later panels into awkward page flow. `.dashboard-list` is now capped at `min(560px, 70vh)` and `.dashboard-items` scrolls internally.
- Screenshot receipts:
  - `evidence/2026-07-07-browser-verdict-list-element-after-css.png`
  - (`...-dashboard-after-css.png` removed 2026-07-10: the full-dashboard
    capture rendered real cross-repo plan content spanning nearly the whole
    frame -- no crop preserved the CSS-containment claim without also
    keeping that content. The list-element screenshot above already proves
    the same fix in isolation.)
- Proof 2026-07-07:
  - `curl -s http://127.0.0.1:7192/api/plans | python3 -m json.tool | rg -n '"verdicts"|"Verdicts"|"proof_rel"|...` found the Verdicts category and PE proof path.
  - Chrome/Playwright DOM check PASS using `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
  - `python3 -m unittest tests.test_browser_server.BrowserDashboardTests.test_dashboard_static_contract tests.test_browser_server.BrowserDashboardTests.test_dashboard_surfaces_pe_verdict_receipts` PASS (2 tests).
  - `python3 -m unittest tests.test_browser_server` PASS (69 tests, skipped=1).
  - `git diff --check` PASS.

## Thin-Surface Final Audit Receipt

- Dirty diff reviewed as one package after the browser visual smoke:
  - Browser source adds read-only Decisions and Verdicts dashboard categories. Verdicts come from `PLAN.md` Evidence lines and proof paths; the browser does not import or run the evaluation harness.
  - Public/core docs and `SKILL.md` now frame Vidux as plan/proof/decision/resume cockpit, with host runtime or Flow owning dispatch and foldback.
  - `prompts/goal-navigation-control-plane.prompt.md` only adds canonical skill binding examples for minted goal pointers; it does not store current goal state.
  - Contract tests cover stale orchestration/kernel language and the browser dashboard categories.
- Stale corpus audit:
  - This checkout has untracked `evaluations/` at 84M with 95 files under maxdepth 3 and no tracked files.
  - Canonical sibling `~/Development/vidux/evaluations/vidux-vs-native-bakeoff` is 252M with 2242 files under maxdepth 3.
  - `diff -qr evaluations/vidux-vs-native-bakeoff ~/Development/vidux/evaluations/vidux-vs-native-bakeoff | head -80` shows the untracked copy is stale/partial: it lacks PE handoff/protocol files and canonical `results/pe*`, while its `runs/live` artifacts differ.
  - The stale copy was not deleted because it is untracked, differs from canonical run artifacts, and may contain previous local/session data. It should stay out of the kernel-cut package unless explicitly archived or deleted.
- Proof 2026-07-07 after this checkpoint:
  - `curl -s http://127.0.0.1:7192/api/health` PASS.
  - `rg -n "lightweight orchestration system|Vidux orchestrates|Documentation is the control plane|planning control plane|Fleet Intelligence|ORCHESTRATED|Orchestration Mode|Default Discipline Swarm|Release Swarm|Vidux orchestrates — decompose, delegate, track" README.md docs guides references SKILL.md -S` returned no matches.
  - `git diff --check` PASS.
  - `python3 -m py_compile browser/server.py` PASS.
  - `python3 -m unittest tests.test_browser_server` PASS.
  - `python3 -m unittest tests.test_vidux_contracts` PASS.

## Package Boundary Receipt

- Package decision: ship the kernel-cut pivot as a thin cockpit/control-plane package, not as a planner-executor kernel package.
- Include only these owned files:
  - `PLAN.md`
  - `README.md`
  - `SKILL.md`
  - `browser/server.py`
  - `browser/static/app.js`
  - `browser/static/style.css`
  - `docs/fleet/index.md`
  - `docs/fleet/operations.md`
  - `docs/guide/index.md`
  - `docs/index.md`
  - `guides/automation.md`
  - `prompts/goal-navigation-control-plane.prompt.md`
  - `references/automation.md`
  - `tests/test_browser_server.py`
  - `tests/test_vidux_contracts.py`
  - `evidence/2026-07-07-browser-verdict-dashboard-after-css.png`
  - `evidence/2026-07-07-browser-verdict-list-element-after-css.png`
  - `evidence/2026-07-07-kernel-cut-pivot.md`
- Exclude `evaluations/` from this package. It is untracked, 84M, has no tracked files, and differs from the canonical sibling `~/Development/vidux/evaluations/vidux-vs-native-bakeoff`; it should not be deleted, archived, staged, or committed as routine kernel-cut cleanup.
- Current transport caveat: this checkout is detached HEAD at `1e61606a2713875c1e9909e737a5de5f74b64ddf`. Create or choose an owned branch before commit/push.
- Exact staging command for this package:

```bash
git add PLAN.md README.md SKILL.md \
  browser/server.py browser/static/app.js browser/static/style.css \
  docs/fleet/index.md docs/fleet/operations.md docs/guide/index.md docs/index.md \
  guides/automation.md prompts/goal-navigation-control-plane.prompt.md references/automation.md \
  tests/test_browser_server.py tests/test_vidux_contracts.py \
  evidence/2026-07-07-browser-verdict-dashboard-after-css.png \
  evidence/2026-07-07-browser-verdict-list-element-after-css.png \
  evidence/2026-07-07-kernel-cut-pivot.md
```
- Staging receipt:
  - `git status --short` shows the owned package staged and `?? evaluations/` still untracked.
  - `git diff --cached --name-only` lists only the owned files above.
  - `git diff --cached --name-only | rg '^evaluations/' || true` returns no staged evaluation files.
- Proof 2026-07-07 after package:
  - `git diff --check` PASS.
  - `python3 -m py_compile browser/server.py` PASS.
  - `rg -n "lightweight orchestration system|Vidux orchestrates|Documentation is the control plane|planning control plane|Fleet Intelligence|ORCHESTRATED|Orchestration Mode|Default Discipline Swarm|Release Swarm|Vidux orchestrates — decompose, delegate, track" README.md docs guides references SKILL.md -S` returned no matches.
  - `curl -sS http://127.0.0.1:7192/api/health` PASS.
  - `python3 -m unittest tests.test_browser_server` PASS (69 tests, skipped=1).
  - `python3 -m unittest tests.test_vidux_contracts` PASS (220 tests, skipped=3).

## Branch Transport Receipt

- Branch: `codex/kernel-cut-cockpit-20260707`.
- Package commit before this closeout update: `8591c98 refactor: cut vidux kernel to cockpit`.
- Base correction: fetched `origin`, then rebased the package commit from detached `1e61606a2713875c1e9909e737a5de5f74b64ddf` onto current `origin/main` at `bf4fcc7`.
- Repo instruction correction: the rebase brought in repo-local `AGENTS.md`; its no-sign-off rule matches this package path and was read before continuing transport.
- Eval exclusion check: post-rebase `git status --short` shows only `?? evaluations/` outside the branch commit. No `evaluations/` path is staged or committed.
- Proof 2026-07-07 after branch transport:
  - `git diff --check` PASS.
  - `python3 -m py_compile browser/server.py` PASS.
  - `rg -n "lightweight orchestration system|Vidux orchestrates|Documentation is the control plane|planning control plane|Fleet Intelligence|ORCHESTRATED|Orchestration Mode|Default Discipline Swarm|Release Swarm|Vidux orchestrates — decompose, delegate, track" README.md docs guides references SKILL.md -S` returned no matches.
  - `curl -sS http://127.0.0.1:7192/api/health` PASS.
  - `python3 -m unittest tests.test_browser_server` PASS (69 tests, skipped=1).
  - `python3 -m unittest tests.test_vidux_contracts` PASS (220 tests, skipped=3).

## PR Nurse Receipt

- Branch pushed: `origin/codex/kernel-cut-cockpit-20260707`.
- PR: https://github.com/firstbitelabsllc/vidux/pull/189.
- Live GitHub readback:
  - state: OPEN.
  - draft: false.
  - mergeStateStatus: CLEAN.
  - Graphite `mergeability_check`: SUCCESS.
- Honest status at PR-nurse time: open PR, unmerged. Merge/findability truth supersedes this receipt below.

## Merge / Findability Receipt

- PR: https://github.com/firstbitelabsllc/vidux/pull/189.
- Merge method: GitHub squash merge.
- Merge commit on `main`: `634bf20efda9295db5a3df1b636055ed5919baf2` (`Cut Vidux kernel to thin cockpit (#189)`).
- Merged at: 2026-07-07T05:52:57Z.
- Verification:
  - `gh pr view 189 --json number,state,mergedAt,mergeCommit,url` reported `state: MERGED` and merge commit `634bf20efda9295db5a3df1b636055ed5919baf2`.
  - `git fetch origin main` moved `origin/main` from `bf4fcc7` to `634bf20`.
  - `git merge-base --is-ancestor 634bf20efda9295db5a3df1b636055ed5919baf2 origin/main` PASS.
- Shipping truth: the kernel-cut pivot is on `main`. Vidux is the thin plan/proof/decision/resume cockpit; it is not the planner-executor kernel.
- Boundary preserved: untracked `evaluations/` remains excluded and untouched.

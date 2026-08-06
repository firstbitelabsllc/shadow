# Shadow v4 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the Method to its tribunal-ruled 8-concept core, enforced by
`scripts/shadow-lint.py` instead of prose, with `shadow accept --row` as the
mechanical flip path and the amended deletions executed with their excision
manifests.

**Architecture:** The lint script lands first (the chief judge's binding
condition: no prose-law deletion without it), then the law rewrite
(AGENT.md v2 + grammar v2), then the acceptance engine extraction, then the
three deletions one commit each, then the board's lint surface, then
migration and release. Every task keeps the full existing gate matrix green;
deleted features take their test suites with them in the same commit.

**Tech Stack:** Python 3.10+ stdlib only (matches repo law), existing
unittest/vitest/Playwright gates, no new dependencies.

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-08-06-method-v2-core-design.md`; verbatim law text: `docs/superpowers/specs/2026-08-06-method-v2-debate/r2-ruling-06.md` §3 (AGENT.md v2) and §4 (grammar v2), amended by `r3-crossexam-postures.md` (BOX/VERDICT heads + four lint checks).
- Operator defaults in force unless overridden at the gate: D-1 A (no account-pinning surface), D-2 A (Langfuse deleted), D-3 A (Drive deleted now under binding conditions).
- Binding condition: any commit deleting prose law or coordination code must contain `scripts/shadow-lint.py` already landed (Task 1 precedes all deletions).
- Drive deletion binding condition: the same release ships `shadow accept --row` carrying `create_lead_review_worktree` (scripts/shadow-drive.py:538) and `lead_review_passes` (:548) verbatim, and rewrites PLAN.md's pending multi-lane successor row to the composed path.
- No new concepts: anything not named in the core eight or the folded sentences is out of scope for this plan.
- Version lands as 4.0.0; VERSION, package.json, package-lock.json, .claude-plugin/plugin.json, CHANGELOG.md move together (lock via `npm install --package-lock-only`).
- Every task ends with the focused suite green; Tasks 5–8 also run `npm run test:py` fully; the final task runs the complete matrix (`npm run test:all`, `docs:build`, `public-ready:grep`, `release:verify:dev`).

---

### Task 1: `scripts/shadow-lint.py` + test suite

**Files:**
- Create: `scripts/shadow-lint.py`
- Create: `tests/test_shadow_lint.py`
- Modify: `package.json` (add `"lint:plan": "scripts/shadow-python.sh scripts/shadow-lint.py"` to scripts)

**Interfaces:**
- Produces: `lint_plan(text: str, repo: Path | None = None) -> list[dict]` where each finding is `{"check": str, "line": int, "severity": "blocking"|"warning", "detail": str}`; CLI `shadow-lint.py [--repo <root>] <PLAN.md path>...` exits non-zero on any blocking finding; importable as module `shadow_lint` (file named with hyphen — load in consumers via `importlib.util.spec_from_file_location`, same pattern the tests already use for `shadow-drive.py`).
- Checks implemented (from grammar v2 LINT paragraph + postures amendment): `ID-DUP` (row IDs `~[0-9a-z]{4}` unique per plan), `NEEDS-DANGLE` (`needs:` targets exist), `PROOF-MISSING`/`PROOF-CLASS` (every row has `| proof:` classed `cmd `|`read `|`gate `), `DOD-COUNT` (exactly one `(DoD)` row per `###` milestone with ≥2 rows), `DOD-EARLY` (DoD `[completed]` while a sibling is not), `DEFER-NO-WAKE` (`## Deferred` row without `wake:`), `MODE-ILLEGAL` (`- Mode:` not `Broad`/`Close`; `Spike|Defer|Challenge` reported as legacy), `TS-ORDER` (Progress timestamps non-monotonic), `READ-FIT` (warning, any line >2,000 chars), `BOX-NO-END`, `BOX-EXPIRED-NO-VERDICT`, `ORPHAN-VERDICT` (warning), `CLOSE-OVER-OPEN-BOX` (blocking when `- Mode: Close` coexists with an expired unverdicted BOX), `CORE-FILE-UNROWED` (grammar v2's "changed core files map to a row": with `--repo <root>`, every path in `git diff --name-only HEAD` under `AGENT.md`/`SKILL.md`/`bin/`/`scripts/`/`browser/` must appear in some non-`completed` row's text or `proof:` argv — blocking; skipped, not passed, when no `--repo` is given so `lint_plan(text)` stays pure). Secrets in proof lines reuse `SECRET_SHAPE_RE` imported from `shadow_drive_lib`.

- [ ] **Step 1: Write the failing tests** — one test per check, each a minimal plan string, e.g.:

```python
def test_dod_early_flip_is_blocking(self) -> None:
    plan = (
        "## Operator Brief\n- Entity: demo\n- Mode: Close\n\n## Checkpoints\n"
        "### M — thing\n"
        "- [pending] first ~ab12 | proof: cmd true\n"
        "- [completed] done ~cd34 (DoD) | proof: cmd true\n"
    )
    findings = lint.lint_plan(plan)
    self.assertIn("DOD-EARLY", {f["check"] for f in findings})

def test_clean_v2_plan_has_no_blocking_findings(self) -> None:
    findings = lint.lint_plan(CLEAN_PLAN)  # fixture with every section legal
    self.assertEqual([f for f in findings if f["severity"] == "blocking"], [])
```

- [ ] **Step 2: Run** `python3 -m unittest tests.test_shadow_lint -v` — expect FAIL (module missing).
- [ ] **Step 3: Implement `shadow-lint.py`** — pure-stdlib line scanner: split sections on `^## `, milestones on `^### ` inside Checkpoints; regexes `ROW_RE = re.compile(r"^- \[(pending|in_progress|blocked|completed)\] (.+?) (~[0-9a-z]{4})( \(DoD\))? \| proof: (cmd |read |gate )(.+)$")` (tolerant variant accepts `| needs:`/`| size:` tails), `BOX_RE`, `VERDICT_RE`, ISO-timestamp capture for TS-ORDER. `CORE-FILE-UNROWED` is the one check that shells out (`git -C <repo> diff --name-only HEAD`, guarded by `repo is not None` and a non-zero-exit bail so a non-git path yields no findings). Deterministic ordering: findings sorted by (line, check).
- [ ] **Step 4: Run the suite** — expect PASS; also run `scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md` and record its findings count in the commit body (the flagship plan is expected to carry legacy findings; the CLI must not be wired into the blocking gate until Task 9 migrates the plan).
- [ ] **Step 5: Commit** `feat(lint): shadow-lint.py — the Method's mechanical enforcer`.

### Task 2: Law rewrite — AGENT.md v2, grammar v2, SKILL.md, contract tests

**Files:**
- Modify: `AGENT.md` (replace body with r2-ruling-06 §3 draft + the BOX/VERDICT sentences from r3-crossexam-postures)
- Modify: `docs/reference/method.md` (replace with grammar v2 from r2-ruling-06 §4, including typed proof classes, BOX/VERDICT Progress heads, ARCHIVE and LINT paragraphs, BOARD paragraph)
- Modify: `SKILL.md` (Method section: postures wording, lint reference)
- Modify: `tests/test_method_contract.py` (anchors: `Broad`, `Close`, `BOX`, `VERDICT`, `shadow lint`, typed proof classes `cmd |read |gate `, drop anchors for deleted concepts: `Spike`, `CHALLENGE`, `CLAIM`, `size:`)

**Interfaces:**
- Consumes: Task 1's check names (AGENT.md references `shadow lint` by name).
- Produces: the law text every later task's wording must match.

- [ ] **Step 1: Update contract-test anchors first**; run `python3 -m unittest tests.test_method_contract` — expect FAIL against old law.
- [ ] **Step 2: Write AGENT.md v2 and method.md v2** verbatim from the rulings (copy, then adjust only cross-references; no new sentences — additions are lint findings against the mega goal).
- [ ] **Step 3: Run** contract tests + `npm run docs:build` — PASS.
- [ ] **Step 4: Commit** `feat(method)!: the 8-concept core — AGENT.md v2 + grammar v2`.

### Task 3: `shadow accept --row` — the mechanical flip path

**Files:**
- Create: `scripts/shadow-accept.py`
- Create: `tests/test_shadow_accept.py`
- Modify: `bin/shadow` (add `accept` dispatch)
- Modify: `docs/reference/commands.md` (accept section replaces the drive table rows)

**Interfaces:**
- Consumes: `create_lead_review_worktree(repo, attempt, lane_id, commit)` and `lead_review_passes(worktree, proof, timeout_seconds)` — moved VERBATIM from `scripts/shadow-drive.py:538/:548` into `shadow-accept.py` (Drive imports them from here until Task 5 deletes it — no duplication window).
- Produces: CLI `shadow accept --row ~ab12 --repo <root> [--timeout-seconds N]`: parses the repo PLAN.md, locates the row by hash, requires state `in_progress|pending`, parses its `proof: cmd ...` argv (only `cmd` class is machine-runnable; `read`/`gate` refuse with a plain message), creates a detached clean worktree at HEAD under `<repo>-shadow-accept/<hash>/`, reruns the proof there, and on success rewrites the row to `[completed]` and appends `- <ts> ~ab12 PROOF <argv> -> pass (accept)` to `## Progress` in ONE commit; teardown removes the review worktree. Failure exits non-zero, touches nothing.

- [ ] **Step 1: Failing e2e test** — temp git repo with a v2 plan containing `- [in_progress] file says hello ~ab12 | proof: cmd python3 -c "import pathlib,sys; sys.exit(pathlib.Path('x.txt').read_text()!='hello')"` and a committed `x.txt` = `hello`; run the CLI; assert exit 0, row flipped, PROOF line appended, one new commit, worktree pool removed. Second test: proof fails → exit non-zero, plan byte-identical.
- [ ] **Step 2: Run** — FAIL (no script).
- [ ] **Step 3: Implement** — move the two functions verbatim; row edit via exact-line replace; commit with pathspec `PLAN.md` only.
- [ ] **Step 4: Run** suite + `python3 -m unittest tests.test_drive_prepare` (Drive still green consuming the moved functions).
- [ ] **Step 5: Commit** `feat(accept): shadow accept --row — clean-checkout proof rerun as the only flip path`.

### Task 4: Board lint chips + red cards

**Files:**
- Modify: `browser/server.py` (load `shadow_lint` via importlib next to the existing lib imports; `plan_record` gains `"lint": {"blocking": n, "warning": n}` and `"parse_ok": bool` — counts only, never finding text; parse failure yields a red-card record with `parse_ok: False` instead of best-effort counts)
- Modify: `browser/static/app.js` (board card: lint chip `lint ✓` / `lint n!`, `.board-card.red` when `parse_ok` false), `browser/static/style.css` (`.lint-chip`, `.board-card.red`)
- Modify: `tests/test_browser.py` + `browser/tests/e2e/board.spec.ts` (chip renders; a fixture plan with a DOD-EARLY violation shows `lint 1!`; finding text absent from the API payload)

- [ ] Steps follow the Task 1 TDD shape: failing browser unit test → implement server fields → failing e2e assertion → implement chip → `npm run test:e2e` PASS → commit `feat(board): lint chips and red cards — the board refuses to prettify`.

### Task 5: DELETE Drive (excision commit 1)

**Files (all removed in one commit):** `scripts/shadow-drive.py`, `scripts/shadow_drive_lib.py`→ KEEP (packet parser feeds nothing after deletion — verify: `extract_document` consumers are drive+browser preview; browser `drive_preview` dies here too) — Remove: `scripts/shadow-drive.py`, `tests/test_drive_prepare.py`, `tests/test_drive_launch.py`, `tests/test_drive_packets.py` (fold its two still-relevant grammar tests into `tests/test_shadow_lint.py` first), browser drive surface (`server.py` drive endpoints `/api/drive/*`, `run_drive_action`, `run_drive_subprocess`, `public_drive_session`, `drive_preview` + `app.js` `renderReadyWork`/`drive()` + related css + `test_browser.py` drive tests + `smoke.spec.ts` ready-work assertions), `bin/shadow` drive dispatch, `docs/reference/commands.md` drive rows, telemetry `record_drive`/`record_route` call sites.
**Also Modify:** `PLAN.md` — rewrite the pending multi-lane successor row (~line 1035) to: `run one real delegated row through fresh worktree + shadow host run + shadow accept --row on a customer repo`, and the Mechanical-proof `shadow doctor` row stays.

- [ ] Delete, then run `npm run test:py && npm run test:e2e && npm run docs:build` — green with suites removed; grep `-ri "drive" bin/ scripts/ browser/ docs/reference/commands.md` leaves only `shadow-accept.py`'s moved engine comments.
- [ ] Commit `feat!: delete Drive — the engine lives on in shadow accept --row` with the full excision manifest in the body.

### Task 6: DELETE roster/route/seat (excision commit 2)

**Files:** Remove `scripts/shadow_roster_lib.py`, `scripts/shadow_route_lib.py`, `scripts/shadow_seat_lib.py`, `scripts/shadow-roster.py`, `scripts/shadow-route.py`, `scripts/shadow-seat.py`, `tests/test_roster.py`, `tests/test_route.py`, `tests/test_seat_overlay.py`, `docs/reference/roster.md`, `docs/reference/routing.md`; Modify `bin/shadow` (drop the three dispatch entries), `scripts/shadow-host.py` per the cross-exam manifest (imports :28–30, `route_file_path`, `route_reference`, `--route-file`/`--roster-file`/`--use-seat`/`--seat-file` flags and guards, selector threading, `payload["route"]`; the frozen-task SHA-256 preflight in `shadow_task_lib` STAYS), `tests/test_shadow_host.py` (route/seat cases removed; bare `--host` cases kept), `docs/reference/native-hosts.md` + `commands.md` + `docs/.vitepress/config.ts` nav.

- [ ] Delete per manifest → full python suite + docs build green → commit `feat!: delete roster/route/seat — shadow host run --host is the whole delegation surface`.

### Task 7: DELETE Langfuse (excision commit 3)

**Files:** Remove `scripts/shadow_telemetry.py`, `tests/test_telemetry.py`; Modify `scripts/shadow-host.py` (drop `import shadow_telemetry` + `host_finished` call), `docs/reference/config.md` (drop `SHADOW_TELEMETRY` + three `LANGFUSE_*` rows + telemetry paragraph), `docs/reference/privacy.md` (telemetry section becomes one line: local receipts and git history are the only observation surfaces).

- [ ] Delete → suites + docs green → commit `feat!: delete the telemetry seam — git history is the trace store`.

### Task 8: Migrate Shadow's own PLAN.md to grammar v2

**Files:** Modify `PLAN.md` (typed proofs on open rows: `proof: cmd npm run verify` style; legacy `[completed]` strata untouched as receipts; `Mode: Close` already legal), Modify `package.json` (`"test:py"` gains `&& npm run lint:plan` so the flagship plan is now lint-blocking).

- [ ] Run `npm run lint:plan` → fix every blocking finding by edit or explicit `## Contradictions` row → gate wired → commit `chore(plan): flagship plan passes its own lint; lint joins the blocking gate`.

### Task 9: Version 4.0.0, changelog, release, reinstall, receipts

**Files:** `VERSION`, `package.json`, `package-lock.json`, `.claude-plugin/plugin.json`, `CHANGELOG.md` (4.0.0 section listing the core eight, the three excisions with their reactivation triggers, and the binding conditions honored), `PLAN.md` (Close-mode DoD proof lines for this milestone).

- [ ] Full matrix (`npm run test:all`, `docs:build`, `public-ready:grep`, `release:verify:dev`) → PR → hosted checks → merge → `gh release create v4.0.0` with packed tarball → `npm install -g` the downloaded artifact → `shadow doctor` (must pass with AGENT.md v2 content) → `shadow lint PLAN.md` clean on main → PLAN.md Close proof lines appended. Migration PRs for moussey/trysnowcubes/resplit plans (one-line `Mode` edits + typed-proof tails) ride as three follow-up docs PRs from fresh worktrees.

## Self-review

Spec coverage: core eight → Tasks 2 (law), 1+8 (lint enforced), 3 (flip path), 4 (board); amendments → Task 1 (BOX checks), 5 (Drive binding), 6 (roster manifest), 7 (Langfuse); migrations → 8–9. Placeholders: none — every deletion names its files, every creation names its interfaces. Type consistency: `lint_plan` finding shape used by Tasks 1, 4, 8; the two moved functions keep their exact drive signatures.

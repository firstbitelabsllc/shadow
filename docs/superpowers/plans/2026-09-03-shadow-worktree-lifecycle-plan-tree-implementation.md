# Worktree Lifecycle + Plan Tree Implementation Plan

> **For agentic workers:** Use subagent-driven development. Work task-by-task with failing tests first, one shared owner per invariant, and focused proof before broader proof.

**Goal:** Implement the approved `shadow clean` and browser Tree contracts without touching any pre-existing worktree.

**Architecture:** A small importable clean module reuses lifecycle inspection/transactions and root-board/plan parsing. Immutable creation receipts bound to Shadow's managed-worktree creation primitive are the only discovery source. Apply locks then atomically moves the exact worktree to Trash while keeping its Git registration recoverable. Browser Tree is a pure extension of the existing `/api/plans` projection.

**Tech stack:** Python 3 standard library, Git, Bash dispatcher, existing dependency-free browser shell, `unittest`.

## Task 1: Freeze provenance and preview

**Files:**
- Create `scripts/shadow_clean.py`
- Create `scripts/shadow-clean.py`
- Create `bin/shadow-clean`
- Create `tests/test_clean.py`
- Modify `bin/shadow`
- Modify `schemas/retirement-manifest.v1.json` only if the shared validator requires it; prefer a separate strict clean-manifest schema.

1. Write failing tests for immutable creation receipts, forged/pre-existing refusal, default zero-write explanation, fresh manifest generation, expiry, and changed-manifest refusal.
2. Add the managed-worktree creation primitive and `shadow clean --create`, requiring an exact live claim and absent destination.
3. Build clean preview from creation receipts only; delegate Git/plan checks to existing lifecycle/root-board owners.
4. Add dispatcher/help and docs without changing `shadow lifecycle` compatibility.
5. Run `scripts/shadow-python.sh -m unittest tests.test_clean.CleanPreviewTests -v`.

## Task 2: Trash apply and restore

**Files:**
- Modify `scripts/shadow_clean.py`
- Modify `scripts/shadow-lifecycle.py` only to expose shared inspection/receipt primitives cleanly
- Modify `tests/test_clean.py`

1. Write the full failing refusal matrix: primary, dirty, untracked, ignored, unlanded, active claim, process-held, symlink, submodule, expired/changed manifest, post-preview mutation.
2. Add bounded cross-platform process inspection that fails closed when unavailable.
3. Under the existing project lock, revalidate, lock the Git worktree, write the private journal, and same-device rename the exact inode to Trash. Assert no remove/prune/force invocation.
4. Add exact restore: validate receipt/inode/locked registration, rename back, verify, unlock, and finalize the private receipt.
5. Prove crash points before lock, after lock, after journal, after rename, and after public receipt are retryable or explicitly recoverable.
6. Run `scripts/shadow-python.sh -m unittest tests.test_clean.CleanApplyTests -v`.

## Task 3: Lifecycle-only automatic cleanup

**Files:**
- Modify `scripts/shadow_clean.py`
- Modify the narrow post-success seams in `scripts/shadow-accept.py` and `scripts/shadow-lifecycle.py`
- Modify `tests/test_lifecycle.py`
- Modify `tests/test_shadow_accept.py`

1. Write failing tests for strict computer preference, disabled default, one enabled call at a successful terminal boundary, and zero calls from status/browse/install/cold start.
2. Add `shadow clean --auto enable|disable|status` with isolated-home tests; do not enable it on the development computer.
3. Call the shared clean boundary exactly once after durable success. Preserve success while reporting individual refusals; never retry in a loop.
4. Run `scripts/shadow-python.sh -m unittest tests.test_lifecycle.LifecycleAutomaticCleanupTests tests.test_shadow_accept -v`.

## Task 4: Canonical Tree payload

**Files:**
- Modify `browser/server.py`
- Modify `tests/test_browser.py`

1. Write failing payload tests for the complete hierarchy and every required field.
2. Extend the existing milestone projection with an include-completed mode and safe proof/wake fields.
3. Build `tree` from the root-board payload and already-projected canonical entities; attach sanitized lifecycle summaries by entity/checkpoint.
4. Add negative tests for private paths, secrets, raw manifests, Git refs/OIDs, broken/symlink plans, and forged lifecycle receipts.
5. Run `scripts/shadow-python.sh -m unittest tests.test_browser.BrowserTreeProjectionTests -v`.

## Task 5: Accessible Tree UI

**Files:**
- Modify `browser/static/index.html`
- Modify `browser/static/app.js`
- Modify `browser/static/style.css`
- Modify `tests/test_browser.py`
- Modify `tests/test_browser_shell.py`

1. Read the UI craft floor immediately before editing.
2. Write failing source/DOM tests for the Tree toggle, nested semantic structure, keyboard operation, empty/unavailable states, required labels, and no write control.
3. Render native details/summary hierarchy with existing state chips, typography, focus behavior, and responsive breakpoints.
4. Run the Impeccable detector once over the changed UI files and address every material finding.
5. Run `scripts/shadow-python.sh -m unittest tests.test_browser.BrowserTreeRenderingTests tests.test_browser_shell -v` and the visual harness when available.

## Task 6: Docs, release, and stranger proof

**Files:**
- Modify `README.md`
- Modify `docs/reference/commands.md`
- Modify `scripts/shadow-release-package.py` and package allowlists only as required for the new owned files
- Create `evidence/worktree-lifecycle-plan-tree/release-receipt.md`

1. Document preview, create provenance, fresh manifest/apply, restore, auto opt-in, Tree authority, and refusal language.
2. Run focused clean/lifecycle/browser tests, then full discovery and the canonical gauntlet from a clean checkout.
3. Build the release archive and run stranger install/doctor/command help from isolated HOME.
4. Record source SHA, exact exits/counts/skips, refusal matrix, Trash recovery, lifecycle trigger, Tree render, package digest, and before/after real-worktree inventory.
5. Do not run real `shadow clean --apply`, restore, or auto-enable against the development machine.

# Task 4 implementer report: Canonical Tree payload

## RED

Command:

```text
scripts/shadow-python.sh -m unittest tests.test_browser.BrowserTreeProjectionTests -v
```

Result: the new focused tests failed with the expected missing-feature errors: `browser.server` had no `tree_projection`, and the shared grammar had no `deferred_wake_projection`.

## Implementation

- `scripts/shadow_plan_grammar.py` now owns strict Deferred wake parsing. It requires exactly one Deferred entry naming the row and exactly one non-empty `wake:` field, including suffix headings and duplicate/missing refusal.
- `scripts/shadow_root_board.py` routes blocked claim-return validation through that parser while preserving the existing `BoardError` message and state checks.
- `browser/server.py` extends milestone projection with an explicit `include_completed` mode and projects safe proof `{class,text}`, wake, and authenticated lifecycle worktree `{id,state}` fields. `tree_projection` joins canonical root-board projects/entities and already-projected plans into `computer -> project -> entity -> milestone -> checkpoint`, and `/api/plans` carries it beside `plans`.
- Tree output uses only canonical project `id`/`priority`; source plans are public locators, integrity is `ok`/`broken`/`unavailable`, and unsafe private paths, secrets, Git refs/OIDs, raw manifests, and standalone receipts are withheld.
- Tests cover complete hierarchy/field sets, completed rows, wake/proof privacy, broken/symlink plans, injected project names, standalone receipts, single-endpoint API shape, and root-board duplicate/missing wake parity.

## GREEN

Focused proof:

```text
scripts/shadow-python.sh -m unittest tests.test_browser.BrowserTreeProjectionTests -v
```

Result: `Ran 6 tests ... OK`.

Directly affected proof:

```text
scripts/shadow-python.sh -m unittest tests.test_browser.BrowserTreeProjectionTests tests.test_root_board.ReleaseStateSpeaksTheOneGrammar tests.test_grammar_contract.GrammarContractTests -v
```

Result: `Ran 19 tests ... OK`.

Affected browser suite:

```text
scripts/shadow-python.sh -m unittest tests.test_browser -v
```

Result: `Ran 67 tests ... OK`.

`python3 -m py_compile browser/server.py scripts/shadow_plan_grammar.py scripts/shadow_root_board.py`, `scripts/shadow-python.sh scripts/shadow-style-guard.py`, and `git diff --check` passed.

## Self-review and concerns

No UI, cleanup/apply/restore, daemon, scheduler, worktree, board, or external state was changed. Tree calls only the Task 1 authenticated public clean preview; malformed/standalone lifecycle records are ignored. The API recomputes canonical plan projection for completed history, so a slow or changing plan read can surface as broken/unavailable rather than raw content. Full release/install/live proof remains Task 6.

# Task 1 implementer report: Freeze provenance and preview

## RED

Command:

```text
scripts/shadow-python.sh -m unittest tests.test_clean.CleanPreviewTests -v
```

Result: `setUpClass ... ERROR`; the focused test module failed to import because `scripts/shadow_clean.py` did not yet exist. This was the expected feature-missing red.

## Files

- `scripts/shadow_clean.py` — pending-to-issued managed-worktree provenance, immutable receipt/journal authentication, zero-write preview, canonical manifest preparation/validation.
- `scripts/shadow-clean.py` — executable Python entrypoint.
- `bin/shadow-clean` — executable standalone launcher.
- `bin/shadow` — `clean` dispatch and help only.
- `schemas/clean-manifest.v1.json` — separate strict `shadow.clean-manifest.v1` schema; retirement schema remains unchanged.
- `docs/reference/commands.md` — preview/create/prepare contract.
- `tests/test_clean.py` — isolated temporary repositories/HOME tests.

## Design choices

Creation writes an exclusive mode-0600 pending journal before `git worktree add`; completion authenticates the exact live claim, source identity, destination registration, and source HEAD before writing a separate immutable mode-0600 receipt and issuing the journal. Retry accepts only the matching nonce and pending intent; a mismatched child remains untouched and unmanaged. Preview reads only receipt/journal pairs, emits an opaque `worktree@<digest>` identity, and never scans Git/filesystem worktrees. `--prepare` alone writes an exclusive digest-named manifest below the private clean manifests directory. No Trash, restore, automatic cleanup, or real developer worktree was touched.

## GREEN

Focused command:

```text
scripts/shadow-python.sh -m unittest tests.test_clean.CleanPreviewTests -v
```

Result: `Ran 7 tests ... OK`.

Affected compatibility proof:

```text
scripts/shadow-python.sh -m unittest tests.test_lifecycle -v
```

Result: `Ran 73 tests in 190.217s OK`.

Additional docs/dispatcher proof: `Ran 13 tests ... OK` (`tests.test_readme_contract` plus lifecycle dispatcher test). Style guard and `git diff --check` passed.

## Self-review

Confirmed no `git worktree remove`, `prune`, force flag, Trash, restore, auto-clean, scheduler, or background loop was introduced. Public create output is limited to schema/state/opaque identity; private paths remain in private records and the explicit prepare response. Receipt and journal reads are no-follow, bounded, regular-file reads with identity checks. Canonical receipt/journal digests, source identity, common Git directory, admin directory, inode/device, HEAD, branch/detached state, claim, and landed ref are bound. Existing `shadow lifecycle` source and schema are unchanged.

## Commit

Commit SHA: `a0b2562a` (`clean: freeze managed worktree provenance and preview`; final amended SHA will be reported by the implementer).

## Concerns

Task 2 owns lifecycle/plan terminal-state checks, process-held checks, Trash apply/restore, and post-preview CAS enforcement; this Task 1 surface intentionally stops at authenticated preview and manifest preparation.

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

Confirmed no `git worktree remove`, `prune`, force flag, Trash, restore, auto-clean, scheduler, or background loop was introduced. Public create and prepare outputs are limited to schema/state/opaque identities, safe expiry, and exact CAS; private paths and raw receipt/journal/manifest fields remain private. Receipt, journal, and manifest reads are no-follow, bounded, regular-file, owner-checked mode-0600 reads with identity checks. Canonical receipt/journal digests, source identity, common Git directory, admin directory, inode/device, HEAD, branch/detached state, claim, and landed ref are bound. Existing `shadow lifecycle` source and schema are unchanged.

## Commit

Initial implementation commit: `401ae1fb80f6a5ea76739900420f1c5e0f1d0733` (`clean: freeze managed worktree provenance and preview`).

## Concerns

Task 2 owns lifecycle/plan terminal-state checks, process-held checks, Trash apply/restore, and post-preview CAS enforcement; this Task 1 surface intentionally stops at authenticated preview and manifest preparation.

## Review fix

### RED

Command:

```text
scripts/shadow-python.sh -m unittest tests.test_clean.CleanPreviewTests -v
```

Result: `Ran 11 tests`; the new CLI post-add retry failed with `worktree destination must be absent`, the privacy assertions raised `KeyError` for the old private response, and the relaxed-mode falsifiers still admitted records (3 failures, 2 errors). The stale-claim falsifier initially exposed a test fixture mutation that violated board claim ordering; it was corrected to remain a valid but expired claim.

### Fixes

- Reordered pending-intent matching ahead of destination absence validation and made the ordinary CLI `--create` retry resume only an exact nonce/intent/claim/child match.
- Added `_locked_claim`, using the canonical `project_lock` first and root-board `_transaction` second, and held both through pending reservation, Git creation, revalidation, receipt write, and issued journal update.
- Enforced owner and strict 0600 checks for every clean receipt/journal/manifest read, including replacement of an existing journal.
- Kept the strict `shadow.clean-manifest.v1` private payload while returning only opaque manifest/worktree identities, expiry, and exact CAS. Added private canonical identity resolution for the later apply surface.
- Updated the governing design's contradictory prepare-output sentence to state the explicit privacy invariant (one ratified specification consistency correction); no other design section changed.

### GREEN

Final code revision tested: `ac0bcc95` (`clean: harden creation retry and private prepare output`).

Focused command:

```text
scripts/shadow-python.sh -m unittest tests.test_clean.CleanPreviewTests -v
```

Result: `Ran 12 tests in 17.953s OK`.

Safe affected documentation/dispatcher checks:

```text
scripts/shadow-python.sh -m unittest tests.test_readme_contract.AReadmeAStrangerCanFollow.test_the_readme_names_only_real_commands tests.test_readme_contract.ShareReadyDocumentationTests.test_acceptance_docs_describe_the_proof_boundary tests.test_readme_contract.ShareReadyDocumentationTests.test_readme_leads_with_authority_loop_and_install -v
bin/shadow clean --help
git diff --check
```

Result: `Ran 3 tests ... OK`; clean help advertised `--prepare` and `--create`; diff check passed.

Affected lifecycle compatibility suite (run against the same final code revision):

```text
scripts/shadow-python.sh -m unittest tests.test_lifecycle -v
```

Result: `Ran 73 tests in 157.566s OK`.

### Final-head evidence

The code/test/docs fix commit is `ac0bcc95`. Report-only follow-up commit `6d54f020` changed only this tracked report, so `ac0bcc95` remains the tested source revision and the report commit is traceable separately.

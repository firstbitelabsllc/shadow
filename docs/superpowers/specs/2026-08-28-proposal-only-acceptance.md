# Proposal-only acceptance

Status: **PROPOSED — design contract for `proposal/protected-authority`; not shipped.**

## Product call

**Agents change. The truth does not.**

Shadow keeps one authority for work state: the computer board plus each
entity's canonical plan. A coding host may propose that a checkpoint is
complete. It may not write the canonical row, proof receipt, source receipt,
history, resume pointer, or claim transition.

This is a Shadow feature, not a new product. It adds no daemon, scheduler,
router, queue, database, transcript store, credential relay, cloud authority,
or second status surface.

## The failure this closes

Today a host receipt is useful evidence, but evidence and acceptance remain
separate manual steps. If a worker can also write the authority it is asking
Shadow to trust, a convincing result can manufacture its own completion.

Proposal-only acceptance makes the split mechanical:

```text
source pass                         proposal pass                     trusted Shadow process
-----------                         -------------                     ----------------------
change product files                start from clean committed HEAD   resolve canonical authority
run bounded tests                   change no source files            verify the live claim
lead reviews and commits            request "complete"       ---->    bind plan root + source HEAD
                                                                      rerun authority-owned proof
                                                                      grade marker + execution floor
                                                                      synthesize canonical receipts
                                                                      commit one atomic transition
```

The worker contributes product changes and a request. Shadow contributes every
fact that becomes authority.

## Version-one boundary

Version one is deliberately narrow:

- The canonical plan is machine-local and outside the worker checkout.
- The worker runs through explicit Codex authority-proposal mode with a
  workspace-write sandbox and the default Codex executable.
- Source edits are reviewed and committed before a second, no-change proposal
  attempt binds one clean `HEAD`.
- The checkpoint has a machine-rerunnable `cmd` proof.
- The only requested transition is `pending` or `in_progress` to `completed`.
- Existing acceptance without a proposal keeps its current behavior.

Git-backed authority and other coding hosts stay unsupported until each has a
hostile-write probe proving that the worker cannot change its canonical plan.
`read` and `gate` proofs remain human judgments.

## Proposal contract

The worker may emit exactly one proposal object inside its existing
`shadow.host-receipt.v1` result:

```json
{
  "schema": "shadow.authority-proposal.v1",
  "entity_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "row_id": "~ab12",
  "owner": "<seat>",
  "base": {
    "plan_root_sha256": "64 lowercase hexadecimal characters",
    "source_head": "40 lowercase hexadecimal characters"
  },
  "request": {
    "transition": "complete"
  }
}
```

The object is closed:

- Unknown or missing fields are refused.
- It contains no Markdown, proof command, proof result, marker, floor,
  timestamp, commit message, source identity, resume pointer, or receipt text.
- It cannot request reopening, blocking, returning, publishing, merging,
  deploying, or changing another row.
- It cannot choose what evidence counts.

The host wrapper validates and preserves the proposal as untrusted evidence.
It never applies it.

The proposal pass is an explicit host mode:

```bash
shadow host run \
  --host codex \
  --work-class coding \
  --delegation direct \
  --authority-proposal \
  --repo . \
  --task-file /absolute/proposal-task.txt \
  --task-id propose-ab12 \
  --out .shadow/evidence/ab12-attempt.json
```

That mode accepts no source write paths and requires one sealed evidence file.
It refuses `--binary` and `SHADOW_CODEX_BIN` before launch, so the custom
executable seam remains available for ordinary adapter tests without being a
proposal authority path. It snapshots source `HEAD` plus Git config, refs,
hooks, index, worktree pointers, and excludes before launch; any drift makes
the attempt unsuccessful and strips the proposal.

## Authority-owned proof result

A proposal-enabled checkpoint declares its positive marker and minimum executed
count in the canonical row:

```text
| proof: cmd ./scripts/prove-authority.sh | marker: authority-proposal-pass | floor: 12
```

The proof command emits exactly one bounded result object:

```json
{
  "schema": "shadow.proof-result.v1",
  "result": "pass",
  "marker": "authority-proposal-pass",
  "executed": 12
}
```

Proposal acceptance requires all of the following:

- The process exits zero.
- The result schema and fields are exact.
- `result` is `pass`.
- `marker` exactly matches the canonical row.
- `executed` is an integer at or above the canonical floor.
- The detached proof checkout remains clean and at the frozen source commit.

The worker cannot lower the floor, guess a different marker, or replace a
structured result with prose.

## Trusted acceptance flow

The public command adds one argument:

```bash
shadow accept \
  --entity "$ENTITY_ID" \
  --repo . \
  --row '~ab12' \
  --by '<seat>' \
  --proposal .shadow/evidence/ab12-attempt.json
```

Before running proof, Shadow:

1. Loads one attempt receipt and extracts one authority proposal.
2. Rejects unsafe paths, extra objects, duplicate proposals, and unknown
   fields.
3. Resolves the entity from the current computer board.
4. Requires a machine-local canonical plan outside the source checkout.
5. Requires the exact row to be claimed by the exact owner.
6. Requires the proposal's plan root to equal the current canonical root.
7. Requires the proposal's source commit to equal the current committed
   source `HEAD`.
8. Re-reads the row and takes the proof command, marker, floor, dependencies,
   and contradiction state only from canonical authority.

Shadow then creates a detached checkout of the frozen source commit, reruns
the proof with an isolated temporary `HOME`, grades the structured result,
rechecks the plan root, source `HEAD`, row, claim, dependencies, and
contradictions, and synthesizes the canonical transition with the existing
acceptance transaction. Proposal proofs must be deterministic and cannot
depend on credentials or configuration stored in the operator's home.

The canonical `cmd` proof is trusted source code chosen by machine-local
authority and reviewed at the frozen source commit. This feature protects that
authority from the proposing worker; it does not sandbox an arbitrary malicious
proof command.

If publication or board finalization fails, Shadow restores the exact prior
authority and retains the claim for a deterministic retry. A proposal never
weakens the existing commit, push, remote-claim, or rollback rules.

## Refusal matrix

Every guard needs a planted mutant that turns the focused suite red.

| Mutant | Required result |
|---|---|
| Proposal mode names a custom Codex binary | Refuse before launch |
| Worker writes the canonical plan | Sandbox refusal; canonical root unchanged |
| Worker commits a changed proof or source tree | Attempt fails on source `HEAD` drift |
| Worker rewrites Git config, refs, hooks, index, or excludes | Attempt fails on Git control-state drift |
| Proposal uses a stale plan root | Refuse before proof |
| Proposal names the wrong entity or row | Refuse before proof |
| Proposal names the wrong owner or an unclaimed row | Refuse before proof |
| Source `HEAD` changed after the proposal | Refuse before proof |
| Proposal adds Markdown, proof, marker, floor, or timestamp | Schema refusal |
| Proof exits nonzero | Refuse; authority unchanged |
| Proof omits or guesses the marker | Refuse; authority unchanged |
| Proof reports zero or below-floor execution | Refuse; authority unchanged |
| Proof weakens its own canonical row during execution | Refuse on recheck |
| A second authority write fails | Restore the exact prior root and claim |

Test count is not the success condition. Success is that each planted fault
changes a passing acceptance into a refusal while preserving canonical bytes.

## Minimal implementation

The implementation stays inside existing owners:

- `bin/shadow` routes and documents `accept --proposal`.
- `scripts/shadow-host.py` validates one optional nested proposal in the
  existing host receipt.
- `scripts/shadow-accept.py` validates the proposal, grades the structured
  proof result, and reuses the existing canonical transition and rollback.
- `tests/test_authority_proposal.py` owns the focused mutation suite.
- Existing host and accept tests receive only compatibility regressions.
- `README.md` and `docs/reference/grammar.md` document the shipped contract
  only after the code passes.

No generic patch language is introduced. No worker-authored authority diff is
accepted. No existing acceptance path is rewritten merely to share vocabulary.

## Acceptance

The milestone passes when:

1. Direct authority writes, stale roots, wrong identity, changed source,
   marker failures, floor failures, proof weakening, and rollback faults all
   refuse with byte-identical authority.
2. One real personal-repository checkpoint completes through a Codex proposal.
3. A fresh process with a different seat reads the accepted successor from
   Shadow without receiving the prior transcript or worker receipt.
4. Focused tests, the full Python suite, release-package verification, and the
   Shadow gauntlet pass at one committed source head.

Until all four are true, the feature remains experimental and no release,
directory submission, hosted bridge, or broader host support is claimed.

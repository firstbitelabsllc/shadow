# Proof-pass harness traps

Mechanics for adversarial release/takeoff-class passes that cost real time to
rediscover. The pass contract (PASS.md) and the repo profile own the law; this
carries the operational traps.

## Resolve interpreter identity before trusting red OR green

Find which interpreter actually executes the gates versus which one the
product uses under its own install. Stdlib behavior shifts across versions
(a strict parser can reject the same input on 3.9 and accept it on 3.10+), so
a too-old interpreter flips unrelated lanes red with errors that imitate
product defects. Re-run the battery under the product's own interpreter
selection before diagnosing any red as a bug, and quote the interpreter in
the receipt. The durable fix lands in the harness, not the operator: have it
hunt the same interpreter locations the product uses, pin the whole harness
PATH to the choice (child drivers invoke plain `python3`), honor an explicit
override env var, and refuse a too-old interpreter with a named marker plus a
distinct exit code BEFORE any lane runs — a bare exit 1 five lanes deep reads
as a product failure.

## Dirty-tree refusals are gates working

Inspect the exact source-admission refusal before diagnosing downstream
failures. Host/build-from-source suites may reject uncommitted changes or
ignored artifacts even when ordinary `git status` looks clean. Compare the
committed bytes and modes, inspect ignored files, and replay only the admission
function against the retained input; do not rerun the author or send path.

Run Python inspection and tests with `-B` when importing a pinned installation:
imports can create ignored bytecode inside the source tree and invalidate its
inventory. Adding a no-bytecode setting to the producer does not constrain
independent inspection processes; protect the actual importing command.

When reviewed test-layer changes are the demonstrated cause, commit the exact
surgery paths on the named branch, then rerun the affected suites. Do not commit
unexplained changes merely to get green. If a wrapper discarded the underlying
exception, retain a bounded private diagnostic while preserving the original
refusal and no-retry behavior; current success does not recover lost history.

## Mutation mechanics

- Commit each planted mutation on a named throwaway branch with a PATHSPEC
  add — never a bare `git add -A`; the shake branch shares its worktree with
  the pass's evidence lane, and a bare add folds the receipt into the
  mutation commit.
- If a restore lands in the same commit as the next mutation (staged-restore
  sweep), the evidence sequence is still mutation → refusal → restore → green
  in history; state it in the ledger instead of rewriting.
- Took-proof means the refusal NAMES the expected code (pin/binding marker,
  behavioral assertion), not merely a nonzero exit.
- Restore = prove zero diff against the pre-mutation ref AND the gate green.

## Stamp and evidence placement

- A receipt whose repo inventory refuses untracked files during gates keeps
  its pre-declaration and lane logs EXTERNAL during the run; copy the receipt
  under the repo's `evidence/takeoff-pass/` only for the stamp.
- Stamp refuses a durable-copy collision: remove any pre-placed copy in the
  durable evidence root and let the stamp place it.
- Lane rows must parse as `- lane <name> rc=N marker="…" count=N` — a table
  of rc/marker/count in separate columns refuses.
- Marker count floors come from the repo's proof manifest; the discovery-run
  floor comes from the last stamped receipt, raised to current observed.

## Two proof surfaces can diverge

A repo can gate per-lane drivers AND a full discovery suite; a production
contract change whose PR updates the lane fixtures but not one discovery
test leaves every lane green while discovery stays red for weeks — nobody
runs discovery outside a pass. Run the discovery suite in every pass (floor
= last stamped count, raised to observed). A deterministic failure that
reproduces identically on repeat is contract drift, not a flake: find the
change that moved production behavior, move the test to the new contract,
re-pin any reviewed-byte pins, and land it through the repo's own review
flow.

## Re-prove at the landed ref

Test-layer surgery lands through the repo's own PR flow mid-pass. After the
squash merge, verify the landed commit is content-identical to the proved
branch (`git diff <proved-ref> origin/main` must be empty), detach to the
landed ref, and re-run the full battery — the receipt describes the ref the
battery actually ran at, not the branch the fix was written on. Quote the
re-run count in the memo.

## Sizing

Budget from the profile prior. Shake repeats on the newest lifecycle suite
plus one full-suite repeat when many PRs landed since the last stamp — a
deterministic single failure reproduced on repeat is a product/test finding,
not a flake.

## Host fallback and quota walls

- A host CLI that dies on quota before running any lane (usage-limit error in
  the log, no memo written) never executed the pass — re-dispatch the whole
  contract to an alternate host rather than reporting the quota as the
  outcome. Verify the alternate host's receipt lands with the same stamp door
  and template shape; the contract, not the CLI, is the program.
- Budget flags are per-invocation and advisory to the host, not enforcement:
  an advisor run that skips its self-check on remaining budget still delivers
  a complete verdict. Read the delivered verdict before treating a budget
  note as a failure.
- Headless advisor CLIs print pre-flight warnings from the CWD's
  `.claude/settings.local.json` (e.g. wildcard allow-rule complaints) before
  the answer — they are noise, not failures. Parse the answer body, not exit
  decoration, and keep the packet self-contained in the prompt so the advisor
  needs no follow-up turns.
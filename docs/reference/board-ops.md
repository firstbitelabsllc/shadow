# Shadow board operations (cold seat)

The `shadow` skill teaches the method and the happy path. This reference carries the
operational mechanics that cost real time to rediscover: what the verbs refuse,
where the true state lives, and how to retire physical material safely. All
rules assume a local per-computer board at `~/.shadow` worked from a Git
checkout under a stable seat name.

## Evidence-anchored probes

- Take every path, ref name, and hash from the owning plan's evidence files —
  never from recall. Probe the recorded path even when a likelier-looking
  location exists; receipts beat plausibility.
- Before declaring a referenced evidence file missing, search the owning
  plan's evidence directory (`~/.shadow/plans/<entity>/evidence/`) plus the
  product's evidence roots: contracts and profiles often cite repo-relative
  evidence paths while the durable copy lives outside the repo. A not-found
  at the first plausible location is a search gap, not proof of absence.
- A receipt's `archive/<name>` recovery-ref shorthand means
  `refs/heads/archive/<name>`. Probe a ref exactly as recorded; if it misses,
  enumerate `git for-each-ref` in the recorded store before declaring a
  mismatch — a namespace guess that fails is an instrument error, not a lost
  recovery ref.
- Resolve probe refs with `git rev-parse --verify <ref>^{commit}`; bare
  rev-parse prints the ref name on ambiguity and its failure hides inside
  pipelines. Never pipe a probe through a filter that swallows its exit code.
- The plan file is a content-addressed pointer, not the content. Read rows
  through the projection door `shadow read --entity <id> --find <literal>`
  (row/receipt lines with plan line numbers, JSON out) — discovery first with
  a broad `--find`, then close on an exact `--row '~id'` or `--receipt TAG:N`.
  Every call needs at least one selector and honors a byte/selector budget, so
  never loop row-by-row reads. Direct grep of `PLAN.d/objects/` is the
  fallback when `shadow read` is unavailable, not the default.
- Entity ids are not guessable: list `~/.shadow/board.json` `entities[]`
  (id → project → plan path) and pass the full logical id to `shadow read`.
  There is no plan-show verb — `shadow plan` is migrate/rollback/amend only.
- Verify on disk before acting on a row whose state moved since it was last
  reported: a completed row is verified and never reworked; a receipt proves a
  past state, not the present one.
- Fold independent reviews back into source evidence before implementing their
  recommendations. Reproduce each claimed failure at the relevant boundary;
  distinguish a plausible historical cause from an observed one. A clean
  replay now cannot exclude transient Git, file-mode, or source-artifact
  failures earlier, and a child verdict is not proof of those exclusions.
- Sibling seats work this board and its repos concurrently: a handoff receipt,
  your own earlier probe, and a git status can each go stale within one
  session. Re-verify the exact surface (commit, installed version, row state)
  immediately before acting on it, and phrase verification claims as
  "verified at <time>" — a receipt says when it was true, not that it still is.

## Claim lifecycle mechanics

- Read the stored claim shape in `~/.shadow/board.json` `claims[]` before
  adopting anything stale — the in-flight projection hides access, write_scope,
  and repository_binding. Adoption must reproduce the stored shape exactly:
  `--access` plus, for write claims, `--path` matching each stored write_scope
  entry; plus `--repo` when a binding exists. A shape mismatch refuses with a
  message that names neither the stored access nor the scope.
- Pass belongs in the observation RESULT TAIL: amend observations as
  `<what was observed> -> pass: <details>`. A head-prefixed `pass:` records
  fine and then accept refuses without saying where pass belongs.
- `shadow return` takes `--row '~id'` (never throw's `--task` flag) and no
  reason flag. Pre-record the parking reason with
  `plan amend --observation '... -> blocked: <exact wake>'`, then return.
- `plan amend` touches only rows the actor currently holds: it refuses with
  "not claimed" once the claim is returned. To record new work or a wake on an
  unclaimed row, run the short loop throw → amend → return in one sequence;
  do not leave the re-claim held — the return re-parks the row at the
  just-recorded wake.
- Accept refuses a milestone DoD row while any sibling row is pending
  (DoD-early). Drain siblings first; the refusal names the row, not the
  blocking siblings — read the milestone section to find them.
- Throw refuses a row already marked `[completed]`. When a wake instructs
  "re-observe and accept ~row", skip the claim step entirely: run `accept`
  directly with that wake's exact `--entity` and `--repo` — accept reconciles
  the outstanding recorded observation instead of re-claiming.
- A row completed on a HOLD verdict with owner-deferred follow-up has no
  reopen path: reopen opens blocked rows only, throw refuses completed rows,
  and no verb adds rows. Route the follow-up through a live pending row whose
  own text covers the work; if none covers it, park the decision with an exact
  wake instead of stretching a row's meaning. When the covering row is parked
  `[blocked]`, reopen is the entry door — the reason must differ from the
  row's parked wake — then throw, amend the verified observation, and return;
  that sequence records the correction without minting a row.
- `plan amend` exposes only `--proof` and `--observation`; there is no note or
  LESSON channel. Durable lessons go in the owning evidence file and the
  session report. Always pass `--entity <id> --row '~X' --by <seat>` — a
  positional `~id` after `amend` is not a row selector, and argparse then
  refuses the three required flags. Throw uses `--task`; amend uses `--row`.
- Free-text Progress folds on plan-tree plans ride the ruled note door
  (PlanTransaction), not a verb: `from shadow_plan_store import
  PlanTransaction` (import `shadow_root_board as board` too when wrapping a
  canonical plan in `board.project_lock(plan)`); then
  `tx = PlanTransaction.begin(plan, expected_root=<digest>,
  expected_generation=<n>)`, append to `tx.original_content.decode()`,
  `tx.replace_content(updated.encode()).publish()`. The refusers are the
  design: begin refuses a stale root/generation, publish re-checks the CAS
  under the root lock (a concurrent publisher wins — you are refused, never
  merged), the losslessness check refuses format drift, and any raw edit
  under the root fence fails closed at parse. Heal an appended fence with
  `restore_exact_root(plan, expected_current_root=digest(bytes on disk now),
  target_root_bytes=<known-good root>)` — the CAS expectation is the corrupt
  bytes, not the good root. Ruling and regression test live in the shadow
  source checkout: `scripts/tests/test_plan_note_door.py`. Cmd proofs that
  run pytest need it installed: `python3 -m pip install --user pytest`
  (works on the Apple CLT python3).
- Mint a machine-local entity with `shadow init --here` run from inside a Git
  worktree — a plain directory refuses, so create a dedicated empty carrier
  repo first rather than reusing a product checkout. No verb mints rows, so
  new work rides the template's pending rows via `shadow plan amend` (the
  top-level CLI has no `amend`).
- Resolve entity IDs from `shadow status --json` `v4_plans[]` — it pairs
  `entity_name` with `next_unclaimed` in one view. Sibling entities share
  name stems, and `throw` refuses a row the named entity's stored plan does
  not carry, so match the full logical id, never a name prefix.
- Keep shell `$` sequences out of `plan amend --observation`/`--proof`
  strings: they are expanded before storage and silently corrupt the receipt
  text. Write words ("at zero new cost") instead of `$` tokens.
- Machine-local rows: accept requires `--repo <proof-source-checkout>` even for
  read-class rows. Committed product-repo entities: `--entity` combined with
  `--repo` refuses — throw repo-first (`shadow throw --repo <checkout>`), which
  reads the row from that checkout's plan; refresh `origin/main` in a clean
  detached worktree first and throw from there when the primary checkout is
  dirty or on another branch, then remove the probe worktree. Parking a product
  row must ride the repo's own review flow: plan amend refuses committed plans,
  so if the wake is already durably recorded in the plan, adopt-then-return is
  the complete recovery.
- A stale foreign claim pointing at a superseded plan generation (the row was
  re-blocked or re-scoped upstream) is a structural dead end: adopt refuses and
  return is owner-only. Document it in the session report and stop — never
  force a board repair by hand.
- When `throw` refuses with "still needs <row>", walk the gate chain before
  picking another target: read each named row (`shadow read --entity <id>
  --row ~XX`) and follow its `needs:` links to a claimable pending row or a
  blocked root. If every pending frontier funnels into blocked rows whose
  proof is a person readback (edition review, usefulness check), no claim is
  reachable — do not force one. Stage the machine-observable half instead:
  read-only probes at the natural occurrence and a recorded landing place
  for the evidence. Reuse an existing authorized observer rather than adding
  a schedule to work around a blocked row. These probes prove only their
  observed stage, not acceptance of the blocked row.
- Distinguish technical blockers from person judgments. A missing scheduled
  artifact is an execution incident, not a request for the person to approve
  an artifact they never received. Investigate the producer and its failure
  signal before returning to editorial or usefulness gates.
- Before promising an automated follow-up, verify the saved schedule,
  timezone, next fire, actual destination, and one executed result. Local-only
  output is a saved report, not a notification; observer success can correctly
  report producer failure. Bind evidence to the requested run identity instead
  of the last successful line in a shared log.
- For correction duties, distinguish capture, reviewed disposition, source
  change, installation, and changed runtime behavior. Prove each claimed
  transition; a captured reply or evidence hash does not implement a fix.
  Preserve the actual authorization boundary: routine reversible corrections
  do not acquire a new person-approval gate merely because they came from
  feedback, while sends and protected actions still require exact approval.
- When an administrative limit blocks repair, inspect the existing recovery
  path and explain the specific scope of any required limit change. Once the
  user authorizes that change, execute and test it rather than asking them to
  find another owner. Check the new boundary and its rejecting negative case,
  preserve unrelated safeguards, and report local versus upstream state.
  Concretely for hot-plan capacity: the byte ceiling is a source constant
  (`HOT_PLAN_MAX_BYTES` in Shadow's `shadow_root_board.py`), not a per-plan
  setting; `lifecycle --self-compact` drops only exact-duplicate receipts and
  progress archival needs an archive-eligible milestone. Tests hard-code
  `288 * 1024`; an uncommitted raise to 320 with those tests unchanged is
  unauthorized dirt — `git restore` the file so `skillbox doctor --strict`
  can pass. Do not commit a new ceiling without updating those tests and
  owner authority; a raise still needs the admit/refuse-one-byte-over proof
  and a reopen reason distinct from the parked wake.

## Physical retirement claims

- Run TTY-confirmed cleanup tools (per-category y/N scripts) from automation
  through a background pseudo-terminal, answering each prompt with the
  process manager's submit action and polling between prompts; submit each
  confirm exactly once and only after the operator's approval covers that
  scope — re-submitting after a wait timeout can answer a prompt the tool
  already consumed. Never strip or bypass the confirm itself.
- A blanket approval of a presented decision ledger authorizes every listed
  item: execute the whole set without re-confirming each one, and do not put
  routine reversible preparation back on the person.
- Re-verify every custody anchor immediately before removal: archive SHA-256
  against manifest, `lsof -b -n -P +D` per root, and a bounded status against
  the parent store. Claim the row before any mutation.
- Record `df -k /System/Volumes/Data` before and after; logical size does not
  predict reclaim — APFS clone sharing can leave most of the logical bytes
  physical.
- Baseline the row's own predicate, not a proxy: a whole-container DoD reads
  `diskutil apfs list diskN` → `Capacity In Use By Volumes`, which includes
  volumes a Data-volume `df` never sees. Report both when the plan names the
  container.
- Read the census column contract before aggregating: the main TSV is
  origin/path/class; the sidecar size is a KiB upper bound, never bytes or
  physical reclaim. Require the current invocation's successful exit and
  final stdout completion line. TSV existence or an older `.done` file proves
  neither completion nor full coverage; reusable markers can survive failed
  reruns beside truncated data. A completed report can still contain UNKNOWN
  measurements, and no census classification alone authorizes retirement.
- Agent processes without Full Disk Access get `Operation not permitted`
  reading `~/.Trash` — that TCC seal is the design working, not a failure to
  retry; the Trash inventory and its per-item disposition belong to the owner.
- Verify Docker through its selected local context and a bounded engine API
  probe before inventory or pruning. A timeout or refused socket is UNKNOWN,
  not zero containers and not evidence of a login or first-run dialog. Inspect
  the actual native window before naming a UI blocker. Preserve volumes and
  unverified container writable layers; prune only exact approved disposable
  artifacts after live-use checks. Do not restart another owner's services
  merely to force an inventory response. After an explicitly approved
  maintenance recovery, require a fresh engine health response and live
  inventory; CLI exit 0 with “already running” is not health. Treat absent
  container Health fields as unconfigured, not failed. Do not prune when the
  live inventory has no eligible cache or dangling images.
- Root ownership and a plausible regeneration story are not a supported
  removal contract. Simulator dyld caches remain report-only: do not issue
  `sudo` or a blanket manual deletion command, even as an owner paste-line.
  Runtime removal requires an exact supported Xcode action, active dependency
  clearance and physical backing/free-space proof. `Volumes/`, `Cryptex/`
  and `Images/` directory totals are not additive reclaim estimates.
- Reconcile an interrupted process before retrying. Census TSVs are appended
  during execution, so their presence does not prove the run finished. Recover
  the actual terminal status and this run's completion output; otherwise mark
  coverage partial and retain usable evidence without inventing completion.
  - A finished delegate's shortened live log may omit its full verdict: recover
    available terminal proof, but do not label an unseen static verdict a pass.
  - When a cheap child 429s on a read-only probe, run that probe natively on
    the lead. Do not re-dispatch into the same limit.
- Remove with `git worktree remove` when registered; otherwise `mv` to
  `~/.Trash` so removal is recoverable. Never rm -rf a checkout.
- Detect an iCloud-evacuated tree before treating it as trash: du near zero
  across thousands of entries and `stat` showing the `dataless` flag. Deleting
  such placeholders propagates the delete to the cloud copy (often the only
  remaining bytes), reclaims ~0 physical space, and any git status or
  inventory walk over the tree hangs while triggering mass materialization —
  probe such trees with stat/metadata only.

## Session ledger

- Append every run to the seat's dogfood report file (`run-N.md`), stub first
  and update after each step; it is the friction ledger and the resume point.
- Update the seat's persistent memory with settled verb facts, but keep this
  skill as the procedure home; memory entries stay one-line facts.

## Reference

- `board-ops/verb-refusals.md` — refusal text to cause to exact fix, one row
  per verb surface.
- `board-ops/proof-harness-traps.md` — release/takeoff-pass mechanics:
  interpreter identity, mutation and stamp doors, evidence placement.

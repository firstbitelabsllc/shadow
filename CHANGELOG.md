# Changelog

## 3.0.0 — 2026-08-05 — Shadow

- The product is renamed to **Shadow** ("you are my shadow"): repository,
  package, command (`shadow`), skill, browser identity, docs, scripts, tests,
  environment variables (`SHADOW_*`), schema identifiers (`shadow.*.v1`), and
  the project state directory (`.shadow/`). No aliases or shims are kept;
  prior `pilot-puppy` history remains in this changelog and the plan as
  receipts. GitHub redirects the old repository URL.

## 2.3.2 — 2026-08-05

- The Briefs shell now actually hides while the Board view is active; it
  previously rendered below the board because a layout rule overrode the
  hidden attribute. Pinned by an e2e assertion.

## 2.3.1 — 2026-08-05

- Plan discovery prunes worktree pools (`*-worktrees/`), which flooded the
  plan cap with duplicate lane copies on real machines and starved the board
  of the canonical plans.

## 2.3.0 — 2026-08-05

- The Method ships as standing behavior: `AGENT.md` (one chief-of-staff
  identity, Spike/Defer/Challenge/Close with a transition law, the adversarial
  gate, planning-is-writing, transfer-the-lesson) plus the machine-readable
  file contract in `docs/reference/method.md` — entities as greppable plan
  lines, milestones as headings, checkpoint rows with hash-stable IDs,
  `proof:` commands and `needs:` readiness, append-only CLAIM/PROOF/DONE
  multiplexing, PLAN-LINT, and the Close coverage matrix with a mandatory
  lesson delta.
- The browser gains a read-only Board view: entity lanes, project cards with
  mode chip, current milestone, checkpoint counts, and a waiting-decision
  marker. Counts only; the board's single interactive element is card select.

## 2.2.1 — 2026-08-05

- Drive no longer blocks or strands green work on ignored build artifacts or
  on its own `.pilot-puppy/` evidence: interpreter caches and dependency
  installs are recorded for review instead of failing scope, and acceptance
  validates the staged merge result — exactly what the commit contains.
- The loopback page can no longer receive private paths or secret-shaped
  text: reflected error text is fixed plain English, and the title, brief,
  and outcome filters now match the canonical evidence gates.
- A lane declared `merge: "manual"` is checked and reproduced like every
  other lane but stays on its kept branch for the person to merge.
- Every lane that needs attention names its reason in plain English, and a
  missing Git commit identity is refused before any host starts.
- Browser and CLI time budgets nest, so the CLI's own bounded step timeouts
  are always the effective limit; a backstop stop is reported honestly.
- An interrupted Drive session relaunches without re-spending finished
  lanes, and concurrent launches or accepts of one session are refused by a
  local lock.

## 2.2.0 — 2026-08-04

- Supervised Drive prepares up to three separate local coding lanes from the
  existing project plan and starts them only when the person explicitly asks.
- A fully green Drive session can now be independently rechecked in a clean
  copy and brought into the local project with one explicit Git merge.
- Optional Langfuse lifecycle observation remains off by default, sends only
  closed metadata after local evidence exists, and cannot alter local work.

## 2.1.0 — 2026-08-03

- Local generic roster for `lead`, `planner`, `bulk`, `debug`, `critic`, and
  `hard-ic` roles.
- Foreground `route` command that explains a deterministic role/native-host
  choice, alternatives, and escalation without launching work.
- Fail-closed route-to-host binding for the frozen task, route-safe roster
  revision/hash, selected enabled slot, and native host.
- No cloud executor, credential relay, transcript store, queue, daemon,
  watcher, or provider-model router.

## 2.0.0 — 2026-08-03

- One Pilot Puppy product, repository, package, command, skill, and UI.
- Repository-owned Outcome, plan, proof, and resume authority.
- Calm chief-of-staff briefing with an honest A/B/C decision receipt.
- Sealed native-host tasks for Codex, Claude Code, and Cursor.
- One atomic, idempotent, project-local evidence path.
- No secondary store, background machinery, or duplicate product surface.

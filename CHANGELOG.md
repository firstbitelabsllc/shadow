# Changelog

## 4.0.3 — 2026-08-07 — goal shaping ships with the skill

- SKILL.md gains "Shape a goal": the gather/synthesize/cut/deliver method
  and the paste-ready goal template (Outcome / Authority / Resume / Scope /
  Proof / Policy), so every mounted session shapes loose asks into
  executable briefs the same way. One folded law line in AGENT.md. The plugin also ships it as a standalone `goal` skill
  (skills/goal/SKILL.md). A method, not machinery — no new commands.

## 4.0.2 — 2026-08-07 — the trust audit lands

A 17-agent full-coverage thermo/ponytail audit (every file assigned by
name, every block adversarially verified by execution) confirmed nine
defects; all are fixed here with regression tests:

- lint: a typo'd `## Tasks` heading can no longer exempt its rows from
  every check (ROWS-WITHOUT-TASKS blocks); the secret scan now covers the
  whole plan (PLAN-SECRET) — including pasted command output in Progress
  PROOF lines — with a left-guard on `sk-` so hyphenated English stops
  false-positiving.
- host: the execution timeout now governs even when a wedged host never
  reads stdin (writer thread); a pre-existing `--out` refuses before the
  host runs instead of after; nested evidence directories no longer
  contradict the sealing check.
- board: the outcome projection enforces the proof-delivery vocabulary
  and the finished-with-proof coupling the canonical validator requires;
  the stylesheet stops referencing design tokens that were never defined.
- packaging: the public-ready gate reuses the canonical secret shape
  instead of carrying a third, weaker transcription.

## 4.0.1 — 2026-08-07 — the board reaches your phone

- `shadow browse --allow-host NAME` (repeatable): opt-in Host-header
  allowlist for a proxy the operator runs on the same machine — e.g.
  `tailscale serve` — so the board and its A/B/C decisions work from a
  phone on the tailnet. The bind never leaves loopback: proxied requests
  still arrive from 127.0.0.1, unlisted hostnames still get 403, and a
  non-loopback `--host` is still refused outright.

## 4.0.0 — 2026-08-06 — the eight-concept core

- **Standard vocabulary only.** Shadow is the one invented name; everything
  else is a standard word: project, milestone, task, lane, spike, brief.
  `## Operator Brief` → `## Brief`, `## Checkpoints` → `## Tasks`,
  `- Entity:` → `- Project:`, `Mode: Broad | Close` → `Mode: explore | ship`,
  `BOX`/`VERDICT` spike heads → `SPIKE`/`DECISION`, "the Method" and "gate
  pair" jargon retired (the law is just AGENT.md + `docs/reference/grammar.md`,
  and the two questions: why now? what does this contradict?).

The Method is reduced to its tribunal-ruled core, enforced by code instead of
prose. Produced by a three-round adversarial debate (design spec + records in
docs/superpowers/).

- **Eight core concepts:** the plan file; the checkpoint row with a typed
  `proof:` (`cmd`/`read`/`gate`); two postures (`Mode: Broad | Close`); Defer
  as a write; the gate pair (why-vs-exploring, what-does-this-contradict);
  Close (the harness defines done); the milestone (one DoD row); entity line +
  read-only board.
- **`scripts/shadow-lint.py`** is the mechanical enforcer — fourteen
  deterministic checks including the BOX/VERDICT exploration lifecycle — and
  runs at the tail of `test:py`. No prose-law deletion landed without it.
- **`shadow accept --row`** reruns a row's `cmd` proof in a clean detached
  checkout and is the only code path that flips a row to completed, carrying
  the retired Drive engine's clean-checkout review verbatim.
- **Deletions (~2,500 lines), each with a written reactivation trigger:**
  Drive (packet/lane vocabulary; the engine survives in accept); roster /
  route / seat (bare `shadow host run --host X` was always the complete sealed
  path); CLAIM/DONE bookkeeping; the Langfuse telemetry seam (git history is
  the trace store). Pre-rename compatibility from v3 is retained.
- The board renders a lint chip per card and blocking findings as a red card. AGENT.md is one page; the grammar is `docs/reference/method.md`.
- A 19-agent adversarial challenge of this release confirmed 12 defects by
  execution (0 refuted); all fixed before tagging. The worst three were in
  the enforcers: lint's field parser truncated at embedded pipes (hiding
  secrets and shortening the command accept reran — a false-green through
  the only flip path), typo'd state tokens were invisible to every check,
  and accept read its proof from row prose instead of the parsed tail.
  `shadow checkpoint` (a second, unverified flip path) is deleted.

## 3.0.1 — 2026-08-06

- AGENT.md — the Method's standing-behavior file — now actually ships in the
  npm package, and `shadow doctor`'s product-identity check requires it at the
  installed root. Found by the Round 1 stress adversary: the v3.0.0 plan row
  claiming "the Method rides the installed mounts" was proven by a doctor run
  that never checked for the file, which was absent from the package. The
  claim-vs-world-state gap the Method exists to prevent, caught in its own
  plan.

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

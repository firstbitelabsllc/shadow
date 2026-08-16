# Changelog

## 1.1.1 — 2026-08-16 — the release artifact stops carrying host-private runtime

- 1.1.0 was tagged before two fixes merged, so its tarball still shipped
  `scripts/shadow-brief.py` — 380KB of retired, host-private runtime carrying
  three personal email addresses and a store id — plus an orphan asset. Trunk
  had already export-ignored and then deleted both; this release is the first
  artifact that actually reflects that.
- The deterministic brief producer, its verb, its help, its dispatch, its
  tests, and its CI lane are gone (17,492 lines). The digest is authored by a
  native host through the operator's own scheduled job.
- A live-host test no longer reports machine contention as a product failure.

## 1.1.0 — 2026-08-15 — slots: the extension surface, owner-shaped

- The term is `slot` everywhere: verb `shadow slots`, env `SHADOW_SLOT_<NAME>`,
  registry `docs/reference/slots.md`, JSON schema `shadow.slots.v1` (was
  `shadow.buckets.v1`, no shim). The `buckets` verb aliases with one stderr
  line and `SHADOW_BUCKET_<NAME>` is read as a deprecated fallback — both die
  next release train.
- The slot set is `{memory, taste}`. `memory` is routed recall: the mounted
  SKILL.md IS the per-person routing file; recall is a lead, never plan,
  proof, or ownership authority. `taste` absorbs the explain remit. The
  superpowers slot is deleted while the pack-leaf delegation guard stays amp
  core, configured by `SHADOW_AMP_PACK_ROOT`; the future slot is deleted and
  its pre-mortem timing is deliberately gone.
- Installers: host-integration documents your-methods-beside-the-block and
  the Cursor manual-paste route.

## 1.0.1 — 2026-08-11 — specific goals start with the right skills

- The one standing Shadow goal remains unchanged and skill-free.
- A specific generated goal now ends with `Skills:` naming the best one to four
  available canonical skills for its actual work. Plugin-qualified names are
  preferred; stale paths, conflicts, unavailable skills, and broad rosters are
  excluded.
- The entity `PLAN.md` still owns the complete tool surface and fallbacks, so
  the launcher stays a bounded pointer rather than becoming a second plan.

## 1.0.0 — 2026-08-11 — durable work from intent to successor

This is the source candidate for Shadow 1.0. It does not by itself claim a
public tag, GitHub Release, Latest promotion, directory listing, or completed
live dogfood receipt.

- One private Git-backed computer board selects projects and records entity
  pointers, priorities, claims, owners, leases, and resume. Each project's
  committed `PLAN.md` remains the sole authority for task detail and proof.
- `shadow status`, `throw`, `amp`, `return`, and `accept` form one bounded loop:
  select work, claim before dispatch, emit an owned execution capsule, prove
  the result in a clean checkout, release ownership, and expose the successor.
- Interrupted chats and independent seats recover through durable local claim
  receipts. Opted-in Git remotes add an append-only coordination lock so a
  protected project does not dispatch the same row on two computers.
- The Git archive, native CLI, Claude and Codex plugin manifests, standing
  goal, and stranger install share one release identity. Public release proof
  remains a separate annotated `shadow-v1.0.0` tag at the exact published
  commit.

## 0.2.0 — 2026-08-10 — one computer board, project plan shards

Shadow now coordinates the whole computer without turning the root into a
second copy of project work. This deliberately changes public verbs, defaults,
and local state; it supersedes the pre-board claim protocol described in older
historical entries below.

- A private Git-backed board at `~/.shadow` owns project priority, entity-plan
  pointers, claims, owners, leases, and one resume checkpoint per entity.
  Committed project `PLAN.md` shards remain the only authority for milestones,
  checkpoint detail, dependencies, and proof.
- Claims are local, offline, atomic, and owner-specific. `shadow throw` claims
  before emitting work; `shadow amp` emits only work already owned by its
  named seat; `shadow return` and `shadow accept --by` close the same claim
  through bounded, crash-recoverable transactions. PLAN `THROWN` lines and a
  remote push are no longer the same-computer mutex.
- `shadow status` and the browser dereference the same canonical board entity
  from any directory. Duplicate worktrees, broken pointers, stale revisions,
  malformed imports, and browser refresh warnings fail loudly instead of
  creating a competing projection. Browser decision receipts hold the board
  revision until the receipt is durable.
- The standing host block now states the plain hierarchy: computer, projects,
  entities, milestones, checkpoints. It requires a stable seat identity,
  focused falsifiers in feature lanes, and the deterministic release train for
  full migration, story E2E, adversarial, rollback, install, and live dogfood
  proof.
- Verification is tiered rather than rerunning every expensive proof on every
  change: mapped focused suites run per change; the full Python matrix runs
  nightly; an optional configured second daily window is explicit; measured
  accepted-trunk-change pressure can start an earlier train. Each train runs
  the isolated story E2E twice and the migration, adversarial, lifecycle,
  rollback, install, and packaging stages with fresh homes. Unknown paths fail
  safe to the full suite.
- Root-board files are private, atomically replaced, locally receipted in Git,
  and recoverable after process death before or after replacement. Canonical
  project lifecycle locks serialize claim, return, and completion without
  holding the computer-wide lock across proof execution or project commits.
- `shadow lifecycle` makes the hot-plan limits executable: lint, import, and
  claim refuse oversized authority; exact-CAS compaction preserves proven
  history and one operation-bound successor. Strict manifests can retire one
  clean landed non-primary worktree or one expired recoverable snapshot without
  force, with crash journals and immutable path-free receipts.

## 0.1.0 — 2026-08-09 — renumbered from 4.1.0

Same code, honest number. Shadow's 4.x line counted releases to a registry
that no longer publishes it: npm was removed on 2026-08-09, so `git clone` is
the only install and there is no downstream `^4` to break. A 4.x version on a
tool this young claimed a maturity and a compatibility history it does not
have. Owner's call, verbatim: *"reset 1.0 ... or .1.0 ... its early"*.

- `VERSION` and `.claude-plugin/plugin.json` are `0.1.0`. Nothing else changed
  — no verb, flag, file format, or default moved with this entry.
- **The method is a separate namespace.** "v4 grammar", "grammar-v2", and "the
  v4 law" name the *plan file format*, not the release. Those words stay
  correct: `## Brief` + `## Tasks` + typed `proof:` tails is still v4 of the
  method while the tool is at 0.1.0.
- The 4.x entries below are retained. They are the build history of this same
  code and the only record of why each verb exists.
- `PLAN.md` shed its v3 `Outcome` block, portfolio readback, and platform
  sections (435 lines) to `docs/plan-archive/2026-08-04-v3-outcome-receipts.md`
  — the last live prose that called the product "Pilot Puppy". Moved, not
  deleted, per archive law.

## 4.1.0 — 2026-08-09 — the goal is a pointer; the board follows you

Built from a real failure: a voice seat opened in a blank workspace and
asked "which project should I attach it to?" — the one question Shadow
exists to make unnecessary.

- `shadow amp` — new verb. Projects one paste-ready goal block from a
  repository's `PLAN.md`: authority ref + section ("the plan wins"), the one
  cycle-law resume row with its proof, the milestone's optional `- tools:`
  line, person-gated rows, open-contradiction count — inside one paste
  budget (default 4,000 chars; optional parts drop from the bottom, the
  pointer and resume never drop). Deterministic: no LLM, no network. Exits 1
  with "mint the successor" on a fully-completed plan — goal chaining
  enforced by the tool. `SKILL.md` § Shape a goal names it as that method's
  executable.
- `shadow status` understands grammar-v2 plans: renders Project / Mode /
  milestone progress / resume / proof through the same parser amp uses (one
  parser, two projections — they cannot disagree; the Milestone line derives
  from the very row amp resumes). Legacy plans keep the previous view.
- Portfolio fallback: `shadow status` in a directory with no plan falls back
  to `SHADOW_PORTFOLIO_ROOT` (default `~/Development`) with a stderr banner,
  so every entry point opens the same durable board. Explicit `--root` and
  `--no-portfolio-fallback` never fall back, and a local plan that fails to
  load blocks the fallback loudly instead of being masked.
- The proxy stance is law (`AGENT.md`): never open empty, never ask "which
  project?", the chief-of-staff moves are Shadow's own unprompted moves,
  chat is projection / plans are memory — and the plan is tied to the
  machine: continuity between machines is git, never a synced chat or an
  impersonated board.
- Out-of-box host integration (`docs/reference/host-integration.md`): the
  static fifteen-line standing goal pasteable into `~/.claude/CLAUDE.md`,
  `~/.codex/AGENTS.md`, and Cursor rules, plus verification steps.
- `docs/reference/honcho.md`: the memory-store question answered once —
  pattern, not store — with a spike path if the ruling should ever change.
- README rewritten around the real product.
- **npm removed.** Shadow installs and runs on Git, Bash, and Python.
  `install.sh` replaces `npm install -g` (the clone is the install; `git pull`
  is the update), `.gitattributes` `export-ignore` replaces npm's `files`
  allowlist, and the release verifier now checks a reproducible `git archive`
  and performs a real stranger-install. A test fails if a package manifest or
  an `npm`/`npx` invocation ever returns.
- **`shadow throw`** — one chat can dispatch dozens of conversations without
  losing them. It refuses unless a ready `[pending]` row with a proof exists,
  claims it, appends a `THROWN` line, commits `PLAN.md` alone, pushes, and
  prints the goal block: launch and flush are one atom. `THROWN` is also the
  dispatched-vs-crashed discriminator — auto-resume skips thrown rows, while a
  hand-claimed `in_progress` row stays a crash-resume target.
- **`shadow status --in-flight`** — every claimed row across the portfolio with
  its proof and throw time: the recovery view after a chat dies mid-fan-out.
- Status never claims a plan is complete while blocking lint findings stand.


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

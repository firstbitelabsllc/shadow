# Shadow — Plan

This file is the sole plan, proof, and resume authority for Shadow (formerly Pilot Puppy; renamed 2026-08-05 — "you are my shadow").

## Brief

- Project: shadow
- Mode: ship
- Priority: land 0.1.0 — one honest version number, and the fan-out law dogfooded

Superseded authority: the v3 `Outcome` block, portfolio readback, and platform
sections that stood here until 2026-08-09 are archived at
`docs/plan-archive/2026-08-04-v3-outcome-receipts.md`.

## Tasks

### M1 — Method encoded
- [completed] AGENT.md encodes the core, gate, and steering ~m3k7 | proof: read AGENT.md carries ## The core, ## Folded behavior, ## The proxy stance
- [completed] method.md contract lands with contract tests ~q8f2 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_grammar_contract | needs: ~m3k7
- [completed] the Method rides the installed mounts ~w5d9 (DoD) | proof: read shadow doctor -> 11/11 with AGENT.md at root | needs: ~q8f2

### M2 — Board live
- [completed] scanner serves gated entity/mode/milestone/checkpoint counts ~t2b8 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_status_focus
- [completed] read-only board view on desktop and phone ~j6n4 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser_shell | needs: ~t2b8
- [completed] full gate matrix green and v3.0.x released ~r9c3 (DoD) | proof: cmd npm run verify | needs: ~j6n4

### M3 — v4 core
- [completed] the Method reduced to eight concepts, lint the enforcer ~h4v1 | proof: cmd npm run test:py | needs: ~r9c3
- [completed] four tagged plans on grammar v2: shadow, moussey #145, snowcubes #2113, resplit #2236 ~g4mv | proof: read shadow lint -> 0 blocking on all four | needs: ~h4v1
- [completed] v4.0.0 released, installed, doctor green ~z7e5 (DoD) | proof: read shadow doctor -> 11/11 on installed v4.0.0 | needs: ~h4v1

### M4 — Amp: the goal is a pointer
- tools: scripts/shadow-python.sh for gates; docs/reference/amp.md is the contract; grammar § Milestone law for the `- tools:` line
- [completed] `shadow amp` projects a bounded pointer-first goal block from PLAN.md ~a4mp | proof: cmd npm run test:py
- [completed] milestone `- tools:` line documented in the grammar and projected by amp ~t0ol | proof: cmd npm run docs:build | needs: ~a4mp
- [completed] `shadow status` v3 outcome-schema path cut or migrated to the v4 Brief ~c9ut | proof: cmd shadow status reports v4 Brief fields, zero "outcome must be a string" on a grammar-clean plan | needs: ~a4mp
- [pending] amp ships in a tagged release, installed mount green ~s4ip (DoD) | proof: gate owner resume: installed `shadow amp` in a v4 repo emits that plan's own goal block | needs: ~t0ol, ~c9ut

### M5 — Shadow is me: continuity + proxy stance
- tools: docs/reference/host-integration.md is the wiring; docs/reference/honcho.md is the memory ruling; scripts/shadow-python.sh for gates
- [completed] status opens the same durable board from ANY directory — portfolio fallback, explicit --root and opt-out flag never fall back ~s4me | proof: cmd npm run test:py
- [completed] the proxy stance is law in AGENT.md: never open empty, never ask which-project, chief-of-staff moves unprompted, static goal, chat-is-projection ~prxy | proof: cmd npm run docs:build | needs: ~s4me
- [completed] the honcho question answered once, durably: pattern not store, function map, spike template to revisit ~hnch | proof: read docs/reference/honcho.md -> ruling + map + revisit path
- [completed] out-of-box host integration: the STATIC standing goal (15 lines) pasteable into CLAUDE.md / AGENTS.md / Cursor rules, plus verify steps ~oobx | proof: read docs/reference/host-integration.md -> static goal block + `cd $(mktemp -d) && shadow status` check
- [completed] README rewritten to the real product: proxy identity, continuity, amp, the refusals ~rdme | proof: cmd npm run verify
- [pending] a real remote/voice seat cold-starts correctly on the installed release: it opens ITS machine's board or says "no plans on this machine — plans live in their git remotes"; never a which-project question, never another machine's board impersonated; findings written to a plan before session end ~vcar (DoD) | proof: gate leo resume: repeat the 2026-08-08 car session against the next tagged release | needs: ~s4me, ~oobx

### M6 — npm removed: Git, Bash, Python
- tools: install.sh is the only install path; scripts/shadow-release-package.py verifies a `git archive` artifact; .gitattributes export-ignore is the allowlist
- [completed] the four JS source-contract tests ported to Python without loss ~jsp0 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser_shell
- [completed] npm deleted from the product: manifest, lockfile, vitest, playwright, vitepress, and every npm invocation in bin/scripts/CI ~npm0 | proof: cmd scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py' | needs: ~jsp0
- [completed] install.sh replaces `npm install -g` and is proven by a stranger-install in the release verifier and in CI ~inst | proof: cmd scripts/shadow-python.sh scripts/shadow-release-package.py --allow-dirty | needs: ~npm0
- [pending] v4.1.0 cut from a clean tree and installed on both machines from the clone ~rel1 (DoD) | proof: gate leo resume: git pull on each machine, bash install.sh, shadow doctor green, then the car test | needs: ~inst

### M7 — one chat, dozens of conversations
- tools: scripts/shadow-throw.py is the dispatch record; `shadow status --in-flight` is the recovery view; design corpus = the 2026-08-08/09 session's five real cases
- [completed] `shadow throw` claims a row before any conversation leaves the chat — refuses proofless, needs-blocked, already-thrown, and mid-merge rows ~thrw | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw
- [completed] auto-resume skips THROWN rows; hand-claimed in_progress rows stay selectable ~dsc0 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw | needs: ~thrw
- [completed] `shadow status --in-flight` renders every claimed row across the portfolio with its proof and throw time ~mstr | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw | needs: ~thrw
- [completed] dispatch law lands in AGENT.md + grammar.md: row-first dispatch, THROWN discriminator, write-at-discovery, the death sequence ~dlaw | proof: cmd scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md | needs: ~mstr
- [pending] one real multi-conversation cycle driven through throw end to end, with a deliberate chat kill mid-flight ~live (DoD) | proof: gate leo resume: throw 3+ rows, kill the chat, then recover the fleet from `shadow status --in-flight` alone | needs: ~dlaw

### M8 — 0.1.0: one honest number, and the fan-out law dogfooded
- tools: `scripts/shadow-release-package.py --expect-version` is the artifact gate; the audit runs as three NAMED agents (inspectable, messageable), never a sealed workflow; doctor's native-host floor and standing-goal checks read the machine running it, not the clone, so ~land asserts the install-scoped checks by name instead of doctor's exit code
- [completed] the v3 Outcome blob leaves PLAN.md; no live prose calls the product Pilot Puppy ~dslp | proof: read docs/plan-archive/2026-08-04-v3-outcome-receipts.md holds 839 lines incl. 54 mentions; every mention left in PLAN.md is a dated receipt or the rename note -- zero live law prose
- [completed] VERSION and plugin.json read 0.1.0 and the release artifact verifies at that version ~vrst | proof: cmd scripts/shadow-python.sh scripts/shadow-release-package.py --expect-version 0.1.0 --allow-dirty
- [completed] repo audited for 0.1.0 readiness; every must-fix either fixed or written as a row ~audt | proof: read 11 must-fix findings from the 5-agent audit: 9 fixed in b76dfa3, 1 held as a Contradiction, 1 as a Deferred row
- [completed] the fan-out law is stated where dispatch is decided: an unattended fan-out leaves a thrown row first, whichever mechanism spawns it ~fout | proof: read AGENT.md Row-first dispatch carries mechanism-neutrality, supervisable-by-default, and the mid-flight clause; grammar.md Dispatch law names a self-launched batch
- [completed] 0.1.0 merged to main, installed from the clone, and every doctor check the clone itself controls green at that version ~land (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; bash "$d/s/install.sh" --bin-dir "$d/bin" --no-skills >/dev/null; test "$("$d/bin/shadow" --version)" = 0.1.0; if HOME="$d/home" "$d/bin/shadow" doctor > "$d/out"; then :; fi; grep -q "^\[PASS\] python:" "$d/out"; grep -q "^\[PASS\] git:" "$d/out"; grep -qx "\[PASS\] product identity: shadow 0.1.0" "$d/out"' | needs: ~vrst

### M9 — Shadow installs itself: host directives, extension buckets, one canonical plan home
- tools: superpowers is the reference implementation for host-directive injection; `shadow doctor` is where every claim in this milestone gets a check; research runs as NAMED agents on disjoint surfaces
- [in_progress] the five open design questions are answered from evidence, not preference: how a tool safely owns a block in someone's CLAUDE.md, what Cursor's real user-rule surface is, where plans actually live on this machine, how an optional method pack is declared a dependency, and what Langfuse puts on the wire ~rsch | proof: read five agent reports folded into M9 as decisions, each citing file:line or a live observation
- [pending] `shadow install --hosts` writes a MANAGED block into ~/.claude/CLAUDE.md, ~/.codex/AGENTS.md, and the real Cursor surface -- idempotent, marker-delimited, refreshable, removable, never clobbering a person's own text ~host | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives
- [pending] extension buckets: Shadow declares named slots where a method pack plugs in (superpowers, honcho, taste), install defaults them, and doctor reports each as present/absent/stale ~bkts | proof: cmd scripts/shadow-python.sh -m unittest tests.test_extension_buckets | needs: ~host
- [pending] the canonical home for plans is decided from what is actually on this machine and written into grammar.md; the portfolio fallback either implements that rule or is corrected ~home | proof: read grammar.md names the rule; `shadow status` from three unrelated directories returns the same board
- [pending] one deterministic setup verifier per host proves the wiring end to end -- not that files exist, but that a cold Claude/Codex/Cursor session resolves the skill, reads the directive, and reaches the board ~detv | proof: cmd bash -c 'scripts/shadow-verify-host.sh --host claude-code && scripts/shadow-verify-host.sh --host codex' | needs: ~host
- [pending] observability verdict: adopt, augment, or kill Langfuse for end-to-end triage, decided against Shadow's no-daemon/no-transcript boundary, with the bounded design if adopted ~obsv | proof: read a written verdict citing what Langfuse requires on the wire and which Boundaries clause it touches
- [pending] a stranger runs one command and ends with all three hosts wired, doctor green, and the board reachable from any directory ~w1re (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; HOME="$d/home" bash "$d/s/install.sh" --bin-dir "$d/bin"; HOME="$d/home" "$d/bin/shadow" doctor; rm -rf "$d"' | needs: ~bkts

## Worklane boundary

- Shadow has its own product plan and proof gap. That gap never blocks an
  unrelated product from shipping the highest-value reachable row in *its* own
  canonical plan.
- “One bounded task” means one reviewable handoff with an exact scope. It does
  not mean only one project may move, nor that the Outcome has only one
  deliverable. It is an execution-granularity and safety rule: after one packet
  is proven, resume the next highest-value reachable lane in this same plan.
  A safe, obvious in-scope improvement must not wait for an unrelated host,
  quota, or portability check.
- Use Shadow where its briefing, bounded execution, or resume record helps.
  Otherwise work directly in the product lane and prove the real user-visible
  outcome there. Amp only sharpens that lane's brief; it does not dispatch,
  validate, or become its authority.
- The current portfolio lanes are Star67 (formerly Pivot SQL), Moussey consignment,
  Moussey cleaner/host safety, Snowcubes consignment/storefront, StrongYes
  Code Reps/Game Plan, Resplit 2.0 launch readiness, and security/privacy plus
  release handoff. Each lane keeps its own canonical plan and owner/worktree
  boundary. Nicole's shipped SQL trainer and StrongYes archived/paused queues
  are mapped but do not create new work.

## Portfolio map

- **Star67:** public authority is `nlau1193/pivot-sql` at
  `main@bc9808dc`, with the browser-first/browser-only README linking directly
  to `https://learn-sql-peach.vercel.app/`. The live front door is HTTP 200 with
  Star67 content. The public repository is pushable but not admin-accessible
  from this account, so the requested `star67-learn-sql` rename and homepage
  writes remain owner-admin work.
- **StrongYes:** the live authority is the current Code Reps/Game Plan
  `vidux/launch-validation/PLAN.md`, not the dirty voice-debug checkout or its
  archived queues. Public `main@e4b53680` contains merged PR #1475's dependency
  repair; the production-only npm audit is 0 vulnerabilities and the isolated
  source proof is green. Deployment, live Grafana correlation, ACL, and
  credential predicates remain separate owner work.
- **Resplit 2.0:** the canonical authorities are
  `resplit-web/vidux/resplit-2.0-launch/PLAN.md` and `INBOX.md`, with the iOS
  plan's release evidence kept separate. The launch plan still carries
  unresolved iOS/TestFlight/Sentry/on-device and web-chaos gates; the primary
  iOS and web checkouts are dirty and owner-bound. Do not revive historical
  worktree queues or start a build, upload, merge, or device mutation from this
  umbrella lane.
- **Snowcubes/Moussey consignment:** current Snowcubes public `main@12b01ba`
  contains the 2026-05-21 Marathon row as FREE/UNKNOWN, `$0.00` open, with no
  charge or payment row; old `$225.63`, `$342.04`, and `$57.75` amounts remain
  historical and must not be treated as receivables. Current Moussey public
  `main@c74c8c67` is separate from cleaner `f355f2e7`, where PRs #129–#133
  carry the consignment first-frame, dependency, passcode-doc, smoke, and
  proof receipts. The protected `:4321` process belongs to a dirty primary
  checkout and still renders the older tracker/audit surface; no restart or
  credential retrieval was attempted. The cleaner branch is not a second
  wholesale merge target because it contains unrelated voice/cleaner work.
- **Snowcubes storefront:** `https://trysnowcubes.com/` returned HTTP 200; the
  public page did not expose the retired receivable figures or consignment-only
  billing/source language.
- **Moussey cleaner:** the canonical photo-cleaner plan still has active
  MPCLEAN-254 host-survival work and MPCLEAN-253 real-media inspection work,
  under an existing Claude Code single-writer lease. The fresh read-only host
  sample at `2026-08-03T18:44:20Z` reports about 50,285 of 51,200 MiB swap
  used, only about 915 MiB swap free, and about 15 GiB root free. The approved
  disk-clean
  dry run found only 51 MiB of DerivedData and no meaningful safe reclaim. The
  cleaner build/browser/media ladder is therefore paused; no process, cache,
  source, or personal-media mutation was attempted.
- **Security:** Snowcubes PR #1567 merged at `7fd0a06` is included in the
  current public lineage ending at `main@f13e6db`. The package-lock production
  audit reports 0 vulnerabilities, and the current source gitleaks/audit
  boundary remains clean. The latest tracked agent-discovery readback reports
  the public UCP endpoint healthy and catalog-only, while public capability
  docs and `/.well-known/ucp` still advertise unsupported
  cart/checkout/payment/order/fulfillment capabilities and a mismatched
  endpoint. This remains an existing Shopify/Worker owner-deploy predicate,
  not a storefront workaround.
- **Codex Security:** the official plugin workspace is open against the clean
  Moussey integrated-proof target; setup is valid but `setup.submitted=false`,
  so the app is still waiting for the user to press Start scan. The required
  wait was left without a scan ID or report; no plugin findings or remediation
  are claimed. The earlier official
  `@openai/codex-security@0.1.5` input-only dry-runs and canceled Pilot Puppy
  attempt remain historical receipts; CodeQL, gitleaks, npm audit, and focused
  source-security receipts remain the authoritative completed checks.
- **Host credential privacy:** a names-only local process audit observed
  credential-bearing arguments in existing MCP launchers. Secret values are
  intentionally not recorded. No process was restarted or killed; the exact
  remaining predicate is owner-approved credential rotation followed by safe
  relaunch through an environment/keyring channel that does not expose values
  in process arguments.
- **External gates:** GitHub repository name/homepage/topic settings, other-computer access, and native Codex
  quota remain explicit deferred predicates, not global blockers.

## Privacy and safety

- Local by default; loopback browser only.
- Evidence is project-bounded, retention-bounded, and free of credentials,
  prompts, transcripts, provider payloads, and absolute private paths.
- Credential-bearing process arguments are a host privacy defect, not evidence;
  never copy them into receipts or plans. Rotation/relaunch remains an
  owner-controlled security action.
- Writes are atomic and idempotent. Host work is limited to an exact worktree
  and explicit allowed paths. Scope escape fails closed.
- Git history is preserved with ordinary forward commits.

## Work

- [completed] Establish the canonical package, command, skill, configuration,
  schemas, browser identity, and local state contract.
- [completed] Fold in the smallest proven native-host driver for Codex, Claude
  Code, and Cursor, with a sealed task and validated bounded receipt.
- [completed] Prove restart/resume, chief-of-staff status, A/B/C choice, privacy,
  packaging, installation, documentation, and full test behavior.
- [completed] Replace shared, private, and installed callers, then remove every
  predecessor command, skill, mount, hook, job, configuration, and active file.
- [completed] Rename the existing GitHub repository in place, merge, release,
  fresh-install, and read back the remote, mounts, command, and real UI.
- [completed] Run the final cold review and zero-surface audit; close only when
  all changed repositories are clean, pushed, and remotely verified.
- [completed] Publish the portable other-computer handoff with bootstrap,
  mounting, proof, privacy, and one exact resume predicate.
- [completed] Keep the local Outcome and A/B/C brief actionable when an
  external host is unavailable; take reachable product work without waiting.
- [completed] Resolve a Python 3.10+ interpreter from PATH or an explicit
  override so local commands and the browser do not fail on a pinned bare
  `python3`.
- [completed] Honor the documented local development-root and browser host/
  port environment defaults while preserving command-line precedence.
- [in_progress] Coordinate the full product portfolio from this plan: resume
  each lane from its own authority, keep source/merged/deployed/live/proven
  states distinct, and close reachable Star67, Moussey, Snowcubes, security,
  and handoff work without creating a second operating layer.
- [completed] R1: Add a provider-neutral, local roster contract and safe
  foreground display for explicit `lead`, `planner`, `dev`, `debug`, `review`,
  and `hard-dev` roles. It must be local configuration only, no-overwrite,
  bounded, and private-text safe. Local roster output may show safe role labels
  and availability; concrete model, account, quota, command, and machine data
  must stay out of browser/status/evidence output.
- [completed] R2: Add a foreground smart role router that deterministically
  selects a role and native-host surface from an explicit task class, prints
  its reason, alternative, and escalation, and never launches work. Preserve
  existing `host run --host` compatibility and bind a later packet to the
  route-safe roster revision/hash.
- [completed] R3: Bind a ready explicit route to the existing one-task native
  host handoff. Reject unsafe, stale, forged, task-mismatched, host-mismatched,
  or self-overwriting route packets before a host starts. Keep one explicit
  packet at a time; do not add a fan-out manager, queue, daemon, or retries.
- [completed] R4: Keep rerouting and independent review at an evidence
  boundary. A `review` route remains a manual review decision; the lead starts
  any new route explicitly and retains final proof/acceptance.
- [completed] R5: Add a local private seat overlay because a real native-tool
  setup needs more than the generic role/host roster. It may select only a
  validated model flag for a ready, route-bound native host; it must stay
  owner-local, with its configuration absent from browser/status, plans, route
  evidence, attempt receipts, packages, and stranger installs. It may never hold credentials,
  prompts, provider payloads, profile guesses, or arbitrary command arguments.
- [completed] R6: Prove the default `planner`, `dev`, `debug`, and `hard-dev`
  route shapes without launch, and publish their honest calibration boundary.
  A native-host calibration is valid only for the same role and frozen task in
  separate clean worktrees. Report route, scope, proof, lead reproduction, and
  elapsed time or an honest null; never claim model quality, provider usage,
  tokens, cost, quota, or performance by assertion.
- [completed] R7: Complete OSS hardening: threat boundary, license/provenance,
  fresh install, docs, loopback UI readback, package, privacy, and security
  gates.
- [completed] R8: Make local role routing usable without source spelunking:
  render the four work shapes in the loopback briefing and add one atomic local
  `roster prefer` command that reprioritizes only declared, enabled generic
  role/host slots. It must not read providers/models/quotas, launch work, or
  create project evidence.
- [completed] R9: Align the public roster and route vocabulary with the six
  user-facing work roles `planner`, `dev`, `debug`, `review`, `hard-dev`,
  and `lead`. Existing local `bulk`, `critic`, and `hard-ic` labels remain
  readable as compatibility aliases, but normalized roster views, route packets,
  docs, and the loopback guide emit only the current names.
- [completed] R10: Build foreground Supervised Drive for one project: read
  its current `PLAN.md`, prepare up to three path-disjoint sealed lanes, and
  wait for one explicit local launch before reusing native host runs, local
  proof, and one explicit lead-reproduced local merge. Add optional, off-by-default,
  metadata-only Langfuse observation after local truth exists; it may never
  receive task, plan, code, prompt, path, provider, or credential data, and it
  may never route, launch, retry, accept, or alter a local result.
- [completed] R11: Close the real-dogfood gaps in Supervised Drive found by
  the first end-to-end run and an adversarially verified 21-agent review of
  v2.2.0. Ignored build artifacts and product-owned `.pilot-puppy/` state no
  longer block or strand green work; the loopback page can no longer receive
  private paths or secret-shaped text; declared `merge:"manual"` lanes stay on
  their kept branches; every needs_attention lane names its reason; commit
  identity is refused before any host starts; browser and CLI time budgets
  nest; interrupted sessions relaunch without re-spending finished lanes; and
  concurrent launch/accept of one session is refused by a local lock.
- [pending] Successor: run one real multi-lane Drive Packet on a customer
  repository end to end on the installed v2.2.1 CLI — two or three
  path-disjoint lanes on distinct declared hosts, driven prepare → launch →
  accept with kept-branch review, receipts folded back here. Exact resume
  move: pick the highest-value reachable repo from its own canonical plan,
  run one real delegated row through a fresh worktree + `shadow host run` +
  `shadow accept --row` on a customer repository.
- [deferred] Close cross-host portability proof through the other-computer
  route or the local quota-reset fallback; require the same sealed task, exact
  allowed-path change, and lead-reproduced check.

## Mechanical proof required

- Full tests, docs, package, privacy, security, fresh clone, and install pass.
- `shadow doctor` passes; removed commands fail lookup.
- Codex, Claude Code, and Cursor each complete one sealed task with
  lead-reproduced proof.
- One real Outcome survives restart and renders an accurate brief and A/B/C
  choice.
- Active repositories and installed roots contain no predecessor product
  names, duplicate state, credentials, raw transcripts, or absolute private
  paths.
- The renamed public remote, release artifact, installed skill, command, and UI
  all read back as Pilot Puppy.
- Star67 proof includes the public launch URL, source branding, focused
  contracts, typecheck, dependency audit, secret-scan disposition, and
  current-main preview-browser proof.
- Moussey/Snowcubes proof includes source-authority audit, focused money/UI
  tests, production build, credential-URL checks, and real public readback;
  primary dirty/owned checkouts are never restarted or overwritten by proof.

## Progress

- 2026-08-09T03:30:00Z ~dlaw PROOF plan lint 0 blocking with the dispatch law in AGENT.md (row-first dispatch, THROWN discriminator, write-at-discovery, post-death sequence) and grammar.md (THROWN vocabulary + Dispatch law section); the concurrency line was corrected in place — concurrent APPENDERS serialized by fast-forward are legal, concurrent FLIPPERS are not
- 2026-08-09T03:30:00Z ~mstr PROOF tests.test_throw InFlightView -> --in-flight lists every claimed row portfolio-wide with project, milestone, proof, throw time, and dispatched-vs-hand-claimed; empty portfolio says so. This is the master multi-head view Leo asked for as a "trie" — its heads are plans, its data is rows that already exist
- 2026-08-09T03:30:00Z ~dsc0 PROOF tests.test_throw ThrownExcludedFromAutoResume -> a thrown row is never auto-selected (explicit --task still reaches it) while a hand-claimed in_progress row without a THROWN line stays selectable; without this split a fresh seat re-runs work another conversation is running
- 2026-08-09T03:30:00Z ~thrw PROOF tests.test_throw -> 11 tests; refuses unknown/needs-blocked/proofless/already-thrown/bad-id, claims + appends THROWN + commits PLAN.md ALONE + prints the goal block, working tree clean after. 212 tests green overall
- 2026-08-09T03:25:00Z STRUCT M7 added | trigger: owner 2026-08-09 verbatim: "in one chat, a conversation needs to be able to throw dozens of conversations, and know when to break out a milestone create an entity whatever and durably track it WHILE the ongoing work is going for the other chats". Designed by a 10-agent arena (3 opposed designs, 6 thermo challenges, 1 synthesis) against a corpus of five REAL cases from this session, including the plan-mediated relay that shipped PR #2251 and the evaporated car-session packet. Why now: the pattern worked all day on hand-discipline alone and had exactly one unrecoverable hole — a chat dying mid-fanout. Contradicts: nothing; throw writes only into PLAN.md, --in-flight is pure projection, no daemon/queue/registry. REJECTED with reasons in the design record: a flush verb, a `- thrown:` row field, `amp --throw`, a milestone-mint verb, a THROWN-DANGLE lint, and any session registry. KNOWN RISK: cross-machine same-row double-throw merges silently (bounded to duplicate work — accept refuses the second finisher); wake = the first verified incident, which then wakes seat-token hardening.
- 2026-08-09T02:40:00Z ~inst PROOF release verifier on the git artifact -> OK (4.0.3, 80 files, sha256 7fe6ff81...); its stranger-install now extracts the archive and runs install.sh for real, a STRONGER check than the npm-pack/npm-install path it replaced
- 2026-08-09T02:40:00Z ~npm0 PROOF full python suite -> 201 tests OK with zero node present; migrated five npm-coupled surfaces (doctor identity, public-ready metadata gate, release verifier, release tests, python-resolution test) to plugin.json+VERSION+git-origin; CI rewritten to two node-free jobs
- 2026-08-09T02:40:00Z ~jsp0 PROOF tests/test_browser_shell.py -> the four browser/tests/unit assertions ported verbatim (they only ever read three static files and asserted substrings; vitest+happy-dom+vue+vitepress existed to run four greps), PLUS a NoNodeDependency test that fails if a package manifest returns or npm/npx appears in bin|scripts|.github — the ruling enforces itself
- 2026-08-09T02:40:00Z STRUCT M6 added | trigger: owner ruling 2026-08-09 verbatim "delete npm simplify it we dont need npm that is final answer... no more no npm ever again" and "after this i dont want to hear npm blocking us ever again". Why now: npm auth (E401) was the ONLY thing blocking the v4.1.0 release; deleting the dependency deletes the blocker instead of waiting on a login. Contradicts: nothing in the law — Boundaries never required a package manager; the deleted playwright e2e is the one real coverage loss, accepted because browser/server.py already carries 28 python tests and the board was ruled non-essential 2026-08-07 ("no standing board").
- 2026-08-09T01:05:00Z STRUCT ~vcar pass-condition tightened + machine boundary written into AGENT.md and host-integration.md | trigger: owner ruling 2026-08-09 verbatim "the plan should be tied to the machine" — the car seat ran on a REMOTE machine, so the correct behavior there was never to show THIS machine's board; it was to open its own (empty) board and say where the plans live. Continuity between machines is git, not a synced surface.
- 2026-08-08T23:30:00Z ~rdme PROOF npm run verify -> 171 py + 4 js + docs build + public-ready gate all green with the rewritten README in place
- 2026-08-08T23:30:00Z ~oobx PROOF read host-integration.md -> static goal block present; mktemp-d verify step documented; voice/remote rule: out-of-band findings are written to the owning PLAN.md before session end
- 2026-08-08T23:30:00Z ~hnch PROOF read honcho.md -> ruling (pattern not store, v4), four-row function map, spike-to-revisit path; the recurring question now has a link-instead-of-rederive answer
- 2026-08-08T23:30:00Z ~prxy PROOF npm run docs:build -> clean with the proxy-stance section in AGENT.md
- 2026-08-08T23:30:00Z ~s4me PROOF npm run test:py -> 171 OK incl 3 new portfolio-fallback pins (blank-cwd falls back + banner on stderr; explicit --root never falls back; --no-portfolio-fallback keeps empty empty)
- 2026-08-08T23:25:00Z STRUCT M5 added | trigger: owner car-session 2026-08-08 (Codex voice, remote machine) — four verbatim gaps: (1) "why does every shadow not open the same durable plan list?" — reproduced live: blank voice workspace answered "which project should I attach it to?" because status scanned cwd only; (2) "why haven't we installed hauncho" — the v4 ruling existed but had no durable, linkable answer, so it kept re-costing; (3) "the readme is just a rip of what vidux used to be" — README described a passive per-repo tool: no continuity story, no amp, no proxy stance; (4) "shadow is supposed to be me... the /goal should always be the same, a static pointer" — nothing shipped that static goal or the out-of-box host wiring. Also: this is Deferred ~ob1c's wake firing for real (cold-start cost named as friction by the person, in production). Evidence caveat: the "Fable-ready packet" the voice seat claimed to assemble lives on the remote machine and is unverifiable here — the pasted transcript is the durable capture, which is itself gap-(4)'s lesson: chat is projection, plans are memory. Contradicts: nothing — extends M4's pointer doctrine from the goal block to the whole product surface.
- 2026-08-08T20:30:00Z ~c9ut PROOF shadow status on this repo -> renders the v4 Brief (project shadow, Mode ship, milestone M4 2/4, resume ~c9ut itself — the output was its own proof), zero "outcome must be a string"; v4 plans route through the amp parser so status and amp can never disagree, legacy v3 plans keep the old view; 168 py tests OK incl 3 new status pins (schema-error regression, cwd-independence, JSON shape)
- 2026-08-07T22:55:00Z ~t0ol PROOF npm run docs:build -> "build complete in 1.78s", amp.md + grammar § Milestone law tools line rendered (run fresh in this checkout before the flip)
- 2026-08-07T22:55:00Z ~a4mp PROOF npm run test:py -> 12/12 test_amp + full py suite + lint:plan 0 blocking, all in the same commit as this flip; dogfood: `bin/shadow amp` on this plan exited 1 "no open task — mint the successor" BEFORE M4 existed (goal-chaining enforced by the tool itself) and emits M4's goal block after
- 2026-08-07T22:55:00Z STRUCT M4 added | trigger: owner directive 2026-08-07 (verbatim: "a goal prompt MUST MUST MUST be a pointer to the durable plan data source") — amp is Shadow P0; M3 closed 04:55Z handing the chain to product goals with no Shadow successor row, so this is also that missing successor. Why now: the 4k goal ceiling is hit by every real multi-project goal tonight. Contradicts: nothing — the per-milestone tooling line is pattern-not-store, consistent with the honcho ruling; `shadow status`'s v3 outcome schema DOES contradict the v4 grammar (250/250 plans report "needs a valid Brief") and is named as cut row ~c9ut rather than diluting the grammar.
- 2026-08-07T13:30:00Z ~fa17 PROOF 17-agent full-coverage audit (thermo+ponytail, 100% of product files) -> 9 confirmed blocks (0 refuted), all fixed + regression-tested in v4.0.2; 29 follow-ups parked (read)
- 2026-08-07T12:30:00Z STRUCT operator ruling (Leo, in chat): Shadow is a method per orchestrator, not a durable singular service — it spins up with the caller's session (codex or claude), and the ongoing chat is the on-the-go surface; no standing board. Same-day revert of my over-build: shadow-browse LaunchAgent removed, tailscale :8443 serve off, tailnet config back to pre-existing paths only. `browse --allow-host` STAYS in the repo as a generic opt-in proxy knob (not tailscale-specific; one-line veto: say revert and 4.0.2 removes it). Personal deploy choices live outside the OSS repo (operator CLAUDE.md/memory), so no /shadow-leo skill is minted for a recipe nobody runs. | trigger: 'there is no need for me to see the board on the go'
- 2026-08-07T12:05:00Z ~gate PROOF Leo confirmed in chat ('delete all the old ones, we don't need to port over anything') -> deleted ~/Development/vidux (68M) + vidux-friendly-artifact-20260804 + vidux-snowcubes-current-20260804 + the .disabled vidux-browser plist; pre-deletion inventory: 0 dirty files, 0 unpushed commits in all three; the vidux remote redirects to firstbitelabsllc/shadow so all history survives there; board healthy post-delete (read)
- 2026-08-07T11:40:00Z AUDIT seat=chief 7-verifier subsumption sweep (goal: shadow = vidux/pilot-puppy/swarm/sidekick/pilot-leo/ninety all-in-one + car mode): swarm/sidekick/ninety never existed here (sweep receipts in session); pilot-puppy retired on disk, 2 orphan ghost servers running deleted code killed (PIDs 49826/65757, ports 7191/7199 freed); vidux job subsumed but LaunchAgent was LIVE on 0.0.0.0:7191 feeding tailnet path /flavors — retired only AFTER the successor went live; pilot-leo skill source still being written in 2 stale ai-leo checkouts (untouched, see Deferred)
- 2026-08-07T11:40:00Z PROOF car mode -> https://leos-mac-studio-10442.tail4cfd4f.ts.net:8443 serves the board through the tailnet: /api/health 200 v4.0.1; LaunchAgent com.leokwan.shadow-browse (loopback bind :7195 + --allow-host) + tailscale serve --https=8443; vidux-browser booted out (plist kept as .disabled-20260807, revert = mv back + bootstrap), /flavors path removed (read)
- 2026-08-07T04:55:00Z SHIP report — mega goal (Shadow v4) closes agent-side: M3 DoD ~z7e5 proven (doctor 11/11 on installed 4.0.0); step 4 proven (~g4mv, four plans lint-clean); the 19-agent challenge fixed 12 confirmed defects pre-tag; standard vocabulary shipped per operator ruling. LESSON folded: invented vocabulary is product surface an operator must veto — standard words survive; the highest-yield adversarial target is the enforcers themselves. SUCCESSOR: the chain hands to product goals — first: trysnowcubes-web's open storefront milestone runs start-to-ship on Shadow as substrate; ASC resubmission stays gate leo. In-flight background: vocab-resweep workflow over moussey #145 / snowcubes #2113 / resplit #2236 (complete when all three report pushed + worktrees pruned). Deferred ~ob1c (one-chat brief surface) wake HAS fired; it re-parks with wake: the first product cycle names cold-start cost as friction — product goals own the chain first.
- 2026-08-07T04:35:00Z ~z7e5 PROOF shadow doctor on installed v4.0.0 -> 11/11, 0 warnings; tarball sha256 9b617fe0..3d53f matches the release; version 4.0.0 (read, re-observed post-install)
- 2026-08-07T04:35:00Z ~z7e5 DoD flips: M3 complete — the mega goal's Shadow-side work is done; the chain hands to product goals per the completion condition
- 2026-08-07T04:05:00Z ~g4mv PROOF shadow-lint over the four migrated plans -> 0 blocking (moussey fdb2f223 on #145; snowcubes draft #2113 + graphite; resplit 897801527 on #2236; worktrees torn down) (read)
- 2026-08-07T03:40:00Z NOTE seat=chief concept-drift audit vs the founding manifesto: core followed (method-over-harness, planning-is-writing, gate pair, checkpoints, A/B/C, auth-out); deliberate drifts confirmed (4 modes -> 2 postures with Spike/Defer/Challenge as moves; ledger deleted for git+board; adversarialism is process not machinery); named gap: the one-identity chat is behavior, not substrate -> Deferred row ~ob1c
- 2026-08-06T17:05:00Z BOX ~v4ch is the v4 core survivable under a 7-lens adversarial challenge (correctness/simplify/deletion/coverage/interop) | ends: 2026-08-06
- 2026-08-06T23:30:00Z VERDICT ~v4ch keep -> 12 confirmed defects (0 refuted of 12) fixed in 6 commits: enforcer false-green paths closed, checkpoint second-flip-path deleted, drive lib deleted, no-op scrub deleted, SKILL/docs stopped teaching dead commands, board crash fixed; 27 worthwhile triaged (cheap ones done, rest Deferred)
- 2026-08-06T16:35:00Z PARK seat=chief — v4 (PR #254) is green locally
  (Python 131, JS 4, Playwright 10, docs, privacy, 4.0.0 package) and pushed,
  but merge is blocked by a GitHub Actions outage: every job fails at "Set up
  job" with "Failed to resolve action download info: Service Unavailable" —
  GitHub cannot fetch actions/checkout etc. Not our code; two re-triggers hit
  the same infra failure. Not retry-looping. RESUME: when Actions recovers,
  `gh run rerun` the failed workflows (or push an empty commit), and on green
  merge #254, cut v4.0.0, reinstall on the operator machine (flips DOD d2
  ~z7e5 Unknown->Verified), tear down the worktree.


- 2026-08-06T15:30:00Z ~h4v1 PROOF npm run test:py -> 124 pass, lint 0 blocking (accept)
- 2026-08-06T15:30:00Z POSTURE Broad->Close | harness: the v4.0.0 full gate matrix

### Close

- DOD d1 Method reduced to eight concepts, lint-enforced | C: ~h4v1 | proof: cmd npm run test:py -> pass, shadow lint 0 blocking | status: Verified
- DOD d2 v4.0.0 released, installed, doctor green | C: ~z7e5 | proof: read shadow doctor -> pending reinstall on the operator machine | status: Unknown
- LESSON folded into AGENT.md v2 + docs/reference/method.md: a method that needs a glossary fails its own readability test; every concept must pay rent (name a failure it prevents) or fold. Preemptive machinery (the beads-derived concurrency tokens) was deferred until a real collision occurs.

- 2026-08-06T06:25:00Z POSTURE note seat=chief — Method v2 simplification
  debate ran three adversarial rounds (10 seats + 5 judges + chief + 1 of 4
  cross-examiners); verdict: ~28 concepts -> 8 core. Spec + debate records
  committed under docs/superpowers/specs/. ACCESS-ALERT: subagent session
  limit hit 02:10 ET mid-Round-3; green work pushed per protocol. Resume:
  re-run workflow wf_1cbfdc76-3f3 from cache after 04:10 ET, fold three
  outstanding cross-exams (drive fold, langfuse deletion, posture collapse)
  into the spec, then operator review gates any implementation. The spec
  changes no shipped behavior.

- 2026-08-06T04:05:00Z CONTRADICTION recorded: C3~w5d9 was flipped completed
  on a proof (doctor) that verified mounts but not content — AGENT.md was
  never in the npm files list, so v3.0.0 installs carried no standing-behavior
  file. Found by the Round 1 stress adversary. Row demoted to in_progress;
  v3.0.1 ships the file, doctor now requires it, and a contract test pins the
  files entry. Re-flip only after reinstall + doctor on the operator machine.

- 2026-08-05T23:05:00Z M1 REPORTION seat=chief — tagged C3~w5d9 as M1's (DoD)
  row; M1 shipped without one, which its own PLAN-LINT (pass E, milestone
  shape) flags. Trigger: first lint of this plan under the released grammar.
- 2026-08-05T23:05:00Z ~w5d9 PROOF seat=chief out=`pilot-puppy doctor` -> 11/11
  on installed v2.3.2 (mounts resolve to the release package).
- 2026-08-05T23:05:00Z ~w5d9 DONE seat=chief
- 2026-08-05T23:05:00Z ~r9c3 PROOF seat=chief out=PRs #247/#248/#249 squash-merged
  with hosted checks 11 pass / 1 skip each; releases v2.3.0
  (`6a25eb51…45e2bc`), v2.3.1 (`893e75fe…c0ffd2`), v2.3.2 (`fdc0876d…32be92`)
  public; full local matrix Python 180/180, Playwright 10/10, vitest 4/4,
  docs, privacy 0 findings.
- 2026-08-05T23:05:00Z ~r9c3 DONE seat=chief
- 2026-08-05T23:05:00Z ~h4v1 PROOF seat=chief out=/api/plans readback shows four
  entity lanes (pilot-puppy, moussey, resplit, snowcubes) each with mode,
  milestone, checkpoint counts; desktop+phone board screenshots reviewed by
  eye (which caught and fixed the shell-hide defect in v2.3.2). Tagging PRs:
  moussey #145, trysnowcubes-web #2057 (first root PLAN.md), resplit-ios
  #2236 (additive; authority remains vidux/north-star).
- 2026-08-05T23:05:00Z ~h4v1 DONE seat=chief
- 2026-08-05T23:05:00Z ~z7e5 PROOF seat=chief out=this commit's own diff: mode
  Close declared in the Operator Brief, checkpoint rows flipped only with
  these paired PROOF lines, one re-portioning line with its trigger, and the
  Close matrix below — the cycle ran by the released grammar it shipped.
- 2026-08-05T23:05:00Z ~z7e5 DONE seat=chief

### Close

- DOD d1 The Method encoded and installable | C: ~m3k7,~q8f2,~w5d9 | proof: `python3 -m unittest tests.test_method_contract` -> 4/4 + doctor 11/11 on v2.3.2 | status: Verified
- DOD d2 Board live, read-only, both viewports | C: ~t2b8,~j6n4 | proof: `npm run test:e2e` -> 10/10 incl. zero-write and shell-hidden assertions | status: Verified
- DOD d3 Real plans render as entity lanes | C: ~h4v1 | proof: /api/plans readback + reviewed screenshots (scratchpad board-desktop/phone.png) | status: Verified
- DOD d4 One Method-style cycle ran in a tagged repo | C: ~z7e5 | proof: this commit's PLAN.md diff | status: Verified
- LESSON folded into docs/reference/method.md and CHANGELOG through v2.3.2:
  worktree pools must be pruned from discovery, and hidden-attribute views
  need explicit display guards — both found by real dogfood, both now pinned
  by regression tests. No further standing-knowledge delta.

- 2026-08-05T21:30:00Z ~m3k7 ~q8f2 ~t2b8 ~j6n4 DONE seat=chief — Method v1
  build slice from fresh `main@1ed58392`: AGENT.md, docs/reference/method.md,
  SKILL.md Method section, 4 contract tests, board scanner (3 TDD tests), and
  the read-only board view (2 e2e specs, desktop+phone). Steal-spec research
  grounded in source reads of beads (hash IDs, ready predicate), ralph
  (one-item loops, AGENT.md content law), spec-kit (analyze lint passes),
  liatrio (DoD coverage matrix), superpowers (skill enforcement), and OpenSpec
  (lesson-delta archive). Proofs on this head: contract tests 4/4, browser
  unittest 20/20, playwright 10/10, docs build, privacy scan ok. 'huncho'
  verified as plastic-labs/honcho — a Postgres+deriver second store; adopt its
  hook *pattern* only, not the store.

- 2026-08-05T06:20:00Z: R11 is merged, released, installed, and re-proven.
  PR #245 squash-merged to `main@7fd88682` with hosted CI, CodeQL (three
  analyzers), gitleaks, the public-ready gate, and tests on Python
  3.10/3.12/3.14 all green; Graphite was triggered and posted no findings.
  Release v2.2.1 is public with package SHA-256 `e2496f31…d64587`; the
  artifact was re-downloaded from the public release, checksum-verified,
  and installed globally, and `pilot-puppy doctor` reads 11/11. The exact
  dogfood shape that v2.2.0 failed — a Python repo with no `.pilot-puppy/`
  gitignore entry, a proof that generates interpreter caches, and a real
  native Cursor host — now completes prepare, launch (passed), accept (one
  local acceptance merge), and a second prepare on the installed CLI. The
  remaining Drive proof is the multi-lane customer-repo run in the
  successor row.

- 2026-08-05T05:45:00Z: R11 done from fresh `main@171351ac` in an isolated
  worktree. First, the operator machine finally runs what shipped: the
  released v2.2.0 package (SHA-256 `d5c92d…ab3723`) was installed globally
  from its verified artifact, the three skill mounts were repointed to the
  installed package, and `pilot-puppy doctor` reads 11/11 — all without
  touching the dirty lane checkout that had blocked this handoff. The first
  real end-to-end Drive dogfood on a disposable Python project then failed
  honestly: the host fixed the file and the focused test passed, but the
  scope gate blocked the lane on `__pycache__` files created by running the
  declared proof. A 21-agent adversarial review of the v2.2.0 source
  confirmed nine defect clusters in total, including a second P0 pair
  (vanilla-repo accept stranding on the product's own evidence; the browser
  reflecting raw OSError text with absolute paths). Every confirmed P0/P1 is
  fixed in six bounded commits with regression tests, and the same dogfood
  now passes prepare, launch, accept, and re-prepare. Proof on this head:
  Python 172/172, JavaScript 4/4, desktop and phone browser 6/6, docs build,
  public-ready privacy scan 0 findings across 106 files, and the development
  package check. Nothing was pushed before this entry's commit; deferred P2
  structure notes from the review (pseudo-module exec, duplicated sealing
  helpers) are recorded here and intentionally not acted on.

- 2026-08-04T22:29:33Z: R10 now closes the local work loop without becoming an
  autonomous delivery system. After a real disposable native-Codex Drive task
  produced a green kept review commit, an explicit acceptance action created a
  separate clean lead checkout, reran the named proof, and made one local
  acceptance commit. The resulting diff contained only the declared file;
  source and review checkouts stayed clean. Full Python (163), JavaScript (4),
  desktop/phone browser (6), docs, public-readiness, and development-package
  gates pass. No remote branch, pull request, deployment, publication, or
  external message was created. The browser now calls this final step **Bring
  checked work into this project** and keeps it an explicit foreground action.

- 2026-08-04T22:16:03Z: Real local dogfood now proves the foreground path,
  not just a fake adapter: a disposable, one-file Drive task selected native
  Codex from the local roster, wrote a green kept review-branch commit, and
  left its source checkout clean. A separate detached lead checkout reproduced
  the named check and `git diff --check`; the only tracked change was the
  declared one file. This is local execution and lead reproduction evidence
  only—no remote branch, pull request, merge, deployment, publication, or
  customer project was touched. R10's next smallest gap is an explicit,
  lead-reviewed handoff from that kept branch into ordinary delivery, without
  adding automatic GitHub or deployment behavior.

- 2026-08-04T22:14:00Z: Pushed the reviewed R10 implementation as public
  branch `codex/pilot-puppy-drive-langfuse-20260804` at `7ce87de5` from its
  isolated worktree. No pull request, merge, release, or deploy was created.

- 2026-08-04T22:10:23Z: R10 now has a foreground Drive Packet and both CLI
  and loopback-browser flow: it previews only short work summaries, prepares
  no more than three separate local handoffs, and starts them only after a
  distinct **Start ready work** action. The browser never receives task text,
  paths, commands, provider details, or credentials; optional Langfuse export
  remains off by default and metadata-only after local evidence. Full Python,
  JavaScript, desktop/phone browser, docs, public-ready, and development
  package checks are green. The intentional current stop is a kept local
  review branch after scope and named-check success—no push, PR, merge,
  deployment, publish, retry, or remote control has been added. Next: dogfood
  one harmless real native-host Drive task, reproduce its review branch, then
  decide the smallest lead-reviewed merge handoff from evidence rather than
  inventing an autonomous delivery system.

- 2026-08-04T21:36:37Z: Started R10 from fresh public
  `main@10b35604` in an isolated worktree. The first slice adds an optional
  Langfuse lifecycle seam with a closed metadata allowlist and no control-path
  readback; route and host observation occur only after their local evidence
  file is durably written. Supervised Drive remains the next implementation
  slice, not a new queue, daemon, or second plan.

- 2026-08-04T16:29:20Z: The chief-of-staff surface now names the required operator sequence directly: Outcome, Now, Change, Proof, and A/B/C decision. The existing local role/host, sealed packet, privacy, and lead-acceptance contracts are unchanged.

- 2026-08-04T02:17:54Z: Revalidated the reachable Star67 public lane at branch
  `codex/star67-smoke-proof-20260804@5d6f005`. The Vercel front door returns
  HTTP 200; the Vercel-first README and source contain no `pivot-sql` or
  `nlau1193/pivot-sql` residue outside a dated historical audit receipt; and
  both full and production-only `npm audit --audit-level=high` runs report 0
  vulnerabilities. The remaining repository rename, homepage, and topic
  metadata write is still owner-admin gated (`admin:false`, `homepage:null`),
  so no cosmetic source edit or false rename claim was made. Star67 is closed
  for reachable implementation work and remains in the umbrella only for the
  owner-admin predicate and future live/merge/deploy readback.

- 2026-08-04T02:23:22Z: Continued the same full-portfolio Outcome and attempted
  to reopen the existing official Codex Security workspace for clean Moussey
  `main@3c44bbec`. The workspace command failed before setup submission, so no
  scan ID, findings, report, or remediation exists; no replacement workspace
  was created and no product or production surface was changed. Keep the
  official security predicate open and resume it from the existing workspace
  when the app/tooling handoff is healthy; the independent npm, CodeQL,
  gitleaks, and source-boundary receipts remain the only current evidence.

- 2026-08-04T02:30:27Z: Reopened the existing official Codex Security workspace
  successfully against clean Moussey `main@3c44bbec`. Setup validation is
  valid, but `setup.submitted=false`; the app is waiting for the user to press
  Start scan. The bounded wait ended without a scan ID, preflight, findings, or
  report, so no security result is claimed and no terminal fallback or second
  workspace was created. Resume from this same workspace after Start scan, then
  carry its canonical artifacts back into this umbrella plan.

- 2026-08-04T02:34:41Z: Advanced the reachable Moussey repair lane without
  touching the dirty primary or live owner runtime. Clean branch
  `codex/moussey-dependency-audit-20260804@e6dd162` passed a fresh production
  `npm audit --omit=dev --audit-level=high` with 0 vulnerabilities, the full
  consignment/invoice suite with 64 pass and 1 pre-existing skip, and the
  consignment surface check. The repair PR #121 remains OPEN/CLEAN and
  unmerged; authenticated production readback is still owner-controlled. The
  same receipt sweep confirms Pilot Puppy PR #99 at `36c3d1a` is
  OPEN/CLEAN/MERGEABLE with all required checks passing. No merge, deploy,
  credential, payment, ledger, or production-runtime write was made.

- 2026-08-04T02:36:24Z: Re-read the reachable public surfaces. The Snowcubes
  source-of-truth audit returned `ok: true` with Zack `$0.00`, Marathon
  `$0.00`, and Everyman `$22.00`; its 2026-05-21 Marathon record remains the
  explicit FREE/UNKNOWN row with no charge or payment row. `https://trysnowcubes.com/`
  returned HTTP 200 and no retired receivable or consignment-only billing/source
  labels. `https://learn-sql-peach.vercel.app/` returned HTTP 200 with Star67
  branding and no old repository-name text in the public HTML. No deployed
  surface or source data was changed; Snowcubes merge/deploy and Star67
  owner-admin metadata remain external predicates.

- 2026-08-04T02:38:11Z: Reproduced the Moussey repair branch's focused privacy
  boundary on `codex/moussey-dependency-audit-20260804@e6dd162`:
  `lib/moussey-url.test.ts` passes 4/4, covering removal of query credentials,
  URL userinfo, and STT WebSocket query credentials while preserving safe media
  capability tokens. This is branch proof only; PR #121 remains unmerged and
  the owner-controlled production runtime was not restarted.

- 2026-08-04T02:41:26Z: Re-read Pilot Puppy PR #99 after the latest plan
  correction. Head `7d90140` is OPEN/CLEAN with every required check passing:
  CI Python 3.10/3.12/3.14, browser-and-docs, CodeQL and its actions/
  JavaScript/Python analyses, gitleaks, public-ready-gate, and Graphite
  mergeability; `[code]smith` is skipped by policy. This closes the Pilot
  Puppy receipt gate only. The PR remains unmerged and the product, admin,
  runtime, deployment, and official-security predicates remain independent.

- 2026-08-04T02:12:44Z: Revalidated the full portfolio against current
  external state. Pilot Puppy PR #99 is `1836bcf` and OPEN/CLEAN/MERGEABLE with
  CodeQL, gitleaks, public-ready, Python 3.10/3.12/3.14, browser/docs, and
  Graphite passing; Star67 PR #2, Moussey PR #121, and Snowcubes security PR
  #1567 are also OPEN/CLEAN/MERGEABLE. The host gate remains constrained at
  62% free memory, `13.97/15.36 GiB` swap used, and `14 GiB` free on Data, so
  cleaner work and Snowcubes `npm ci` remain deferred. No merge, deploy,
  owner-admin metadata write, credential rotation, payment, ledger, or
  production-runtime write was made. Resume predicates remain explicit in the
  lane readback; the umbrella Outcome stays working.

- 2026-08-04T02:08:33Z: The clarified full-portfolio umbrella receipt is now
  pushed at Pilot Puppy PR #99 head `27045aa`. Its Analyze actions,
  JavaScript/TypeScript, and Python CodeQL jobs pass alongside gitleaks,
  public-ready, Python 3.10/3.12/3.14, browser/docs, and Graphite; GitHub's
  aggregate CodeQL row and `[code]smith` remain skipped by policy. This
  validates the orchestration-plan correction only: PR #99 remains
  OPEN/MERGEABLE/unmerged, and the active Star67, Moussey, Snowcubes, security,
  deployment, and handoff lanes remain in the same working Outcome.

- 2026-08-04T01:51:43Z: Completed the next full-portfolio receipt sweep. The
  umbrella Outcome remains active; no packet or PR closes it. Pilot Puppy PR
  #99 is OPEN/CLEAN/MERGEABLE with all current required checks passing.
  Star67 PR #2 is OPEN/CLEAN with build and Chromium/Firefox/WebKit checks
  passing; Snowcubes PR #1567 is OPEN/CLEAN/mergeable at its current base; and
  Moussey PR #121 is OPEN/CLEAN with no configured remote checks. No merge,
  deployment, owner-admin rename, credential rotation, payment, ledger, or
  production-runtime write was made. Continue the next reachable lane while
  keeping those external and owner-controlled predicates explicit.

- 2026-08-04T01:48:13Z: Re-read current public refs before another portfolio
  claim. Snowcubes `main@41e778148` explicitly records Marathon's 2026-05-21
  nine-pack stock-add as FREE/UNKNOWN with no charge or payment row; current
  source audit returned `ok: true`, `cafe:doctor` reported 18 checks with 0
  blocking failures, and focused source tests passed 314/24/14. The live
  storefront returned HTTP 200 with no retired receivable figures or
  consignment-only billing/source labels. Rebuilt Snowcubes PR #1567 from
  current `main` and carried only its reviewed lockfile commit; head is now
  `f51e2d90`, `npm ci` passes, production-only audit reports 0 vulnerabilities,
  and the PR is OPEN/CLEAN/mergeable. Pilot Puppy public main is now
  `d8c9bb0`; the local portfolio branch includes that public-main metadata and
  the current-lane receipt is being refreshed. No merge, deployment, ledger,
  Shopify, or payment write was made.

- 2026-08-04T01:39:24Z: Rebased Snowcubes security PR #1567 from stale base
  `cafb80c9` onto current public `main@546e220c`, then pushed the actual PR
  branch at `5e442977`. The change remains lockfile-only; production-only
  `npm audit --omit=dev --audit-level=high` returns 0 vulnerabilities and
  `git diff --check` passes. PR #1567 is OPEN/CLEAN/mergeable. Current-main
  source audit is `ok: true`, cafe doctor is 18/18 with 0 blocking failures,
  the focused source tests are 314/24/14, and the public storefront returned
  HTTP 200 without retired figures or consignment-only billing/source labels.
  No merge, deployment, ledger, Shopify, or payment write was made.

- 2026-08-04T01:30:55Z: After the portfolio-plan checkpoint was pushed,
  PR #99 reran and passed its full required receipt at `d268474`: Python
  3.10/3.12/3.14, browser/docs, CodeQL, gitleaks, public-ready, and Graphite
  all pass; `[code]smith` remains skipped by policy. The PR is still OPEN and
  unmerged, so this is review proof for the umbrella plan, not public-main or
  deployment proof.

- 2026-08-04T01:32:12Z: Pushed another docs-only portfolio checkpoint to PR
  #99 after removing stale current-head pinning. The new tip's required checks
  must be re-read before treating the PR as green; no merge or deployment is
  claimed.

- 2026-08-04T01:28:53Z: The full-portfolio control PR #99 is now
  OPEN/MERGEABLE at `39f36f7`; all required CI, CodeQL, gitleaks,
  browser/docs, public-ready, and mergeability checks pass, while
  `[code]smith` is skipped by policy. This proves the portfolio-plan change
  is reviewable; it is not a merge or deployment claim. A fresh readback of
  `https://trysnowcubes.com/` also returned HTTP 200 with HSTS, CSP,
  `x-frame-options: DENY`, and no retired receivable figures or consignment
  billing/source labels in the public body.

- 2026-08-04T01:25:54Z: Branch-owned Moussey production proof passed on
  isolated port `45123` from `codex/moussey-dependency-audit-20260804` at
  `e6dd162`: desktop/mobile consignment smoke, flow/focus/stepper-overlap
  smoke, and current tracker-authority readback all passed. A simulated
  remote request returned 401 without credentials and 200 with the
  Authorization header. The passcode was read from the local key file only;
  no URL token was used. The existing primary `:4321` process was not touched.

- 2026-08-04T01:23:33Z: Direct Snowcubes readback confirms security PR #1567
  is OPEN/MERGEABLE at head `479c48a4` against `cafb80c9`; production-only
  high audit returns 0 vulnerabilities and the source-truth audit returns
  `ok: true` with Zack `$0.00`, Marathon `$0.00`, and Everyman `$22.00`.
  The consignment branch `6dfd526` still records the 2026-05-21 Marathon
  row as FREE/UNKNOWN with no payment row and no reopen/collect action. No
  merge, deployment, ledger, Shopify, or payment write was made.

- 2026-08-04T01:20:42Z: Read-only Moussey branch receipt confirms PR #121 at
  `e6dd162` is clean and reproducible: consignment surface PASS, invoice
  suite 64 pass/1 skip, production-only high audit 0 vulnerabilities, and
  `git diff --check` PASS. The old billing/source/amount-due/history wording
  is absent; only intentional settled-state `No payment due` remains, and
  passcode text is confined to the operator gate. The remaining predicate is
  branch-owned authenticated browser proof; the existing `:4321` process was
  not touched because it belongs to the dirty primary checkout.

- 2026-08-04T01:18:51Z: Star67's full-data CI correction is proven. Both the
  push and pull-request workflows (`30867642389` and `30867639603`) completed
  successfully at `5d6f005`: build, Chromium, Firefox, and WebKit all passed;
  the browser jobs consumed the complete generated `public/data` artifact.
  PR #2 remains OPEN/MERGEABLE and the Vercel launch surface is unchanged.
  This closes the artifact/CI proof gap only; rename/admin, merge, and any
  deployment predicate remain separate.

- 2026-08-04T01:07:11Z: Re-read the deployed Star67 public surface while the
  full-data branch CI was still running. `https://learn-sql-peach.vercel.app/`
  returned HTTP 200 from Vercel with `strict-transport-security`,
  `x-content-type-options: nosniff`, and `x-frame-options: DENY`; the body
  contained Star67 markers and no stale Pivot SQL marker. This is live-main
  evidence only; the pending branch has not been deployed.

- 2026-08-04T01:05:11Z: Consumed the first full-data CI correction. The build
  job passed and the artifact restored `manifest.json`, but WebKit preview
  then exposed a second missing generated input, `public/data/dim_account.parquet`.
  Branch `codex/star67-smoke-proof-20260804` now carries `5d6f005`, which
  uploads the entire generated `public/data` directory alongside `dist` and
  downloads it at repository root. YAML and diff checks pass and a fresh CI
  run is pending. The security workspace remains valid but its setup is still
  unsubmitted.

- 2026-08-04T00:44:33Z: Continued the portfolio Outcome rather than narrowing it
  to a single deliverable. Star67's hosted proof branch is now at `bc023a9`:
  the CI workflow builds `dist` once, uploads the exact artifact, and makes
  Chromium, Firefox, and WebKit consume that artifact instead of running three
  concurrent native builds. This addresses the prior CI-only DuckDB failure
  boundary without changing the deployed app. PR #2 remains OPEN; the new
  build check is pending. The packet advances the Star67 lane and does not
  close the portfolio Outcome.

- 2026-08-04T00:40:43Z: Fresh review-state readback kept the portfolio open.
  Star67 PR #2 still has Chromium, Firefox, and WebKit checks pending;
  Moussey PR #121 is OPEN/CLEAN with no checks reported; Pilot Puppy PR #99
  is OPEN/BEHIND after `dc076fb` with its required checks rerunning. Snowcubes
  PR #1567 remains OPEN/CLEAN/mergeable with only its policy-skipped/Graphite
  readback. No merge, deployment, rename, credential, payment, or owner-runtime
  action was claimed.

- 2026-08-04T00:38:42Z: Advanced the Moussey security/clarity lane without touching
  the dirty primary or live runtime. The pushed repair/UI branch `e6dd162` was
  checked against `origin/main@3c44bbec` and opened as PR #121:
  https://github.com/leojkwan/moussey/pull/121. It contains only the lockfile
  vulnerability repair and two residual consignment-copy fixes; prior proof
  remains 0 production audit vulnerabilities, focused consignment surface and
  invoice tests green, production build green, and diff clean. PR #121 is
  OPEN/CLEAN with no checks reported yet; merge/deploy remains unclaimed.

- 2026-08-04T00:36:07Z: Continued the whole-portfolio Outcome with a reachable
  Star67 proof slice. The current harness reproduced 182/183 against the live
  Vercel URL because one hosted behavior assertion incorrectly required
  `localPreview=true`; the result itself was built-in/private, advisory, on
  the current result, and made zero coach requests. Isolated branch
  `codex/star67-smoke-proof-20260804` removes only that predicate at `5b4c7ec`.
  Hosted smoke now passes 183/183; `npm run build` passes generation,
  determinism, contracts, typecheck, and Vite production build; `npm audit
  --audit-level=high` reports 0 vulnerabilities; and `git diff --check`
  passes. PR #2 is OPEN with its browser matrix running. The deployed app was
  not changed. Snowcubes PR #1567 was re-read at current base `cafb80c9` and
  head `479c48a4`: OPEN/CLEAN/mergeable with Graphite mergeability passing and
  policy-skipped checks; no merge or deployment is claimed. Owner-admin,
  Moussey C11, cleaner host resource, security scan start, credentials,
  payment, merge/deploy, and portability predicates remain open.

- 2026-08-03T23:51:58Z: The clean-CI receipt was followed by one plan-only
  portfolio refresh, so PR #99's required checks are running again on the new
  documentation head. The last code-equivalent head `ab10af3` passed every
  required listed check; the current refresh changes only `PLAN.md`. No code,
  product data, external admin metadata, merge, deployment, credential,
  payment, or owner-runtime state changed.

- 2026-08-03T23:50:56Z: Fresh post-push readback for Pilot Puppy PR #99 at
  head `ab10af3` completed cleanly: test 3.10/3.12/3.14, browser-and-docs,
  Analyze actions/javascript/python, CodeQL, gitleaks, public-ready-gate, and
  Graphite mergeability all passed; `[code]smith` was skipped by policy. The
  PR remains OPEN/BEHIND and unmerged. No merge, deployment, external admin
  rename, credential, payment, or owner-runtime action was taken.

- 2026-08-03T23:49:26Z: Closed the Snowcubes C14 evidence predicate without
  changing money state. The local read-only iMessage fallback found the Zack
  thread's 2026-07-25 drop record: 10 packs were reported and one JPEG was
  registered on the same Messages row (`chat.db` row `429590`, 4.3 MB). The
  JPEG payload is not downloaded on this Mac, so no image interpretation is
  claimed. Snowcubes source audit remained `ok: true` with 7 Bagels `$0.00`,
  Everyman `$22.00`, and Marathon `$0.00`; `cafe:doctor -- --fast` passed all
  9 blocking checks. The source-plan receipt is committed at `61709a22` on
  `codex/consignment-plan-free-decision-20260803`; no ledger, tracker,
  Shopify, payment, merge, deployment, or partner-facing state changed. C11,
  owner-admin, cleaner host-resource, security scan, credential rotation,
  merge/deploy, and portability predicates remain open.

- 2026-08-03T23:35:37Z: Continued the whole-portfolio Outcome with a bounded
  Moussey security slice; this advances one lane and does not close the
  portfolio. A fresh audit of clean Moussey `origin/main@3c44bbec` found 3
  production dependency vulnerabilities (1 moderate, 2 high) in transitive
  `hono`, `ip-address`, and `undici` packages. In disposable worktree
  `/private/tmp/moussey-audit-fix.U5paDH`, a lockfile-only repair upgraded them
  to `4.13.0`, `10.4.0`, and `7.29.0`; `npm audit --omit=dev --audit-level=high`
  returned 0 vulnerabilities, `npm ci --ignore-scripts` completed, the
  65-test consignment/invoice suite passed 64/65 with one pre-existing skip,
  the consignment-surface check passed, the production build passed, and
  `git diff --check` passed. Commit `63293fb` is pushed on
  `leojkwan/moussey` branch `codex/moussey-dependency-audit-20260804` and is
  not merged. The dirty Moussey primary, live runtime, credentials, payment,
  deployment, and official Codex Security setup were not mutated; the
  official workspace remains `setup.submitted=false` with no scan report.

- 2026-08-03T23:28:18Z: Re-audited the full portfolio and reopened the existing
  Codex Security workspace rather than creating a second scan. Pilot Puppy
  revision 62 is clean at `76754c0`; PR #99 is OPEN/CLEAN with all listed
  checks passing, and Snowcubes PR #1567 remains OPEN/CLEAN/mergeable at
  `8d6ae00c`. Star67 main remains `1277dd8` with its Vercel front door returning
  HTTP 200. Snowcubes main `c48ace456` source audit remains `ok: true` with
  Zack `$0.00`, Marathon `$0.00`, and Everyman `$22.00`; the public storefront
  remains HTTP 200 without retired receivable figures or removed billing/source
  labels. Nicole's MacBook Air target is online; fresh `/api/health` and
  `/api/consignment?view=summary` responses are HTTP 200, but the summary body
  remains `data_unavailable`, so C11 is still open. The Codex Security workspace
  targets clean Moussey `origin/main@3c44bbec` with `setup.submitted=false`; the
  bounded wait ended without a scan ID, report, or findings. Host pressure is
  still unsafe for cleaner build/browser/media work. No dirty primary, owner
  process, credential, payment, Shopify, merge, deploy, or cleaner mutation
  occurred.

- 2026-08-03T23:22:37Z: Pushed the revision-61 receipt as commit `1f801a1`.
  Because this is a plan-only change, PR #99 checks reran on the new head; the
  fresh post-push readback showed analysis jobs in progress and the remaining
  checks queued. The preceding head `09ae9d4` had all listed required checks
  passing. `git diff --check`, `pilot-puppy status --json`, and
  `npm run docs:build` passed before the push. No merge or deployment is
  claimed; the next resume move is to read the new check result, not to create
  another receipt-only push.

- 2026-08-03T23:20:52Z: Re-ran the whole-portfolio readback from current
  worktrees and public surfaces. Star67's current-main README still leads with
  the Vercel launch URL and `https://learn-sql-peach.vercel.app/` returned
  HTTP 200. Snowcubes current-main source audit returned `ok: true` with Zack
  `$0.00`, Marathon `$0.00`, and Everyman `$22.00`; `https://trysnowcubes.com/`
  returned HTTP 200 without the retired receivable figures or removed
  billing/source labels. Pilot Puppy PR #99 at `09ae9d4` is OPEN/CLEAN with
  every required listed check successful; Snowcubes PR #1567 at `8d6ae00c`
  remains OPEN/CLEAN/mergeable. Nicole's MacBook Air is active on Tailscale;
  fresh quoted requests to `/api/health` and `/api/consignment?view=summary`
  returned `200`, but the summary body is still `data_unavailable`, so C11
  remains open. No dirty primary checkout, owner process, credential,
  payment, Shopify, merge, deploy, or cleaner mutation occurred.

- 2026-08-03T23:16:05Z: Completed the current-ref reconciliation readback.
  Pilot Puppy PR #99 at head `e2b5a5e` against public `main@601c37c` is
  OPEN/CLEAN with CI 3.10/3.12/3.14, browser/docs, CodeQL, gitleaks,
  public-ready, Graphite, and `[code]smith` skipped by policy. Snowcubes PR
  #1567 at `8d6ae00c` against `main@c48ace456` is OPEN/CLEAN/mergeable with
  Graphite passing and review checks skipped by policy. A fresh C11 readback
  found Nicole's MacBook Air online and Tailscale-pingable; `/api/health` and
  `/consignment` return `200`, but `/api/consignment?view=summary` returns
  `data_unavailable` because consignment data is not configured on that machine.
  The four expected C14 source CSVs were not found in the current repo/history
  or local attachment search, so none was fabricated. No owner process,
  credential, Shopify, payment, merge, deploy, or cleaner mutation occurred.

- 2026-08-03T23:13:14Z: Re-read direct GitHub refs and reconciled the current
  portfolio boundary. Pilot Puppy public `main@601c37c` is the current base;
  PR #99 was OPEN/CLEAN with all listed CI, browser/docs, CodeQL, gitleaks,
  public-ready, Graphite, and `[code]smith` checks passing at head `226444e`
  before this receipt refresh. Snowcubes public `main@c48ace456` still passes
  the source-truth audit with Zack `$0.00`, Marathon `$0.00`, Everyman `$22.00`;
  the live storefront remains HTTP 200 without retired figures or removed
  billing/source labels. Refreshed security PR #1567 onto that current base at
  `8d6ae00c`: production/high audit `0`, full audit `2 low esbuild` findings,
  diff check clean. No merge, deployment, Shopify mutation, owner-runtime
  restart, credential action, or cleaner mutation occurred.

- 2026-08-03T23:09:18Z: Merged public `main@601c37c` into the portfolio receipt
  branch and resolved the `PLAN.md` conflict so both intents survive. The
  portfolio Outcome, decision, predicates, and receipts stay authoritative, and
  main's 280-character Operator Brief contract now holds: `Outcome`, `Next`,
  `Proof`, `Proof Summary`, and `Proof Delivery` fit the contract while their
  full text moves to unparsed `... Detail` bullets that the browser and
  `status` ignore. `pilot-puppy status --json` returns a valid
  `pilot-puppy.status.v1` brief at Revision 57 with no contract error, and
  main's brief-contract plus other-computer-recheck Progress entries are
  preserved. No routing, execution, provider, credential, or evidence behavior
  changed.

- 2026-08-03T22:58:20Z: Reconciled the Snowcubes Marathon 2026-05-21 decision
  across its canonical FPA and consignment-hardening plans. Isolated branch
  `codex/consignment-plan-free-decision-20260803` at `c05efdde` now records the
  row as deliberate FREE, payment UNKNOWN, `$0.00`, with no charge/payment row,
  and fences the historical `$225.63`, `$342.04`, and `$57.75` artifacts; source
  audit still returns `ok: true`. A fresh Tailscale readback found the Moussey
  target reachable but not configured for consignment data, so C11 remains an
  explicit runtime predicate and no owner process was restarted. The official
  Codex Security plugin workspace is open on clean Moussey main and has not yet
  delivered findings; the full portfolio Outcome remains active.

- 2026-08-03T23:04:00Z: Pushed the refreshed full-portfolio receipt as Pilot
  Puppy PR #99 head `e5b7bd2`. Its CI, browser/docs, CodeQL, gitleaks,
  public-ready, and Graphite checks passed; `[code]smith` was still in progress
  at readback, so no clean/mergeable or merged state is claimed. The plan keeps
  the Snowcubes C14 source-cited count gate, Moussey C11 authenticated-runtime
  gate, Star67 owner-admin metadata gate, cleaner host/resource gate, security
  report gate, credential rotation, deployment, and portability as separate
  predicates within the same active portfolio Outcome.

- 2026-08-03T23:06:55Z: Pilot Puppy PR #99 advanced to head `be02f0f` after
  the explicit C14/current-check receipt update. CodeQL, the three analysis
  jobs, and Graphite passed; `[code]smith` remains in progress. Earlier-head
  CI, browser/docs, gitleaks, and public-ready results are not reused as proof
  for this new head. The plan remains the sole whole-portfolio authority and
  the PR remains unmerged.

- 2026-08-03T23:07:54Z: Removed the self-referential current-head hash from
  the operator summary. The final plan-only refresh is pushed, but its new
  external checks are not yet read back; earlier-head results remain historical
  only. This keeps the plan honest without turning each receipt refresh into a
  new proof claim.

- 2026-08-03T19:12:15Z: Confirmed the full-portfolio receipt is durable and
  current: PR #99 remains OPEN/CLEAN/MERGEABLE against `main@2029756`, all
  required checks pass, and the canonical plan is the sole portfolio authority.
  The plan intentionally records PR state without embedding a self-referential
  head hash that becomes stale every time this plan is refreshed.

- 2026-08-03T19:10:24Z: Refreshed the canonical portfolio receipt to the exact
  current PR #99 head `1e50a8cdd4c5cee6afc004d13a5a895935ae5539` after the
  Revision 50 plan-only push. The new head's required CI, browser/docs,
  CodeQL, gitleaks, public-ready, and Graphite checks are green; CodeSmith is
  skipped by repository policy. The full portfolio Outcome remains open.

- 2026-08-03T19:10:14Z: The final receipt head is now
  `89a9f5b723d4118f34e5df99d719f8204bed2ae4`, based on public
  `main@2029756`, OPEN/CLEAN/MERGEABLE. Its fresh CI, browser/docs, CodeQL,
  gitleaks, public-ready, Graphite, and CodeSmith checks all pass. This is the
  current Pilot Puppy proof boundary; the full portfolio Outcome remains open
  for the independent product and external gates below.

- 2026-08-03T19:04:39Z: Pilot Puppy PR #99 is current against public
  `main@2029756`: head `a3e3d9fc6ca42033d71d479d7c5adc314bbf05ed`,
  OPEN/CLEAN/MERGEABLE. CI 3.10/3.12/3.14, browser/docs, CodeQL, gitleaks,
  public-ready, Graphite, and CodeSmith all pass. The portfolio receipt now
  records the public R5 seat-overlay release as well as the full cross-product
  Outcome; no external merge or deployment is claimed.

- 2026-08-03T19:01:01Z: Pilot Puppy public main advanced to `2029756` through
  merged PR #111, delivering the R5 owner-local, route-bound native seat
  overlay. Refreshed the portfolio branch onto that exact base and resolved
  the plan conflict in favor of the full portfolio Outcome, while preserving
  the new R5 implementation and its public-main proof. The receipt branch is
  not yet pushed after this refresh; no external merge, deployment, credential,
  runtime, or customer-data mutation was attempted.

- 2026-08-03T18:57:33Z: Closed the clean-clone Moussey invoice-authority
  evidence prerequisite. After generating the expected local E2E bundle, the
  current `origin/main@3c44bbec` helper returned `ok: true`,
  `allDryRunsOk: true`, `privateFieldsRedacted: true`, and
  `mutationPerformed: false`. Its ignored generated output lives in the
  separate Snowcubes clone, whose Git worktree remains clean. The helper's
  operator-gate state is not a partner-balance claim; Snowcubes
  `audit-consignment-source-truth.py` remains the money/source authority.

- 2026-08-03T18:55:06Z: The final receipt head is now
  `850068f6f108454098c69a31a6ea9ff18cf3b701`, and its fresh remote run is
  OPEN/CLEAN/MERGEABLE with CI 3.10/3.12/3.14, browser/docs, CodeQL,
  gitleaks, public-ready, and Graphite passing; `[code]smith` is skipped for
  the docs-only plan change. No merge or public-main readback is claimed.

- 2026-08-03T18:53:27Z: Portfolio PR #99 reached its final post-push proof at
  `164644b37246df1cd7edf53162e27024fc3d12b2`: OPEN/CLEAN/MERGEABLE, with CI
  3.10/3.12/3.14, browser/docs, CodeQL, gitleaks, public-ready, and Graphite
  checks passing. `[code]smith` is skipped because this receipt changes only
  the durable plan. The PR remains unmerged; public-main readback is still the
  external next move.

- 2026-08-03T18:51:47Z: Revalidated the whole portfolio instead of collapsing it
  into one deliverable. Clean Moussey `origin/main@3c44bbec` passed the focused
  65-test consignment/invoice suite (64 pass, 1 pre-existing skip), the
  consignment-surface anti-slop check, a production webpack build, and
  production-only `npm audit` with 0 vulnerabilities. A fresh clone cannot run
  the broader invoice-authority helper without its generated E2E bundle; that
  missing prerequisite is recorded as an evidence boundary, not a false green.
  Snowcubes public main advanced to `f3f877ee`; source audit remains `ok: true`
  with Zack `$0.00`, Marathon `$0.00`, and Everyman `$22.00`, including the
  5/21 Marathon FREE/UNKNOWN decision. Refreshed security PR #1567 onto that
  exact base as `48121626`; its diff is only `package-lock.json`, `git diff
  --check` passes, production/high audit is clean, and full audit leaves only
  two low Shopify CLI `esbuild` findings. No merge, deploy, owner-runtime
  restart, owner-admin write, cleaner mutation, or personal-media mutation was
  attempted.

- 2026-08-03T18:44:20Z: Snowcubes public main advanced to `926e7d34` through a
  documentation-only release. The source-authority audit still returns
  `ok: true` with Zack and Marathon at `$0.00` and Everyman at `$22.00`; the
  live storefront remains HTTP 200 without retired figures or
  consignment-only labels. Refreshed security PR #1567 onto that exact base
  as `52e57137`; its current diff is only `package-lock.json`, `git diff
  --check` passes, the production/high audit reports 0 vulnerabilities, and
  the full audit leaves only two low `esbuild` findings in the Shopify CLI
  dev chain. The PR is OPEN/CLEAN/MERGEABLE and not merged or deployed. The
  current host sample has about 915 MiB swap free, so Cleaner and the owned
  Moussey runtime remain paused. No merge, deployment, owner-admin write,
  runtime restart, or personal-media mutation was attempted.

- 2026-08-03T18:34:05Z: Re-read all reachable public predicates. Snowcubes
  `origin/main@a265e0869` still returns `ok: true` from the source-authority
  audit and the live storefront remains HTTP 200 without retired figures or
  consignment-only labels. A fresh public-main lockfile audit reports 7 high
  and 4 low development-chain findings; the security PR #1567 head
  `8960bf02` reports 0 production/high findings and only 2 low `esbuild`
  findings in the Shopify CLI chain, with `git diff --check` clean. Pilot
  Puppy portfolio PR #99 is now `3ba54a0`, OPEN/CLEAN/MERGEABLE, and all
  required CI, CodeQL, gitleaks, browser/docs, public-ready, and Graphite
  checks pass; `[code]smith` is skipped for this docs-only receipt. No merge,
  deployment, owner-admin write,
  authenticated-runtime restart, or cleaner mutation was attempted.

- 2026-08-03T18:25:49Z: Reconciled the Pilot Puppy portfolio receipt with the
  current branch head `41ddc699`. Its required CI 3.10/3.12/3.14,
  browser/docs, CodeQL, gitleaks, public-ready, and Graphite checks pass;
  `[code]smith` is skipped. The plan-only receipt is current and does not
  claim the open external merge.

- 2026-08-03T18:22:27Z: Snowcubes public main advanced to `7a0e59b3`; the
  current source-authority audit still returns `ok: true` with Zack and
  Marathon at `$0.00` and Everyman at `$22.00`. The live storefront remains
  HTTP 200 and exposes none of the retired amounts or removed billing/source
  labels. Rebased security PR #1567 from `c78b8edb` onto current main and
  pushed `8960bf02`; the diff remains exactly `package-lock.json`, diff check
  passes, and the production-only lockfile audit reports 0 vulnerabilities.


- 2026-08-03T18:19:42Z: Snowcubes public main advanced to `373a556e`; the
  source-authority audit still returns `ok: true` with Zack and Marathon at
  `$0.00` and Everyman at `$22.00`. The live storefront is HTTP 200 and does
  not expose `$225.63`, `$342.04`, `$57.75`, or the removed billing/source
  labels. Rebased security PR #1567 from `165fab4a` onto current main and
  pushed `c78b8edb`; the diff remains only `package-lock.json`, diff check
  passes, and the production-only lockfile audit reports 0 vulnerabilities.


- 2026-08-03T18:16:44Z: Re-read the parked host/runtime predicates. The Mac
  reports 60% system-wide memory free, about 50,849 MiB of 52,224 MiB swap in
  use, and 16 GiB root free; this does not clear MPCLEAN-254, so no Cleaner
  build, browser/media ladder, process restart, or source/personal-media
  mutation ran. Moussey `:4321` is still PID 73384 from the dirty owner
  checkout. Star67 still reports `admin=false` with no homepage, and the two
  open PRs remain unmerged. This is a current safety boundary, not a claim of
  portfolio completion.

- 2026-08-03T18:13:42Z: Portfolio PR #99 at `c0840e01` completed its fresh
  post-plan-update proof cycle. CI 3.10/3.12/3.14, browser/docs, CodeQL,
  gitleaks, public-ready, and Graphite all pass; `[code]smith` is skipped.
  GitHub reports the PR OPEN/CLEAN/MERGEABLE and not merged. This closes the
  current Pilot Puppy proof packet, not the whole portfolio Outcome.

- 2026-08-03T18:11:49Z: Re-read current Snowcubes `origin/main@5d9a7bc4` and
  reran `audit-consignment-source-truth.py`; it returned `ok: true` with Zack
  `$0.00`, Marathon `$0.00`, and Everyman `$22.00`. Rebased security PR #1567
  from `77e2bb5e` onto that current main and pushed `165fab4a`. The resulting
  diff is exactly `package-lock.json`; `git diff --check` passed and the
  production-only lockfile audit reported 0 vulnerabilities. No merge,
  deployment, or dirty primary checkout was touched.

- 2026-08-03T18:04:59Z: Re-read the Star67 public presentation against current
  `origin/main@1277dd8`. The README is 37 lines, puts the Vercel launch link
  before local setup, explains the no-account/local-browser boundary, and
  keeps contributor commands below the user path. The live Vercel URL returned
  HTTP 200 with the Star67 page title and branding. No copy change was needed;
  the remaining Star67 predicate is GitHub owner-admin access for the rename,
  homepage, and topic settings.

- 2026-08-03T18:01:37Z: Ran the bounded Codex Security CLI dry-run against
  current Snowcubes `origin/main@29383d7f9` with
  `npx --yes @openai/codex-security@0.1.5 scan . --dry-run --format json`.
  Input validation and preflight passed; the receipt is explicitly dry-run
  only, authentication was unverified, and no findings or remediation are
  claimed. The disposable worktree was removed after the readback.

- 2026-08-03T17:58:39Z: PR #99 at `cd4182ca` reached a clean required-check
  readback: CI 3.10/3.12/3.14, browser/docs, CodeQL, gitleaks, public-ready,
  and Graphite all pass; `[code]smith` is skipped. The portfolio branch is
  pushed and reviewable but remains unmerged by the external merge boundary.
  This closes the Pilot Puppy ledger-proof packet, not the whole portfolio
  Outcome. Star67 admin metadata, Moussey authenticated runtime, Snowcubes
  security merge/deploy, cleaner host safety, credential rotation, and
  cross-host portability remain separately tracked predicates.

- 2026-08-03T17:56:55Z: Re-read Snowcubes current public main at
  `29383d7f9` in a clean disposable worktree. `audit-consignment-source-truth.py`
  returned `ok: true` with Zack `$0.00`, Marathon `$0.00`, Everyman `$22.00`,
  and the 2026-05-21 Marathon row FREE/UNKNOWN with no charge/payment row.
  Focused current-main proof passed rollup 24/24, summaries 14/14, output
  validation 314/314, and cafe doctor 93/93. `https://trysnowcubes.com/`
  returned HTTP 200 and its body contained none of the retired amounts or
  consignment-only billing/source labels. No dirty primary, PR branch, merge,
  deployment, or customer data was changed.

- 2026-08-03T17:54:27Z: Final check-state readback for the current portfolio
  packet. PR #99 is at `3c564ebc`; Graphite mergeability passes, required
  CI/CodeQL/gitleaks/public-ready checks are pending, and `[code]smith` is
  skipped. This is a normal open PR state, not a product failure and not a
  reason to create another queue or plan. Star67, Moussey, Snowcubes, cleaner,
  security, deployment, and portability predicates remain listed above with
  their real owners and resume conditions.

- 2026-08-03T17:53:23Z: Reconciled the portfolio ledger after Pilot Puppy
  `v2.1.0` role-routing changes landed on the PR branch. The whole Outcome is
  still active: Star67's admin metadata, Moussey authenticated runtime,
  Snowcubes merge/deploy, cleaner host safety, credential rotation, and
  cross-host portability remain separate predicates. PR #99 is at `defa64d8`
  and its fresh CI/CodeQL/gitleaks/public-ready/[code]smith jobs are running or
  queued; no merge or public-main claim is made. The latest host sample remains
  unsafe for cleaner work (`63%` free memory, `51,017/52,224 MiB` swap used,
  `23 GiB` root free, load `11.67/10.97/12.28`). No owner checkout, process,
  merge, deployment, credential, or personal-media mutation was performed.

- 2026-08-03T17:47:50Z: Reproduced current Moussey `origin/main@3c44bbec`
  consignment proof in a clean disposable worktree. `npm ci --include=dev
  --ignore-scripts` reported 0 vulnerabilities; the consignment/invoice suite
  passed 64/65 with one pre-existing skipped visit-delegation test, URL-boundary
  tests passed 4/4, recorder tests passed 7/7, the consignment-surface check
  passed, the production webpack build passed, `npm audit --omit=dev` returned
  0 vulnerabilities, and `git diff --check` passed. Source inspection confirms
  the old `$225.63`, `$342.04`, and `$57.75` values are a retired-open-balance
  guard only, while passcodes stay in headers/cookies and the media capability
  token is the documented exception. The stale owner `:4321` runtime was not
  restarted; authenticated live browser readback remains owner-controlled.

- 2026-08-03T17:43:09Z: Re-read current public refs and continued the next
  reachable product lane. Star67 `origin/main@1277dd8` already contains the
  accessibility and plain-language progress behavior from the existing branch;
  no redundant PR was opened. Current-main proof passed `npm run data` with
  2,930,845 rows, casebook 18/18, `npx tsc -b`, `npx vite build`, and preview
  smoke 183/183 with no uncaught errors or hosted-sync requests. Snowcubes
  current `origin/main@ecaa2b20` source audit returned `ok: true`; current
  focused proof passed 24 rollup tests, 14 summary tests, 314 output-validator
  tests, 93 cafe-doctor tests, and `npm run cafe:doctor` 18 checks with 0
  blocking failures. The source readback keeps Zack `$0.00`, Marathon `$0.00`,
  Everyman `$22.00`, and the 2026-05-21 Marathon row FREE/UNKNOWN with no
  charge or payment row. No money, Shopify, deployment, or dirty-primary
  mutation occurred.

- 2026-08-03T17:31:40Z: Reused the official Codex Security CLI rather than
  adding a scanner surface. Version `0.1.5` loaded successfully; clean-revision
  `scan . --dry-run --format json` passed for Pilot Puppy `396ae544`, Star67
  `1277dd8`, Snowcubes `c16d1f93`, and Moussey `3c44bbec`. A real standard
  Pilot scan authenticated and entered the scan phase, then was canceled after
  no findings output because the host resource gate was already red. Partial
  state was kept outside the repos, no finding was accepted, and the temporary
  worktrees were removed. The existing CodeQL/gitleaks/npm-audit/source proofs
  remain current. The same read-only host audit exposed credential-bearing MCP
  process arguments; values were not recorded and no owner process was touched.
  Resume security with owner-approved credential rotation/relaunch, then rerun
  the Codex scan only after the host resource gate is green.

- 2026-08-03T17:21:50Z: Re-read all named portfolio refs, open PRs, live
  surfaces, and canonical plan rows. Pilot Puppy PR #99 is OPEN/CLEAN at
  `f1694484` with all required CI, CodeQL, gitleaks, browser/docs,
  public-ready, and mergeability checks passing; it is not merged. Star67
  remains public `nlau1193/pivot-sql` with homepage unset and admin permission
  absent. Snowcubes remains `origin/main@c16d1f93`, live HTTP 200, with PR #1567
  OPEN/CLEAN; F9, F10, and F12 remain Found-export, visit-cycle, and product
  fact gates owned by Leo/Nicole rather than missing code. Moussey consignment
  remains clean source at `3c44bbec`, but its owner process is still the stale
  `:4321` runtime. The active cleaner plan is now included in the portfolio
  map: its first resource sample is red on swap/disk pressure, the dry-run
  cleanup has no meaningful safe reclaim, and the existing single-writer lease
  forbids overlapping edits. Continue reachable non-heavy lanes; resume cleaner
  only after two quiet green host samples plus lease/readiness confirmation.

- 2026-08-03T17:17:49Z: Amp review corrected the operating brief: the active
  goal is the full Star67, Moussey, Snowcubes, security, deployment, and
  handoff portfolio. “One bounded task” is only the safe execution packet; it
  is not a one-feature or one-repository finish line. Refreshed the external
  readback to Snowcubes `origin/main@c16d1f93`; PR #1567 remains OPEN/CLEAN at
  `77e2bb5e` against its previously reviewed `27665b6e` base. No product code
  was changed. Continue all reachable lanes; leave owner-admin, authenticated
  runtime, merge/deploy, and portability predicates explicit.

- 2026-08-03T17:13:44Z: Audited the complete current Moussey runtime source for
  the password-URL requirement, not just consignment. `lib/moussey-url.ts`
  removes URL userinfo and all credential query keys; WebSocket URLs clear
  query and hash before connection; the only preserved token is the documented
  short-lived cleaner-media capability. No runtime source path emits a
  password/passcode/token URL; remaining token strings are test fixtures or
  the intentional media exception. Clean `origin/main@3c44bbec` proof passes
  with dev dependencies installed: 39/39 URL, phone-origin, consignment, and
  route tests (one pre-existing visit-delegation test skipped), the
  consignment-surface check, a production webpack build, and `npm ci` with
  zero reported vulnerabilities. No source change was needed; the invariant
  is already centralized and covered. The remaining Moussey predicate is only
  owner-controlled runtime restart plus authenticated browser readback.

- 2026-08-03T17:06:10Z: Rebased Snowcubes security PR #1567 onto the current
  public main `27665b6e` and pushed `77e2bb5e`. The diff remains exactly one
  file, `package-lock.json`, and `git diff --check` passes. In the isolated
  worktree, 208/208 Jest suites and 1,672/1,672 tests pass; the full 800-test
  Python suite and serial Node gate pass; production audit is zero, the
  high-severity audit exits clean with two low dev-only Shopify/esbuild
  findings, gitleaks is clean, source truth is `ok: true`, and `cafe:doctor`
  reports 18 checks with no blocking failures. GitHub readback is
  `OPEN/CLEAN`, base `27665b6e`, head `77e2bb5e`, Graphite mergeability passes,
  and `[code]smith` is skipped. No merge or deployment is claimed; the next
  security predicate is the external review/merge path followed by
  post-merge reruns.

- 2026-08-03T16:20:00Z: Reframed the active outcome from a narrow platform
  proof slice to the full reachable product portfolio, rebased on the merged
  Python-floor and configuration-default receipts at revision 8. Star67 README
  commit
  `0721078` is pushed and the Vercel surface is live/healthy; clean Snowcubes
  `origin/main@3be131f` passes the source-truth audit and focused FPA,
  consignment, cafe-doctor, and recorder suites; clean Moussey
  `origin/main@3c44bbec` passes the 65-test consignment/invoice suite, the
  credential-free URL suite, the consignment-surface check, and production
  build; `trysnowcubes.com` returns HTTP 200. The requested GitHub rename is
  the only current external blocker: the authenticated account has WRITE but
  not ADMIN permission, so the old repository name remains factual.
- 2026-08-03T16:03:34Z: Revalidated current Snowcubes `origin/main@3be131f`.
  Source audit remains `ok: true`; `npm test` is 1,669/1,669;
  `npm run test:storefront` is 1,457/1,457; focused FPA/consignment/cafe
  suites are 314/69/93/127; gitleaks and content secret checks are clean.
  Lockfile-only security repair `83bc74c9` is pushed as PR #1567 and is
  mergeable. `npm audit --omit=dev` is zero and high-severity audit passes;
  only two low Shopify CLI/esbuild findings remain. No live deployment or
  Shopify mutation occurred.
- 2026-08-03T16:07:58Z: Portfolio plan PR #99 is rebased on current public
  main `396ae544` at `1086d2f9`. Remote CodeQL, gitleaks, public-ready,
  browser/docs, Graphite, and Python 3.10/3.12/3.14 checks all pass. The PR
  remains OPEN and unmerged; public main is therefore still the narrow
  platform plan until the external merge step occurs. No merge or release is
  claimed.
- 2026-08-03T16:14:07Z: Rechecked the current Snowcubes remote after new public
  main commits moved the security branch's base. Fast-forwarded PR #1567 with
  current `origin/main@97377b9`, pushed head `8afc5709`, and verified the PR is
  clean/mergeable. On the merged worktree, `npm test` is 207/207 suites and
  1,669/1,669 tests; the 69-test consignment suite, source-truth audit,
  production/high-severity audits, gitleaks, and AI safety checks pass. The
  remaining two low esbuild findings are still confined to the Shopify CLI
  dev chain; forcing `@shopify/cli@4.6.0` would be a breaking change.
- 2026-08-03T16:15:51Z: Pilot Puppy portfolio PR #99 is pushed at
  `af363a82` with the refreshed ledger. Local `npm test` passes 3 JavaScript
  and 86 Python tests, docs build, public-ready scan, and diff check; remote
  Python 3.10/3.12/3.14, CodeQL, browser/docs, gitleaks, public-ready, and
  mergeability checks all pass. The plan is current on the open PR branch but
  is not yet public-main until the external merge occurs.
- 2026-08-03T16:18:36Z: Snowcubes public main advanced again to
  `51ce2487` while the security review was open. Fast-forwarded PR #1567 with
  that current base, pushed head `22c8c590`, and reran the full current-main
  gate: 207/207 Jest suites and 1,669/1,669 tests, 69 consignment tests,
  source-truth `ok: true`, production/high-severity audits clean, and gitleaks
  clean. PR #1567 is clean/mergeable and remains open; no merge or deployment
  is claimed.
- 2026-08-03T16:36:11Z: Rebased the Snowcubes security repair against the latest
  observed public main `de0a0a88`; PR #1567 is now at `016f324e`, remains
  OPEN/CLEAN, and the diff is still lockfile-only. The current security
  worktree passes 208/208 Jest suites and 1,672/1,672 tests, source-truth
  `ok: true`, the 69-test consignment suite, production/high-severity audit,
  and gitleaks. The exact direct-email draft suite passes 26/26; the full Node
  gate passes 1,148/1,148 serially, while the default concurrent run exposed
  one timing-sensitive failure. No production code or send authority changed;
  the next move is to preserve this distinction while continuing the remaining
  portfolio lanes and external merge/readback predicates.
- 2026-08-03T16:40:05Z: Snowcubes public main advanced again to `b8b18e1f` with
  docs and a product-flavor contract update. Merged that current base into the
  lockfile-only security branch and pushed PR #1567 at `ca975aa4`. The rebased
  worktree passes 208/208 Jest suites and 1,672/1,672 tests, production audit
  with zero findings, high-severity audit, gitleaks, and source-truth `ok:
  true`; the full Node serial gate and consignment receipts remain from the
  same dependency state. This is the latest observed boundary; verify PR
  checks/mergeability before claiming it ready to merge.
- 2026-08-03T16:41:44Z: Rechecked the two active control PRs after the latest
  receipts. Snowcubes PR #1567 at `ca975aa4` is based on `b8b18e1f`,
  lockfile-only, and `CLEAN` with mergeability passing. Pilot Puppy PR #99 at
  `976796ff` is `CLEAN`; Python 3.10/3.12/3.14, browser/docs, CodeQL, gitleaks,
  public-ready, and Graphite checks all pass. Neither PR is merged or deployed;
  the next action remains the external merge/readback predicate plus the
  owner-controlled Star67 metadata and Moussey authenticated-runtime gates.
- 2026-08-03T16:46:55Z: Completed the real production Star67 browser readback.
  `https://learn-sql-peach.vercel.app/` opens the branded landing page and
  enters the practice workspace without an account. The local warehouse
  reports 2,930,845 available rows; Riff is the primary guided task, Frosty is
  labeled optional and built-in/private, and running the prefilled query
  returns one read-only row with `transaction_lines = 2,736,642` and the task
  marked delivered. The non-developer launch and hierarchy requirement is
  therefore proven; the remaining Star67 predicate is only the owner-admin
  GitHub rename/homepage/topics update.
- 2026-08-03T16:49:53Z: Reproduced clean Moussey `origin/main@3c44bbec` in an
  isolated production server. Build passed; `/consignment` rendered the
  `PRIVATE OPERATOR SURFACE` passcode gate; unauthenticated
  `/api/consignment` returned HTTP 401 with `operator passcode required`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and no URL
  credential. The owner-owned `:4321` process was not restarted; its visible
  shell still bypasses the current gate and shows `$0.00/all set` cards beside
  open activity and old draft records, so it is explicitly stale proof.
  Resume only with an owner-controlled rebuild/restart and authenticated
  browser readback against `3c44bbec`.
- 2026-08-03T16:54:57Z: Snowcubes public main advanced to `047c0142` with a
  package/test contract update. Merged that exact current base into the
  lockfile-only security branch and pushed PR #1567 at `c9b15faa`. The refreshed
  worktree passes 208/208 Jest suites and 1,672/1,672 tests, production audit
  with zero findings, high-severity audit, gitleaks, source-truth `ok: true`,
  and the full serial Node gate at 1,148/1,148. The default concurrent Node
  invocation remains timing-sensitive; no production authority was weakened.
  Verify the new PR head's mergeability/check state before calling the security
  repair ready to merge.
- 2026-08-03T16:56:48Z: Final readback passed after the Snowcubes rebase.
  PR #1567 is OPEN/CLEAN at `c9b15faa` on base `047c0142` with mergeability
  passing. Pilot Puppy PR #99 is OPEN/CLEAN at `a2c3be39`; Python 3.10/3.12/3.14,
  browser/docs, CodeQL, gitleaks, public-ready, and Graphite checks all pass.
  Neither PR is merged or deployed. The portfolio proof is current through
  this observed boundary; remaining predicates are the external merges, Star67
  admin metadata, and owner-controlled Moussey authenticated-runtime proof.
- 2026-08-03T15:54:45Z: Re-read the public Star67 repository metadata. The
  description is branded, but homepage is unset and `star67` is absent from
  topics. GitHub returned HTTP 404 for both the rename/settings PATCH and the
  topics replacement with the current account; `gh api` reports `WRITE` and
  `admin: false`. No metadata mutation is claimed. Resume with owner/admin
  access, then set the repository name, homepage, and topics and read them back.
- 2026-08-03: Tightened the Operator Brief's `Next` field to the 280-character
  contract so `pilot-puppy status` and the loopback browser render the current
  Outcome again. No routing or execution behavior changed.
- 2026-08-03: R5 is complete. `seat init`, `seat set`, and `seat show` maintain
  a strict owner-local selector overlay for an existing enabled roster slot;
  `host run --use-seat` requires a sealed route and fails before host launch if
  the mapping is absent, stale, unsafe, or mismatched. The selected model or
  Codex profile enters only the native argv and is rejected from receipts.
  Generic roles, routes, browser/status, plans, package contents, and stranger
  installs remain selector-free. The full gate passed: 136 Python tests, 3
  JavaScript tests, 6 desktop/phone browser tests, docs build, the 98-file
  public-source scan, and a reproducible 63-file package with SHA-256
  `f372fd76c0d93b9d72baf9cb90d4319121ab1a3a2a0bd90772e55b2257c0153f`.
- 2026-08-03: The generic roster alone cannot express the requested named local
  seats. Installed Codex, Claude Code, and Cursor-native CLIs each expose a
  model-selection flag, so R5 now implements a local-only, route-bound model
  overlay rather than a cloud router or cost dashboard. It will accept no
  arbitrary native arguments, credentials, profiles, account discovery, quota
  checks, or provider calls; a bad or unsupported local choice must fail before
  a host starts. The exact private selector must not appear in a browser,
  `status`, plan, route packet, or host attempt receipt.
- 2026-08-03: R8 passed the integrated public gate: 126 Python tests, 3
  JavaScript tests, 6 desktop/phone browser tests, docs build, the 95-file
  public-source scan, package verification, and a zero-vulnerability
  dependency audit. It adds no host launch, provider/model/usage selection,
  cloud execution, credential relay, queue, daemon, watcher, or transcript
  store. This is source proof only; it does not claim a new public release or
  a native-host execution.
- 2026-08-03: Restored the live local delegation surface to public main
  `bc2e06c0` without copying or adding a runtime. Skillbox read back one
  current Pilot Puppy source in Codex, Claude Code, and Cursor; `pilot-puppy`
  reported 2.1.0 and its doctor passed 11/11. A fresh private generic roster
  exposes routine development as bulk/Cursor with bulk/Codex fallback,
  debug/Codex, and hard implementation/Claude Code. A no-launch `dev` route
  read back that exact Cursor-first selection. R8 adds a visible four-shape
  guide and an atomic `roster prefer` command. Specific native model/profile
  selection remains deferred until a
  real same-host need and safe invocation contract exist.
- 2026-08-03: User made local role-based smart routing and a usable roster P0.
  Pilot Puppy will not add cloud execution, voice/on-the-go controls, a
  credential relay, a transcript store, or autonomous dispatch. The direct
  work starts with a secure generic roster, followed immediately by a
  transparent role route that saves stronger native seats for work that needs
  them.
- 2026-08-03: R1–R4 are implemented in the local delegation slice. `roster`
  stores only generic local roles/hosts; `route` selects one role/host from an
  explicit task kind, prints alternatives and escalation, and does not launch.
  `host run --route-file` validates the frozen task, route-safe roster hash,
  declared enabled slot, and selected host before launch. This works in an
  ordinary clean Git repository without adding an ignore rule, while preserving
  the bounded evidence directory. No cloud executor, credential relay,
  transcript store, queue, daemon, watcher, voice client, or provider-model
  router was added.
- 2026-08-03: Independent hostile-input coverage now rejects named pipes,
  group/world-readable local rosters, private slot-ID hash leakage, malformed
  or stale packets, undeclared selections, route/output collisions, and cross-
  host substitution. Full Python, JS, docs, package, public-source, and
  desktop/phone loopback gates are the remaining R7 proof fold.
- 2026-08-03: Made the local-first boundary operational. The unavailable Jump
  route is deferred, while the Outcome now offers three honest local choices:
  dogfood here, take the next reachable product row, or defer cross-host proof.
- 2026-08-02: Established one product authority. Outcome, briefing, decision,
  privacy, and native-host behavior stay; unrelated machinery is removed.
- 2026-08-02: Public core gate passes 79 Python tests, 3 JavaScript tests,
  4 desktop/phone browser tests, docs build, privacy fixtures, and a reproducible
  51-file stranger install. Real host, restart, cross-repository, and remote
  release proof remain open.
- 2026-08-03: Public main `6bd03c3f` passes 79 Python, 3 JavaScript, and
  4 Chromium tests, the 81-file public-ready scan, docs build, zero-vulnerability
  install, and a 51-file release package with SHA-256
  `9827381f6570dac1bf5e66611fae4056e18f3a14c6a914d85a099e5d5643b8cb`.
- 2026-08-03: `pilot-puppy doctor` passes 11/11 with one command and the same
  Pilot Puppy skill mounted in native Claude Code, Codex, and Cursor roots.
  Every predecessor command fails lookup; shared main is `c9efb7fe` and private
  main is `958a6163` after caller and runtime removal.
- 2026-08-03: Real sealed Claude Code and Cursor tasks changed only their exact
  allowed file and passed lead-reproduced checks. The real Codex CLI changed
  nothing and failed because its account usage limit resets after
  2026-08-07 23:52 America/New_York.
- 2026-08-03: A real mobile Chromium brief retained the identical
  `a4bf32b072f933ea2d89535097c3dc157a4c02ef3f2bb4ceec9d821d531f0f3f`
  API hash across a full server stop/restart and rendered the same Outcome and
  A/B/C choices.
- 2026-08-03: The final read-only Fable cold-review attempt returned no review
  payload after 12 internal turns and ended `aborted_streaming`; it is recorded
  as an unavailable sidecar, not approval. The lead Thermo audit found no
  duplicate authority, state store, runtime, compatibility surface, or release
  blocker. A stale unrelated health watcher was retargeted to neutral local
  state, stale Claude cleanup hooks were removed, and the retired state root
  was absent after final configuration validation.
- 2026-08-03: PR #88 merged as `6375c84a`; public release `v2.0.0` points to
  that exact commit and is the only visible release. Its attached 51-file
  package has SHA-256
  `9827381f6570dac1bf5e66611fae4056e18f3a14c6a914d85a099e5d5643b8cb`.
  A fresh public tag clone passed a zero-vulnerability install, 3 JavaScript
  tests, 79 Python tests, the 81-file public-ready scan, docs build, stranger
  package install, version readback, and a real new-repository A/B/C brief.
- 2026-08-03: PR #90 merged as `0c6d8ce1`. Its docs-only handoff makes the
  second-computer route the first unblock attempt for the remaining Codex
  execution proof. No new runtime, queue, autonomous router, credential relay,
  or second plan authority is needed.
- 2026-08-03: The read-only Jump Desktop attempt to the other-computer route
  returned `Computer is offline`; no remote UI, install, doctor, skill mount,
  or native-host receipt was produced. This is host availability, not a Pilot
  Puppy code failure.
- 2026-08-03: A fresh public clone at `83a95d3b` passed `npm ci`, rendered a
  working `pilot-puppy status`, and passed the 82-file public-ready scan.
  Its doctor was 8/11 because this computer's existing native skill mounts
  still resolved to the primary checkout; the documented mount commands are
  required on the target computer. This is an environment-boundary receipt,
  not a source defect.
- 2026-08-03: Made the worklane boundary explicit: Pilot Puppy is optional
  support for a project's own plan, not a universal validation gate. One
  bounded task keeps a handoff reviewable; it does not stop other projects
  from shipping safe, high-value reachable work.
- 2026-08-03: PR #98 merged as `a24120ff`. Post-merge `origin/main` readback
  passes 83 Python tests, 3 JavaScript tests, public-ready, docs, desktop and
  phone browser, and release-package verification. This proves merged source
  and CI behavior only; no new release or deployment was performed.
- 2026-08-03: The local Python-floor receipt now records five resolution tests,
  including hermetic override and low-bare-python fallback coverage; the
  84-test Python suite, public scan, docs, package, and browser gates pass
  without claiming remote host readiness.
- 2026-08-03: Configuration behavior now matches the public reference: `status`
  honors `PILOT_PUPPY_DEV_ROOT`, the browser honors `PILOT_PUPPY_DEV_ROOT`,
  `PILOT_PUPPY_BROWSER_HOST`, and `PILOT_PUPPY_BROWSER_PORT`, and explicit flags
  win over environment defaults. Two hermetic tests cover the status path and
  parser precedence; full gates remain the resume proof for this row.
- 2026-08-03: Architecture review restored the useful delegation policy that
  earlier consolidation removed: a provider-neutral role roster, foreground
  selection, bounded packets, lead-owned acceptance, and evidence-boundary
  escalation. The public product will not restore a hidden queue, autonomous
  router, daemon, credential relay, transcript store, or private provider
  roster.
- 2026-08-03: The completed R1–R4 implementation passes 120 Python tests, 3
  JS tests, 4 desktop/phone Chromium tests, docs build, public-source scan,
  and a 61-file clean development package with zero dependency vulnerabilities.
  The only active row is R7: commit/push/remote review and release-readback;
  no provider host or cloud executor ran for this local routing work.
- 2026-08-03: A final independent hostile-input review found no release blocker.
  It re-ran 44 focused routing/host tests and the 120-test Python suite. The
  release candidate rejects FIFO inputs, stale or forged packets, undeclared
  slots, route/output collisions, private roster permissions, and host
  substitution before launch. Remote merge, tag, and release readback remain
  the only R7 actions.
- 2026-08-03: R7 delivered. PR #107 merged as c7d63619; public release v2.1.0
  targets that exact commit with a 61-file asset whose SHA-256 is
  ecdc1509261b2eefc1d92074783cbc28f7be4ef1ac3bf0766326c9e22dd98634.
  Hosted Python 3.10/3.12/3.14, browser/docs, gitleaks, public-readiness,
  CodeQL, and mergeability checks passed. A fresh v2.1.0 tag clone installed
  with zero vulnerabilities, read back version 2.1.0, passed 3 JavaScript and
  120 Python tests, and passed the 95-file public-source scan.
- 2026-08-03: R6 delivered. A focused no-launch regression now proves the
  default planner/manual, bulk/Cursor, debug/Codex, and hard-IC/Claude Code
  decisions. One fresh real bulk/Cursor dogfood followed its sealed route,
  changed only its allowed file, returned `status: ok`, passed its verifier,
  and passed lead reproduction in 29.5 seconds. The host receipt explicitly
  records `projection_is_usage: false`; no token, cost, quota, model, or
  provider-performance claim is made. A literal valid receipt example fixed
  the one malformed-proof-label block found in the first fresh attempt. The
  raw route and attempt receipt stay local because they are task- and
  worktree-specific; this public record preserves only the safe mechanical
  facts above.
- 2026-08-03T22:57Z: Rechecked the documented other-computer route. Jump
  Desktop opened `Leos-Macbook-M4-Pro` but remained on `Connecting...` for
  about 15 seconds; the attempt was closed without reaching the remote UI.
  No clone, install, doctor, mount, or native-host receipt was produced. The
  target-host availability predicate is still unmet; do not retry in a loop.
- 2026-08-03T23:03Z: Made one bounded follow-up attempt after a fresh Jump
  state check. `Leos-Macbook-M4-Pro` remained at `Connecting...` for another
  15 seconds and was closed without reaching the remote UI. No clone,
  install, doctor, mount, Outcome/A/B/C, or native-host receipt was produced.
  The target-host availability predicate remains unmet; do not retry again in
  this run.
- 2026-08-03T23:33:34Z: Made one fresh low-cost reachability check after the
  pause. `Leos-Macbook-M4-Pro.local` resolved to `192.168.4.29`, but the
  bounded ICMP probe received no replies and read-only SSH timed out after
  five seconds. No clone, install, doctor, mount, Outcome/A/B/C, or
  native-host receipt was produced. The target-host availability predicate
  remains unmet; do not open another Jump or retry in a loop.
- 2026-08-03T23:38:52Z: Restored the public-safe frozen packet metadata from
  the repository's prior packet receipt after auditing the current plan. This
  preserves the exact task ID, target revision, hash, allowed path, and proof
  command without copying the packet file or any private task content. It is
  packet readiness only; no target-host or native-host receipt is claimed.

- 2026-08-04T05:21:53Z: Advanced the reachable StrongYes security lane through
  merged PR #1469 at public `main@eb48309`. The isolated lockfile-only repair
  was reproduced with clean `npm ci`, `npm run typecheck`, focused analytics
  tests 36/36, and `npm run build`; production audit moved from 20 findings
  (5 high) to 16 (3 high, 0 critical). The remaining three high findings still
  require the separately tested Next/AI/OpenTelemetry major migrations, whose
  current Next 16.3.0 path fails typecheck, `next lint`, and build. No owner
  dirty checkout, deployment, customer data, or production runtime was
  changed; this is a safe dependency improvement with an explicit migration
  predicate remaining.

- 2026-08-04T05:25:29Z: Published the StrongYes receipt and portfolio-wide
  authority correction through Pilot Puppy PR #130, merged at `main@7f697d1`.
  The public plan is now revision 120 and explicitly records that the
  umbrella Outcome contains many active workstreams; the bounded-packet rule
  is execution scope only, not a one-deliverable limit. Required analysis,
  CodeQL, browser/docs, gitleaks, public-ready, and Python test checks passed.
  The remaining admin, authenticated-runtime, official-scan, host-resource,
  consumer/device, agentic-discovery, framework-migration, and Resplit gates
  stay open with their existing owner or mechanical predicates.

- 2026-08-04T05:33:05Z: Advanced the reachable StrongYes security and
  observability lane through PR #1455 (`5a2cec3`) and PR #1458 (`1f444be`),
  both merged to public main. PR #1455 gives signal-specific OTLP headers
  precedence over the generic/Grafana fallback so a separate collector cannot
  receive the Grafana access-policy credential; PR #1458 flushes buffered error
  logs even when the emit call throws. The lead reproduced the two PR heads and
  current public main `1f444be` with 69/69 focused observability tests, clean
  typecheck, and diff check. No deployment, credential value, customer data, or
  production runtime mutation was performed; live Grafana deliberate-error
  correlation remains the exact next external proof.

- 2026-08-04T05:09:39Z: Revalidated the next reachable Snowcubes lane after
  the public repository advanced. Current public `main@560ff497` includes
  merged security PR #1567 at `7fd0a06`; `npm audit --package-lock-only
  --omit=dev` reports 0 vulnerabilities, and `audit-consignment-source-truth.py`
  passes with Zack `$0.00`, Marathon `$0.00`, Everyman `$22.00`, and the
  2026-05-21 Marathon row explicitly FREE/UNKNOWN with no charge or payment
  row. The live POST `/api/ucp/mcp` still returns HTTP 422
  `invalid_profile_url`, while `agents.md`, `llms.txt`, and `/.well-known/ucp`
  advertise capabilities beyond that proven endpoint. This is now an explicit
  Shopify/Worker/agentic-discovery owner-deploy predicate; no storefront,
  Shopify, payment, ledger, or production-runtime mutation occurred.

- 2026-08-04T05:05:18Z: Continued the umbrella outcome through the reachable
  StrongYes security/dependency lane. In a fresh isolated clone of public
  `main@c02f052`, `npm ci` and `npm run typecheck` passed; the current
  production-only audit reports 20 findings (5 high, 0 critical). The safe
  non-forced `npm audit fix --omit=dev` path was also tested in isolation but
  leaves the direct Next finding. A complete Next 16.3.0 / ESLint 9 migration
  install lowers production findings to 18 (3 high, 0 critical), but fails
  the existing typecheck on async `headers()`/`cookies()` APIs, the existing
  `next lint` script, and the Turbopack build on the dynamic `@strongyes/problems`
  package path. No StrongYes source or lockfile was changed in the owner dirty
  checkout; the migration is an explicit owner-controlled dependency predicate,
  not a speculative security fix. The full portfolio outcome remains working
  and moves to the next reachable lane.

- 2026-08-04T16:29:20Z: The chief-of-staff surface now names the required operator sequence directly: Outcome, Now, Change, Proof, and A/B/C decision. The existing local role/host, sealed packet, privacy, and lead-acceptance contracts are unchanged.
- 2026-08-09T04:34:39Z THROWN ~audt repo audited for 0.1.0 readiness by three named agents on disjoint surfaces; every must-fix either fixed or written as a row | note: three named agents, disjoint surfaces: stranger-install at 0.1.0 / version-pin sweep / vestigial-prose sweep

- 2026-08-09T04:43:11Z ~vrst PROOF scripts/shadow-python.sh scripts/shadow-release-package.py --expect-version 0.1.0 --allow-dirty -> pass (accept)
- 2026-08-09T00:00:00Z ~dslp PROOF 435 lines of v3 Outcome block, portfolio readback, and the three platform sections moved to docs/plan-archive/2026-08-04-v3-outcome-receipts.md (839 lines, 54 "Pilot Puppy" mentions preserved). Two live law lines in ## Worklane boundary corrected to Shadow. The 59 mentions remaining in PLAN.md are: the rename note (line 3), this milestone's own row text, and dated receipts in ## Progress and one completed R11 row whose `.pilot-puppy/` is the literal directory name of that era. Two gates learned the archive is receipts: the brand check exempts docs/plan-archive/ (secret and private-path checks still apply to it), and test_documented_targets stops requiring that deliberately-removed paths exist. (read)
- 2026-08-09T00:05:00Z LESSON a fan-out that leaves no plan row is unrecoverable, whichever mechanism spawns it. The 0.1.0 repo audit ran as a sealed workflow with no row, and when a mid-flight snapshot showed 0 results I called it dead in this plan -- wrongly; it was still running and finished 22 minutes later with 4 of 4 agents and 7 file:line findings. A row would have carried the dispatch, the expected return, and the recovery move, so no snapshot could have been mistaken for a death certificate. Workflows are not banned: they stay opt-in for barrier and multi-model work. What is banned is dispatching without the row. | trigger: my own wrong "died with no live process" entry, written and then deleted from ## Deferred in the same session
- 2026-08-09T00:10:00Z ~vrst PROOF release verifier on the git artifact -> OK (0.1.0, 81 files, sha256=52fbf61b...); flipped by `shadow accept`, which reran the proof in a detached clean checkout (cmd)
- 2026-08-09T00:15:00Z PROOF `shadow goal` ships the static standing goal and it is now pasted into ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md; `shadow doctor` -> 13/13 checks, 0 warnings, "standing goal: claude: current" and "standing goal: codex: current". Before this the adoption was 0 of 3 hosts and no executable could tell. (read)
- 2026-08-09T00:20:00Z PROOF amp no longer lets a plan rewrite the rails of the block it feeds: Priority/Loop/Mode go through _clean, so a newline cannot append an instruction line and a 3,000-char value cannot evict RAILS from a 4k block. 4 tests, both halves mutation-tested (removing the bound and letting the fixed authority pointer win the size comparison each turn the class red). Full suite 240 tests OK, up from 224. (cmd)

- 2026-08-09T00:25:00Z ~fout PROOF the ruling is that nothing new gets built: workflows stay opt-in for barrier and multi-model work, named agents are the default for supervisable work, and the chief's own dispatches obey row-first like every other seat's. Three clauses added to AGENT.md Row-first dispatch (a "conversation" is any work you stop watching; prefer the supervisable mechanism; a mid-flight reading is not a death certificate) and one to grammar.md Dispatch law. grammar.md already said "Liveness is never asserted -- probe the proof, never a process", which is precisely the law I broke -- the gap was never the text, it was that the text did not obviously cover a mechanism I did not think of as a conversation. (read)

- 2026-08-09T00:30:00Z LESSON `shadow accept` runs a cmd proof through shlex.split with NO shell, so a proof containing `&&`, `$(...)`, or a redirect is not a compound command -- the operators arrive as literal arguments to the first binary. This milestone's own DoD proof was written as `bash install.sh ... && shadow --version` and could never have passed: install.sh would have received `&&` as an unknown argument. It was also a false green by construction, since printing a version asserts nothing about it. Rewritten as one `bash -c '...'` token that clones origin/main, installs, and hard-asserts `test "$v" = 0.1.0` plus a doctor run. Verified failing today against main at 4.1.0 (rc=1, "installed 4.1.0"), which is what makes it a gate rather than a printout: a proof that cannot fail before the work is done is not proof. | trigger: reading shadow-accept.py:157 while checking whether my own DoD row was runnable

- 2026-08-09T00:35:00Z ~m3k7 PROOF re-observed: AGENT.md carries ## The core, ## Folded behavior -- one sentence each, ## The proxy stance, ## Appendix. Its npm-era proof `npm run docs:build` retired with npm on 2026-08-09; this row's class changed cmd -> read because the docs build no longer exists and the claim was always about file content. (read)
- 2026-08-09T00:36:00Z ~q8f2 PROOF scripts/shadow-python.sh -m unittest tests.test_grammar_contract -> Ran 6 tests, OK. Replaces the retired `npm run test:py`; same contract, existing runner. (cmd)
- 2026-08-09T00:37:00Z ~t2b8 PROOF scripts/shadow-python.sh -m unittest tests.test_status_focus -> Ran 20 tests, OK. Replaces the retired `npm run test:py`. (cmd)
- 2026-08-09T00:38:00Z ~j6n4 PROOF scripts/shadow-python.sh -m unittest tests.test_browser_shell -> Ran 7 tests, OK. Replaces `npm run test:e2e`, whose playwright board suite was deleted with npm; test_browser_shell ports its four source-contract assertions verbatim. (cmd)
- 2026-08-09T00:40:00Z STRUCT lint gained COMPLETED-NO-PROOF (blocking): a [completed] row must name a "<ts> <id> PROOF ..." line in ## Progress. Why now: a 5-agent 0.1.0 audit proved the product's central claim false -- in a fresh `shadow init` tree a row hand-flipped to [completed] with zero PROOF lines linted "clean" rc=0, and status then said "every task complete; mint the successor". AGENT.md:4, grammar.md:5 and :58, and README property 3 all named lint as that enforcer; lint checked shape, never truth. Contradicts: nothing -- it makes four documents honest. It immediately caught four of this plan's own rows whose npm-era proof commands died with npm; each was re-pointed at a command that exists and re-run today rather than given a fabricated receipt. One test fixture faked completion by string-replacing states without adding proofs, the same shortcut a careless operator takes; it now carries receipts.

- 2026-08-09T00:50:00Z ~audt PROOF the 0.1.0 audit returned 11 must-fix findings. Fixed: lint not enforcing no-proof-no-completed (the flagship claim, mutation-proven false), throw pushing to the wrong ref, accept skipping the needs gate, the release gate blessing a package with amp and throw deleted, CONTRIBUTING's four npm commands and its dead docs/doctrine link, plugin.json advertising deleted role routing, commands.md omitting three verbs, `shadow help throw` printing "unknown command", and every unquoted ~hash example. Held open: `shadow init` scaffolding 19 Brief keys against a 4-key grammar (Contradiction -- its only consumer is the browser's A/B/C surface) and the ~1,746-line v3 Outcome subsystem with no live producer (Deferred -- owner call). 243 tests, lint clean, artifact verifies at 0.1.0. The audit was the workflow I twice declared dead; it was running both times. (read)
- 2026-08-09T05:04:48Z THROWN ~rsch the five open design questions are answered from evidence, not preference: how a tool safely owns a block in someone's CLAUDE.md, what Cursor's real user-rule surface is, where plans actually live on this machine, how an optional method pack is declared a dependency, and what Langfuse puts on the wire | note: five named agents: host-directive injection, Cursor surface, plan locations on this machine, dependency declaration, Langfuse wire shape

- 2026-08-09T01:20:00Z EVIDENCE cross-runtime coordination held in the wild, unprompted and with no router. A separate Claude session and a Codex seat were given the same Snowcubes goal; the Claude seat read the named authority branch FIRST, checked what Codex had already done before claiming anything, found Codex owned gift-box-customizer-modal.js, and took a provably disjoint lane ("read-only and touches no file it has open"). That is the own-row guard and disjoint-surface rule operating across two different runtimes on one goal, with a repo-local plan as the only shared state. It is evidence FOR the current architecture and it re-scopes M9: the coordination layer is not what is missing -- wiring and verification are. It does NOT yet demonstrate `shadow throw` claiming or crash recovery, which is what M7 ~live still gates on. Owner, seeing it: "looks like the system kinda already works so its not a bad base".

- 2026-08-09T01:30:00Z PROOF the standing goal gained `Dispatch:` (nothing leaves the chat unclaimed; a mid-flight reading is not a death certificate) -- the one law this session broke twice and the block did not carry. Changing it made `shadow doctor` report [FAIL] stale copy on BOTH wired hosts within one command, which is the drift detection working on its first real change rather than on a test fixture. Refreshing them then exposed the next gap: doctor says "refresh with: shadow goal", but `shadow goal` only PRINTS -- appending it a second time duplicates the block, so the advice is not followable and the refresh had to be a hand-written find-and-replace with backups. That upgrades M9 ~host from convenience to required: doctor already gives an instruction only a managed, marker-delimited block can satisfy. 19 lines now; the clause-coverage test asserts both new phrases. (read)

- 2026-08-09T05:16:41Z ~land PROOF bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; bash "$d/s/install.sh" --bin-dir "$d/bin" --no-skills >/dev/null; test "$("$d/bin/shadow" --version)" = 0.1.0; if HOME="$d/home" "$d/bin/shadow" doctor > "$d/out"; then :; fi; grep -q "^\[PASS\] python:" "$d/out"; grep -q "^\[PASS\] git:" "$d/out"; grep -qx "\[PASS\] product identity: shadow 0.1.0" "$d/out"' -> pass (accept)
## Contradictions

- Langfuse is an off-box service; Shadow's Boundaries ban a transcript store |
  provisional winner: Boundaries | opened 2026-08-09T01:10:00Z
  `AGENT.md` and `SKILL.md` both say no router, daemon, scheduler, credential
  relay, or transcript store, and `docs/reference/privacy.md` is built on
  nothing leaving the machine. End-to-end triage of a failed cycle is a real
  need and there is no local answer today, but the default Langfuse shape --
  hosted endpoint, API keys, prompt and output payloads -- is precisely the
  banned thing. ~obsv decides between: self-hosted only, metadata-only spans
  with no payloads, or kill. Recorded before any code so the boundary is not
  eroded by an integration that arrives working.

- `shadow init` scaffolds 19 Brief keys; the grammar defines 4 | provisional
  winner: keep the scaffold | opened 2026-08-09T01:00:00Z
  The first command a stranger runs teaches `Outcome ID / Revision / State /
  Decision / Option A|B|C` — vocabulary `docs/reference/grammar.md` does not
  contain (`grep -ic outcome` on it returns 0), and lint has no unknown-key
  check so the scaffold passes forever. Cutting it to the four real keys is a
  10-line change, EXCEPT the browser's A/B/C decision surface reads exactly
  those extra keys, so trimming init leaves `browser/outcome_source.py`,
  `decision_mode.py`, and `chief_of_staff.py` with no producer. Resolving this
  means deciding whether the browser's decision surface stays — an owner call,
  not a lint fix. Held as a contradiction rather than settled quietly.

## Deferred proof (not a global blocker)

- The v3 Outcome/Decision/chief-of-staff subsystem is ~1,746 lines with no live
  producer: pointed at Shadow's own plan the board returns `"outcome": null,
  "briefing": null, "decision": null`. Breakdown measured 2026-08-09:
  `browser/outcome_source.py` 189 + `browser/decision_mode.py` 190 +
  `browser/chief_of_staff.py` 156 + ~96 lines of `browser/server.py` +
  `scripts/shadow-outcome-validate.py` 263 (unreachable — no dispatch case in
  `bin/shadow`) + `schemas/*.json` 297 (nothing imports them) + `examples/` 65
  + 2 reference docs + 462 lines of pinning tests. Retiring it also retires
  the A/B/C sentences in `quickstart.md` and `docs/index.md` and two committed
  screenshots. The remaining ~1,200-line read-only board is coherent and serves
  200s. Owner call; do not cut it as cleanup.
- `docs/superpowers/` (132K, 15 files) is linked from no index and prescribes
  deleted machinery — `shadow route` and `npm install --package-lock-only`. If
  kept, move it under `docs/plan-archive/` so a stranger does not read internal
  design debate as documentation.

- Cursor user rules live in application settings, not a file, so `shadow
  doctor` can only verify the standing goal in `~/.claude/CLAUDE.md` and
  `~/.codex/AGENTS.md`. Asserting `~/.cursor/rules/shadow.md` would invent a
  convention. Resume when the owner names the real Cursor surface; until then
  Cursor is pasted by hand and unverified.

- The Star67 repository settings are owner-admin bound. GitHub reports
  `nlau1193/pivot-sql` with the current account at `WRITE` and returned HTTP
  404 for the rename/settings PATCH and topics replacement because the account
  is not repository admin. Resume when an owner/admin renames it to
  `star67-learn-sql`, sets homepage to `https://learn-sql-peach.vercel.app/`,
  adds the `star67` topic, and reads all three back. No product work waits on
  this.
- Moussey's clean `origin/main@3c44bbec` build and money/UI/security tests are
  green, and an isolated server proves the current private passcode gate plus
  safe unauthenticated 401. The existing `:4321` process belongs to a dirty
  primary checkout, visibly bypasses that current gate, and was not restarted
  or overwritten. Resume with an owner-controlled rebuild/restart and an
  authenticated `/consignment` browser readback against `3c44bbec`; do not
  treat either the stale process or the isolated unauthenticated shell as
  current customer proof.
- Snowcubes security repair PR #1567 merged at `7fd0a06` and is included in
  current public main `560ff497`; the production package-lock audit is 0
  vulnerabilities and the current source audit passes. The remaining resume
  predicate is the live agentic-discovery owner alignment: POST
  `/api/ucp/mcp` returns `invalid_profile_url` while the public capability
  documents advertise cart/checkout/payment/order/fulfillment tools. Do not
  patch the storefront to mask an existing Shopify/Worker owner-deploy issue.
- StrongYes PR #1469 (`eb48309`), PR #1455 (`5a2cec3`), and PR #1458
  (`1f444be`) are included in current public main. The safe lockfile repair is
  proven by clean install, typecheck, focused analytics tests, and build;
  production audit is now 16 findings with 3 high and 0 critical. The two
  observability repairs are re-proven on current main by 69/69 focused tests,
  typecheck, and diff check. Resume the remaining high findings only through an
  owner-controlled Next/AI/OpenTelemetry major migration after its async API,
  lint, build, and runtime contracts are separately repaired and proven. The
  separate live Grafana deliberate-error correlation is still unproven. Do not
  force that migration or claim live telemetry from this umbrella lane.
- Pilot Puppy portfolio receipt PR #133 is merged at `839512e`; its required
  CI, browser/docs, CodeQL, gitleaks, public-ready, Graphite, and Python checks
  passed, and the public plan reads revision 123. `[code]smith` is skipped by
  policy when it skips; the readback is complete for this receipt. Continue
  using the same single `PLAN.md` authority for the next portfolio lane.
- The other-computer route is deferred by host availability. Resume only when
  the target Mac is online and Jump Connect accepts the connection; then run
  the documented clone, install, doctor, skill-mount, and Outcome/A/B/C path.
- The public clone/install/status path is proven locally; the three mount
  failures are intentionally not counted as second-computer proof because the
  target host was offline. Do not call that receipt complete until its doctor
  is 11/11 from the target checkout.
- The frozen packet is ready and must not be replaced: use task ID
  `host-prompt-heading-guard` at target revision
  `b1f5d0a6fefed6d4b3bb278ae1584ff133feec1b`, exact allowed path
  `tests/test_pilot_puppy_host.py`, and proof command
  `python3 -m unittest tests.test_pilot_puppy_host -v`; verify its SHA-256
  as `fc04e1b8730808dbf2bceb30090d049305af1a04db34bd1d3f50f3781be294cd`.
- Native Codex execution is also time-bound. If the target has a usable
  account, run the same sealed task there; otherwise resume after 2026-08-07
  23:52 America/New_York. In either route, it must return `status: ok`, change
  only its allowed path, and pass the lead-reproduced check. A binary/version
  probe does not satisfy this deferred receipt.
- 2026-08-04T06:08:51Z: Fresh target-host recheck found
  `Leos-Macbook-M4-Pro.local` online at the network layer: one bounded ICMP
  probe replied in 15.351 ms. Read-only TCP/22 checks were refused or timed
  out, so no SSH shell was available. One documented Jump Desktop attempt
  opened the target window but remained `Connecting...` for 15 seconds and
  was closed. No clone, install, `pilot-puppy doctor`, skill mount,
  Outcome/A/B/C readback, or native-host receipt was produced. This is a
  fresh reachability receipt only, not cross-computer proof. Keep the target
  handoff WAITING until Jump Connect reaches a usable desktop or an authorized
  remote shell is available; do not retry in a loop.
- 2026-08-04T15:51:07Z: Advanced the reachable Star67 public-presentation lane
  directly. Commit `edd0055b` on
  `codex/nicole-readme-human-prose-20260804` keeps the Vercel launch link first,
  adds the tracked landing/practice-desk screenshots, clarifies the browser
  warehouse, and removes contributor-only install/test commands from the
  non-developer front door. Asset existence and `git diff --check` pass. PR #5
  is open with two GitHub build checks in progress; repository rename/homepage
  metadata remains owner-admin bound and is not claimed.
- 2026-08-04T16:00:58Z: Fresh cross-lane readback kept the money and runtime
  receipts current. Snowcubes remote `main@5f655431` still contains Marathon's
  2026-05-21 FREE/UNKNOWN nine-pack row with `$0.00` open and no payment row;
  the new head is docs-only. Moussey remote `main@40a487c` adds the shoppy
  pouch guide but its consignment source still uses the simplified
  `awaiting payment` / `No payment due` language and its URL sanitizers still
  clear username, password, and credential query parameters. The dirty local
  Moussey runtime remains untouched; authenticated UI proof is still
  owner-controlled. Star67 PR #5 is open at `d9bbf97` with both build checks
  still running. No duplicate data, UI, or security patch was created.
- 2026-08-04T16:03:39Z: Tightened Star67's non-developer front door in commit
  `a3d288c`. README is now 16 lines / 74 words, puts the browser launch link
  first, keeps the two useful screenshots and local-first privacy statement,
  and removes all install, clone, Node, npm, and contributor instructions.
  `git diff --check` and a four-commit gitleaks diff scan pass with zero
  findings. PR #5 restarted its two build checks at this head; no Vercel
  deployment claim or GitHub admin metadata claim was made.
- 2026-08-04T16:05:18Z: Fresh Star67 readback found commit `d3f418f` had
  reintroduced the local Node/clone/`./start` section after the browser-only
  trim. That contradicted the explicit non-developer GitHub front-door goal,
  so commit `39484c9` reverses only that documentation addition and restores
  the verified 16-line / 74-word browser-only README. `git diff --check` and
  the no-install/no-clone/no-npm assertion pass; the PR remains open and its
  current-head CI is the next proof gate.
- 2026-08-04T16:06:18Z: Fresh remote-head readback supersedes older ref
  snapshots. Snowcubes is now `main@f46f6ad` after the independent featured-
  ingredient label-escaping fix; its consignment ledger and current summary
  still contain the verified Marathon 2026-05-21 FREE/UNKNOWN row with no
  payment row. Moussey remains `main@40a487c` with the simplified consignment
  copy and credential-free URL helpers. Star67 PR #5 is clean at `39484c9`
  with the browser-only README; both current build checks remain in progress.
  No stale ref was used as current proof.
- 2026-08-04T16:07:25Z: The same conflicting Star67 README addition appeared
  again as `add3042`, reintroducing Node/clone/`./start` instructions. The
  explicit non-developer front-door requirement remains the controlling
  product decision, so `abf56d6` removes only that addition and restores the
  16-line / 74-word browser-only README. The branch is clean and pushed; PR
  #5 checks restarted from this head. This conflict is recorded so a future
  agent does not mistake the repeated local-start commit for accepted scope.
- 2026-08-04T15:56:33Z: Re-ran the reachable Star67 security lane on the
  browser-first branch. `npm audit --omit=optional --json` reports zero
  vulnerabilities; gitleaks reports zero findings in the README diff and one
  documented false positive in `src/Workspace.tsx:87` for the compatibility
  storage key `pivot.navigatorWidth.v1`; the static sink and sensitive-file
  sweeps found no production match or tracked credential file. The live
  Vercel URL returned HTTP 200 with the Star67 title and expected hardening
  headers. `SECURITY.md` now records the bounded result and keeps the Codex
  Security AI scan explicitly incomplete rather than claiming coverage. The
  product PR is now head `057e90b`; owner-admin repository rename metadata is
  still the only Star67 delivery blocker. This is product security evidence,
  not a Pilot Puppy test objective.
- 2026-08-04T15:59:16Z: Removed the remaining public-facing `pivot` asset name
  from Star67. Commit `d9bbf97` renames the tracked screenshot to
  `docs/star67-practice-desk.png` and updates the README and quality-audit
  links; internal browser-storage and compatibility IDs were intentionally
  preserved. GitHub readback still shows `nlau1193/pivot-sql`, empty homepage,
  no `star67` topic, `WRITE` permission, and `viewerCanAdminister=false`; no
  unauthorized metadata mutation was attempted. PR #5 restarted CI at this
  head and remains open.
- 2026-08-04T16:09:21Z: Snowcubes advanced independently to
  `main@c68223e`, adding a guarded stories visual-smoke harness; the current
  consignment ledger and summary still prove Marathon 2026-05-21 as
  FREE/UNKNOWN with no payment row. Star67 remains clean at `abf56d6` with the
  browser-only README; PR #5's two current build jobs are still in
  `npm run build`. Moussey remains `main@40a487c`. No product surface was
  changed in this readback.
- 2026-08-04T16:13:43Z: Repeated Star67 README drift was made durablely
  reviewable in product commit `913dd44`. It removes the local setup section,
  adds `scripts/readme-contract.mjs`, and runs that contract at the start of
  the existing `npm test` gate. The full local gate passed: README contract
  `PASS lines=16`, determinism 14/14 across three builds, concurrency green,
  and all existing error/format/pack/progression/crew/casebook/contrast/
  navigator/progress/screen/coaching contracts green. PR #5 restarted from
  this head; this is product proof, not a Pilot Puppy test objective.
- 2026-08-04T16:15:24Z: Current Star67 branch readback found another
  committed owner change, `0c0f013`, removing the README contract and restoring
  local Node/clone/`./start` instructions. PR #5 now has no active checks and
  reports `UNKNOWN` merge state. The accepted browser-first implementation and
  full proof remain available at prior commit `913dd44`, but I did not
  force-push over the newer committed owner work. Resume Star67 only when this
  branch owner stops rewriting the public front door or an explicit branch/PR
  authority is chosen. Continue Snowcubes/Moussey and other reachable lanes
  independently.
- 2026-08-04T16:16:30Z: Current remote readback keeps the Star67 branch owner
  conflict open: `0c0f013` still restores local setup copy and PR #5's two
  builds are running against that head. No force-push or duplicate PR was
  created. Snowcubes has independently advanced to `main@e159bea` with a
  press authority packet; its source ledger and current summary still prove
  Marathon 2026-05-21 FREE/UNKNOWN, `$0.00` open, and no payment row.
  Moussey remains `main@40a487c`; no new consignment or URL change is needed.
- 2026-08-04T16:24:11Z: Started the bounded Codex Security standard-scan
  setup for the current Star67 repository, session
  `09af5c9d-bdc1-4c38-b292-ac202fb40782`. The desktop setup remained waiting
  for the explicit Start-scan choice and produced no scan ID, findings,
  coverage, or security acceptance; no product, deployment, credential, or
  runtime state changed. Resume by choosing Start scan (or the setup's
  prompt-only option), then complete the repository-wide scan and record its
  measured coverage here. Do not claim manual checks as a substitute for
  this official scan.
- 2026-08-04T16:29:40Z: Re-ran the reachable Star67 source/security slice at
  current PR head `0c0f013`. `npm audit --omit=optional` reports 0 total
  vulnerabilities; redacted gitleaks reports one known non-secret local
  storage namespace at `src/Workspace.tsx:87`; no credential value was
  printed or accepted. The repository's full `npm test` gate exited 0:
  determinism 14/14 across three builds, concurrency green, and all existing
  error/format/pack/progression/crew/casebook/contrast/navigator/progress/
  screen/coaching contracts green. PR #5's build checks are green while its
  browser checks remain in progress; this is source/test proof only, not
  merge, deploy, live, or official Codex Security proof.
- 2026-08-04T16:30:10Z: Star67 PR #5 remote readback completed the browser
  gate at head `0c0f013`: both build checks and Chromium, Firefox, and WebKit
  checks are SUCCESS, with `mergeStateStatus=CLEAN`. This closes source/test
  and PR-check proof only. The current head still contains the branch owner's
  local Node/clone/`./start` README copy, and the GitHub rename/homepage/topic
  metadata remains admin-gated; no merge, deploy, or metadata mutation was
  claimed.
- 2026-08-04T16:34:44Z: Advanced the reachable Moussey URL-privacy lane from
  clean `origin/main@40a487c` in isolated worktree commit `7507ab9`, published
  as `codex/moussey-credential-free-phone-origin-20260804`. The shared URL
  helper now owns the phone landing page's credential-free HTTPS `:9443`
  origin behavior; userinfo, path, query, and fragment state are removed, and
  invalid input fails closed. The focused URL suite passes 6/6 and `git diff
  --check` passes. The borrowed full TypeScript check remains red on existing
  cleaner/Slack/control-plane type mismatches, with no diagnostic in the three
  touched files; no protected Moussey checkout, runtime, credentials, or
  authenticated browser state was changed. Resume with PR review/merge and an
  owner-controlled authenticated runtime/browser readback; this is product
  progress, not a Pilot Puppy test objective.
- 2026-08-04T16:36:22Z: Reproduced the Snowcubes consignment source lane at
  fresh `origin/main@69041ac` in an isolated sparse checkout. The focused
  Python consignment/cafe suite passes 289/289, `scripts/audit-consignment-
  source-truth.py` passes every check, and the Nicole consignment contract
  passes 2/2. The current ledger keeps Marathon's 2026-05-21 stock-add
  explicitly FREE with payment status UNKNOWN and no payment row; the audit's
  current open totals are 7 Bagels Deli `$0.00`, Everyman Espresso `$22.00`,
  and Marathon Cafe `$0.00`. No Shopify/admin, customer, money, deployment,
  or protected checkout state changed. Remaining resume predicate is the
  already-recorded owner/deployment alignment for the live agentic-discovery
  surface; source truth is not the same as live proof.
- 2026-08-04T16:36:50Z: Opened Moussey PR #127 for the URL-privacy patch:
  https://github.com/leojkwan/moussey/pull/127. The PR is reviewable from
  commit `7507ab9`; no merge or owner-controlled runtime restart was performed.
- 2026-08-04T16:39:48Z: Fresh Star67 `origin/main@6ebcb93` already carries the
  Star67 product name, `star67-learn-sql` package name, and Vercel launch URL.
  Prepared a clean non-developer README from that current base in commit
  `4f2ecba` on `codex/star67-browser-first-readme-20260804`: 12 lines, launch
  link first, one truthful product sentence, one image, and no install,
  contributor, Node, or local-run instructions. `git diff --check` and the
  focused README contract pass. The isolated full npm runner hung in its
  determinism step and was stopped; no green test claim is made. I did not
  open a duplicate PR while owner-controlled PR #5 remains open at `0c0f013`
  with the conflicting local-setup README; resume when one branch/PR authority
  is chosen. GitHub repository rename/homepage/topics remain admin-gated.
- 2026-08-04T16:42:51Z: Rebuilt the Snowcubes consignment source receipt after
  `origin/main` advanced to `3b48a4a` (`docs(plan): record current Snowcubes
  unblock rerank`). The focused Python consignment/cafe suite remains 289/289,
  the source-truth audit remains fully green, and the Nicole contract remains
  2/2. The current ledger still marks Marathon 2026-05-21 FREE/UNKNOWN with no
  payment row and reports open totals of 7 Bagels `$0.00`, Everyman `$22.00`,
  and Marathon `$0.00`. This is fresh source proof; the canonical plan still
  leaves live deploy/admin rows owner-gated, so no Shopify mutation or live
  claim is made.
- 2026-08-04T16:43:33Z: Read the public Star67 Vercel surface directly at
  `https://learn-sql-peach.vercel.app/`: HTTP 200, Star67 title and practice
  metadata present, with HSTS, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, restrictive Permissions-Policy, and strict
  referrer policy. This is live readback of the existing deployment only; it
  does not prove that the staged README commit `4f2ecba` is deployed, and no
  deployment or GitHub admin mutation was attempted.
- 2026-08-04T16:44:17Z: Reproduced the staged Star67 README branch from remote
  commit `4f2ecba` in a clean worktree. `git diff origin/main..HEAD --check`
  passes and `gitleaks git --log-opts='origin/main..HEAD' --redact` scans 11
  commits / 3.79 KB with no leaks. This is documentation-diff security proof;
  it does not replace the still-unstarted official Codex Security scan or
  prove deployment.
- 2026-08-04T16:44:50Z: Expanded the Moussey URL privacy reproduction on PR
  commit `7507ab9`: shared URL and WebSocket helpers plus the voice secure-link
  contract now pass 9/9 focused tests, including credential-bearing phone-link
  input, LAN secure redirect, invalid input fail-closed, app query stripping,
  and STT WebSocket query stripping. The temporary dependency link was removed;
  no protected runtime or checkout changed. Full TypeScript remains a known
  baseline failure and authenticated browser proof remains owner-controlled.
- 2026-08-04T16:45:12Z: Re-ran Snowcubes `npm run ai:discovery -- --json` at
  source `origin/main@3b48a4a`. The read-only guard still fails on exactly four
  external mismatches: `/agents.md` and `/llms.txt` claim unsupported cart/
  checkout mutation tools; UCP capabilities advertise cart, checkout,
  discount, fulfillment, and order while catalog `tools/list` serves only
  `get_product`, `lookup_catalog`, and `search_catalog`; and the discovered
  Shopify endpoint differs from the configured custom-domain endpoint. All
  probes returned 200. Resume predicate: authorized Shopify/Worker owner
  aligns one canonical endpoint and capability profile, then rerun this guard
  and public readback; no storefront workaround was made.
- 2026-08-04T16:49:12Z: Ran supplementary security checks on Moussey PR
  commit `7507ab9`: `npm audit --omit=dev` reports zero vulnerabilities;
  full redacted gitleaks finds 38 matches, all in `.test.*` fixtures, including
  an intentionally secret-shaped GitLab fixture used to test sanitization; a
  clean archived copy with test fixtures removed scans 17.26 MB with zero
  findings. This supports source triage only; the official Codex Security scan
  is still unstarted and authenticated runtime proof remains owner-controlled.
- 2026-08-04T16:49:40Z: Refreshed the two protected portfolio lanes from their
  canonical plans. StrongYes public `main@7c990f69` has only T-10 open in its
  voice-harness plan: a signed-in, real DSA voice run must produce a product-ASR
  WER number while the same spec fails on silence; it requires the owner
  runtime, credentials, audible headed browser, and authorized spend. Resplit
  public `main@77f1b483` retains the submitted 2.0.0 build 5469 release packet;
  developer release and any screenshot replacement remain separately Leo/
  external-authorized, while the protected checkout is dirty with unresolved
  conflicts and was not touched. These are exact owner predicates, not Pilot
  Puppy test work.
- 2026-08-04T16:53:20Z: Ran supplementary Star67 security checks from the clean
  owner checkout at `codex/nicole-readme-human-prose-20260804@0c0f013`.
  `npm audit --omit=dev --audit-level=moderate` reports zero vulnerabilities;
  `git diff --check` passes. Redacted gitleaks reports one `generic-api-key`
  match at `src/Workspace.tsx:87`, which is the literal local-storage key
  `pivot.navigatorWidth.v1`, not a credential; no secret was exposed. This is
  a triaged manual result, not completion of the still-unstarted official
  Codex Security scan or proof that the staged README commit is deployed.
- 2026-08-04T16:55:40Z: Revalidated Snowcubes against fresh `origin/main@40170f9`
  after the source advanced past the prior `3b48a4a` receipt. The focused
  consignment/cafe suite remains 289/289, the source-truth audit remains fully
  green, and the Nicole contract remains 2/2. Marathon's 2026-05-21 row is
  still explicitly FREE/UNKNOWN with no payment row; open totals remain 7
  Bagels `$0.00`, Everyman `$22.00`, Marathon `$0.00`. Read-only agent discovery
  still returns exactly four HTTP-200-surface errors: unsupported cart/checkout
  claims in `/agents.md` and `/llms.txt`, UCP capability drift, and configured
  custom-domain versus discovered Shopify MCP endpoint drift. Resume remains
  the authorized Shopify/Worker owner aligning one endpoint and capability
  profile before rerunning the guard and public readback.
- 2026-08-04T16:55:40Z: Rechecked Moussey current `origin/main@67ade314` without
  touching the dirty owner checkout. The current consignment surface contract
  asserts the old screenshot markers (`Data source`, `Technical source
  details`, `billing model`) are absent while retaining plain-language
  balances, visits, payments, history, and the non-invoice note. The existing
  local `/consignment` listener returned HTTP 200 and its HTML response exposed
  none of those stale markers. This is fresh source plus unauthenticated
  runtime readback; authenticated browser proof and any runtime restart remain
  owner-controlled.
- 2026-08-04T16:56:54Z: Reproduced the Moussey consignment surface contract from
  a clean detached worktree at current `origin/main@67ade314`, using the
  owner checkout's existing `tsx` loader without installing or modifying either
  checkout. `node --test --import .../tsx/dist/loader.mjs
  app/consignment/surface.test.ts` passes 15/15, covering removal of invoice/
  technical/billing-era chrome, plain-language entry points, source-boundary
  states, payment safety, touch targets, and reduced motion. This is source
  proof only; it does not replace an authenticated browser/runtime release
  receipt.
- 2026-08-04T16:57:18Z: Ran supplementary security checks on fresh Snowcubes
  `origin/main@40170f9`: `npm audit --omit=dev --audit-level=moderate` reports
  zero vulnerabilities, redacted gitleaks scans 9.08 MB with no leaks, and
  `git diff --check` passes. This is source/dependency proof only; it does not
  resolve the four live agent-discovery contract errors or authorize a Shopify,
  Worker, Admin, deployment, or customer-data mutation.
- 2026-08-04T16:57:38Z: Fresh direct readback of the existing Star67 deployment
  `https://learn-sql-peach.vercel.app/` returned HTTP 200 with the Star67 title,
  HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, restrictive
  Permissions-Policy, and strict referrer policy. Vercel reports a cache hit;
  this proves the existing deployment only. It still does not prove that the
  staged browser-first README commit `4f2ecba` is merged or deployed, and no
  GitHub-admin or deployment mutation was attempted.
- 2026-08-04T17:00:44Z: Moussey PR #127 merged to `main` as `fbe36506` after
  exact-head review. From a clean detached worktree at current main, the
  consignment surface contract passes 15/15 and the merged URL/privacy suite
  passes 9/9 (`page.phone-secure` 3/3 plus `moussey-url` 6/6), including
  credential-bearing phone input, invalid-input fail-closed behavior, app URL
  query stripping, and STT WebSocket credential stripping. The first combined
  run lacked dependencies in the clean worktree; the rerun used the existing
  owner dependency installation without changing source. Authenticated browser
  and runtime deployment proof remain owner-controlled.
- 2026-08-04T17:58:05Z: Reconciled the portfolio after the next reachable
  product changes. StrongYes PR #1451 merged its private Coding Workbench
  foundation as `main@3386dd3e`; the package gate was reproduced at 21/21 with
  outside-app import and no public publish, and the canonical StrongYes plan
  receipt was closed by PR #1473 at `main@323ab11a`. This is source/merge proof,
  not a deploy or public-package release. Snowcubes advanced to
  `main@b65992fe`; the fresh consignment/cafe gate remains 289/289, the
  source-truth audit is `ok: true`, and Nicole's contract is 2/2. Zack is
  `$0.00` open; the `$225.63`, `$342.04`, and fixture-only `$57.75` values remain
  documented as non-receivables; Marathon's 2026-05-21 row remains explicit
  FREE/UNKNOWN with no payment row; live discovery remains the previously
  recorded external four-error owner/deploy predicate. Moussey advanced to
  `main@c74c8c67` after PR #128; focused source/build/local-runtime proof is
  green and the consignment share copy is plain-language, while protected
  runtime/authenticated browser and official security-scan setup remain open.
  Star67 public source is `main@a157caba` and its existing Vercel front door is
  live/healthy; GitHub rename/homepage metadata and the staged README merge or
  deployment remain admin/owner predicates. Resplit remains `main@77f1b483`
  with its dirty owner checkout and native release/device predicates untouched.
  These are product receipts and explicit resume predicates; Pilot Puppy
  testing is not a portfolio completion gate.
- 2026-08-04T18:08:31Z: Star67 PR #6 merged to public `main@bc9808de`. The
  README is now 12 lines, puts the hosted launch link first, keeps one truthful
  non-developer description and one landing image, and removes all local
  Node/clone/start instructions. `git diff --check` passed. The two GitHub
  build jobs were still `IN_PROGRESS` when the README-only merge completed, so
  CI is not claimed green; the existing Vercel front door independently returns
  HTTP 200 with Star67 title and restrictive security headers. GitHub still
  reports `admin=false`, so repository rename/homepage/topic metadata remains
  owner-admin work. The merged README is source/merge proof, not proof that a
  new Vercel deployment contains README text.
- 2026-08-04T18:08:31Z: Rechecked current Moussey `main@c74c8c67` from a clean
  detached worktree. The full route/privacy/consignment/auth slice passes
  **52/52**: the proxy strips password/token-style query state across every
  non-API app route, intentionally preserves only `/media` capability tokens,
  and the merged consignment copy stays free of technical/billing/invoice-era
  markers. This is source and unauthenticated local proof; protected runtime,
  authenticated browser, and official Codex Security scan setup remain open.

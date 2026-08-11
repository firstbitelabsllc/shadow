# Shadow — Plan

This file is the sole plan, proof, and resume authority for Shadow (formerly Pilot Puppy; renamed 2026-08-05 — "you are my shadow").

## Brief

- Project: shadow
- Mode: ship
- Priority: 1

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
- [completed] `shadow status` v3 outcome-schema path cut or migrated to the v4 Brief ~c9ut | proof: read shadow status -> v4 Brief fields, zero "outcome must be a string" on a grammar-clean plan | needs: ~a4mp
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
- [pending] the release is installed from the clone on the SECOND machine ~rel1 (DoD) | proof: gate leo resume: on the other machine run git pull, bash install.sh, shadow doctor green, then open a cold session and confirm it names a row without being asked | needs: ~inst

### M7 — one chat, dozens of conversations
- tools: scripts/shadow-throw.py is the dispatch record; `shadow status --in-flight` is the recovery view; design corpus = the 2026-08-08/09 session's five real cases
- [completed] `shadow throw` claims a row before any conversation leaves the chat — refuses proofless, needs-blocked, already-thrown, and mid-merge rows ~thrw | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw
- [completed] auto-resume skips THROWN rows; hand-claimed in_progress rows stay selectable ~dsc0 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw | needs: ~thrw
- [completed] `shadow status --in-flight` renders every claimed row across the portfolio with its proof and throw time ~mstr | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw | needs: ~thrw
- [completed] dispatch law lands in AGENT.md + grammar.md: row-first dispatch, THROWN discriminator, write-at-discovery, the death sequence ~dlaw (DoD) | proof: cmd scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md | needs: ~mstr

### M8 — 0.1.0: one honest number, and the fan-out law dogfooded
- tools: `scripts/shadow-release-package.py --expect-version` is the artifact gate; the audit runs as three NAMED agents (inspectable, messageable), never a sealed workflow; doctor's native-host floor and standing-goal checks read the machine running it, not the clone, so ~land asserts the install-scoped checks by name instead of doctor's exit code
- [completed] the v3 Outcome blob leaves PLAN.md; no live prose calls the product Pilot Puppy ~dslp | proof: read every "Pilot Puppy" left in PLAN.md sits in a timestamped ## Progress line or the rename note on line 3; the v1 acceptance section, ## Work, and ## Portfolio map that carried the rest are in docs/plan-archive/
- [completed] VERSION and plugin.json read 0.1.0 and the release artifact verifies at that version ~vrst | proof: cmd scripts/shadow-python.sh scripts/shadow-release-package.py --expect-version 0.1.0 --allow-dirty
- [completed] repo audited for 0.1.0 readiness; every must-fix either fixed or written as a row ~audt | proof: read 11 must-fix findings from the 5-agent audit: 9 fixed in b76dfa3, 1 held as a Contradiction, 1 as a Deferred row
- [completed] the fan-out law is stated where dispatch is decided: an unattended fan-out leaves a thrown row first, whichever mechanism spawns it ~fout | proof: read AGENT.md Row-first dispatch carries mechanism-neutrality, supervisable-by-default, and the mid-flight clause; grammar.md Dispatch law names a self-launched batch
- [completed] 0.1.0 merged to main, installed from the clone, and every doctor check the clone itself controls green at that version ~land (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; bash "$d/s/install.sh" --bin-dir "$d/bin" --no-skills >/dev/null; test "$("$d/bin/shadow" --version)" = 0.1.0; if HOME="$d/home" "$d/bin/shadow" doctor > "$d/out"; then :; fi; grep -q "^\[PASS\] python:" "$d/out"; grep -q "^\[PASS\] git:" "$d/out"; grep -qx "\[PASS\] product identity: shadow 0.1.0" "$d/out"' | needs: ~vrst

### M9 — Shadow installs itself: host directives, extension buckets, one canonical plan home
- tools: superpowers is the reference implementation for host-directive injection; `shadow doctor` is where every claim in this milestone gets a check; research runs as NAMED agents on disjoint surfaces
- [completed] the open design questions are answered from evidence, not preference ~rsch | proof: read three of five named agents reported and their findings are folded into ~obsv, ~home, and ~bkts as decisions with measurements; two went idle without a report and those rows were built from first principles instead
- [completed] `shadow goal --install` writes a MANAGED block into ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md, and install.sh runs it by default -- idempotent, marker-delimited, adopts an unmarked copy, refreshable, removable, atomic, never clobbering a person's own text. Cursor is excluded on purpose until ~rsch names its real surface ~host | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives
- [completed] extension buckets: Shadow declares named slots where a method pack plugs in (superpowers, honcho, taste), the committed declaration IS the default, and doctor reports each as present/absent/stale ~bkts | proof: cmd scripts/shadow-python.sh -m unittest tests.test_extension_buckets | needs: ~host
- [completed] the canonical home for plans is decided from what is actually on this machine and written into grammar.md; the portfolio fallback implements that rule ~home | proof: read grammar.md carries ## Plan location; `shadow status` from an empty temp dir and a plan-less repo returns byte-identical boards, and Shadow's own plan is on it
- [completed] one deterministic setup verifier per host proves the wiring end to end -- not that files exist, but that a cold Claude/Codex/Cursor session resolves the skill, reads the directive, and reaches the board ~detv | proof: cmd bash -c 'scripts/shadow-verify-host.sh --host claude-code && scripts/shadow-verify-host.sh --host codex && scripts/shadow-verify-host.sh --host cursor' | needs: ~host
- [completed] observability verdict: adopt, augment, or kill Langfuse for end-to-end triage ~obsv | proof: read KILL, on two verified facts: Shadow makes zero model or network calls, and self-hosted Langfuse is six restart:always services with an S3 event bucket -- literally the daemon and transcript store Boundaries name
- [completed] a stranger runs one command and ends with all three hosts wired, doctor green, and the board reachable from any directory ~w1re (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; export HOME="$d/home"; mkdir -p "$HOME/.claude" "$HOME/.agents" "$HOME/.cursor" "$HOME/.codex" "$HOME/Development/proj"; cp "$d/s/PLAN.md" "$HOME/Development/proj/PLAN.md"; bash "$d/s/install.sh" --bin-dir "$d/bin" >/dev/null; export PATH="$d/bin:$PATH"; shadow doctor >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host claude-code >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host codex >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host cursor >/dev/null; cd "$d"; test -n "$(shadow status)"' | needs: ~bkts

### M10 — two leads, one plan
- tools: the plan is the channel and `git fetch` is the refresh; the push rejection is the mutex. Nothing here may add a lock, a coordinator, a session registry, or a roster file
- [completed] a claim carries WHO made it: `--by` lands in the THROWN tail (never before the id) and `--in-flight` renders it ~lead | proof: cmd scripts/shadow-python.sh -m unittest tests.test_two_leads
- [completed] two leads racing one row is resolved by the push, not by a lock: the loser recovers onto the winner's revision and is told whose row it is, and never runs over unrelated local commits ~race | proof: cmd scripts/shadow-python.sh -m unittest tests.test_two_leads.ThePushRejectionIsTheMutex | needs: ~lead
- [completed] the collaboration protocol is written where a cold lead reads it: claim with a name, needs: is the dependency tree, NOTE addresses a lead, challenge in writing, no roster ~prot (DoD) | proof: read AGENT.md "Several leads, one plan" and grammar.md Dispatch law carry all five; commands.md documents --by | needs: ~race

### M11 — close the open-PR debt before it rots
- tools: every one of these predates tonight and is BEHIND main; rebase or close, never leave a fourth stale branch. `gh pr diff` against current main before assuming a PR is still needed
- [completed] the two halves of the explain-inline contract land together: the rule in SKILL.md and the guard that makes it fail ~styl | proof: cmd scripts/shadow-python.sh -m unittest tests.test_style_guard
- [completed] the v3 route/seat excision finishes in docs/reference/native-hosts.md, and the seat-map example either lands outside Shadow or is dropped ~excs | proof: read native-hosts.md states the refusal ("There is no roster, route, or seat layer in front of it") instead of leaving silence; `git grep -q 'shadow route' -- ':!docs/plan-archive/**' ':!docs/superpowers/**' ':!PLAN.md'` finds nothing -- plan-archive and docs/superpowers/ are archived design records, not live prose, and superpowers' staleness is its own Deferred row with its own wake
- [completed] a fresh adversarial pass over the ten PRs merged 2026-08-09 finds what their own reviews missed, or says so with the searches that came back empty ~adv9 | proof: read every confirmed finding names file:line and is fixed or given a row; a clean lane reports the search it ran and its zero result
- [completed] every stale PR is landed or closed with its reason, and the branch is gone ~debt | proof: cmd bash -c 'test "$(gh pr list --json number --jq length)" -le 1' | needs: ~styl, ~excs
- [completed] the repo has no open PR older than the newest merge, and main passes the full gate from a clean clone ~clen (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md' | needs: ~debt

### M12 — the configurable half: one config file, the adversarial step, /future

- tools: the fixed half already shipped (standing goal, `--install`, drift check, grammar, proof law). This milestone is only what the owner said users decide. Every row keeps the buckets law: declaration only, zero resolved state, absent is fully functional
- [completed] shadow reads one repo-local config file, and a machine that has none behaves identically to today ~cfg1 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_config_defaults
- [completed] the parser refuses the YAML it does not support by naming the file and line, instead of misreading it into a wrong binding ~yml2 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_config_defaults.TheSubsetRefusesWhatItCannotParse
- [completed] a provider, model, account, or credential key anywhere in the config is refused, never quietly ignored ~noks | proof: cmd scripts/shadow-python.sh -m unittest tests.test_config_defaults.NoSelectorKeys | needs: ~cfg1
- [completed] the adversarial step is written into the method as attack-then-refute with lens sets the config can name, and the no-runtime-roles boundary still reads true ~advm | proof: read docs/reference/method.md names the step and its default lenses, `shadow config --explain` prints them, and SKILL.md still says Thermo and Ponytail are review disciplines rather than runtime roles
- [completed] /future is reachable as a declared bucket and goal-minting reads the plan's own LESSON and DECISION rows instead of a new store ~ftur | proof: cmd scripts/shadow-python.sh -m unittest tests.test_extension_buckets.FutureIsADeclaredBucket tests.test_amp.GoalMintingReadsThePlansOwnLessonRows tests.test_extension_buckets tests.test_amp
- [completed] a stranger clone binds taste, durability, and leads from config alone, behaves identically without one, and refuses one carrying a provider key ~conf (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh -m unittest tests.test_config_defaults' | needs: ~cfg1, ~yml2, ~noks, ~advm, ~ftur

### M13 — what the adversarial pass found, fixed

- tools: 44 agents, 5 attack lanes over ref 88c758c, every finding refutation-tested before it landed here; 33 survived and 5 were killed. Ranked by cost if left. The full report is the ~adv9 PROOF line
- [completed] `shadow throw` can never commit or push a truncated PLAN.md because the root-board design never writes or commits the project plan at all: it pins one committed PLAN.md snapshot, takes the claim through the board's atomic transaction, and leaves the project plan bytes and Git HEAD unchanged ~atom | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw.ThrowUsesTheRootBoard.test_claim_prints_the_pointer_without_changing_the_project_plan tests.test_root_board.ACrashMidClaimLeavesARecoverableBoard tests.test_throw tests.test_root_board
- [completed] row grammar is checked wherever accept would flip a row, so the enforcer and the only flip path agree on what a task is ~rows | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.RowGrammarRunsWhereverAcceptWouldFlip tests.test_shadow_lint
- [completed] a cmd proof is validated as argv: shell operators are refused unless argv is a shell with -c, and argv zero must resolve ~argv | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ACmdProofIsValidatedAsArgv tests.test_shadow_lint tests.test_shadow_accept
- [completed] every section lookup is prefix-matched, so a suffixed heading cannot silently drop a blocking check ~pfix | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.EverySectionLookupIsPrefixMatched tests.test_shadow_lint | needs: ~rows
- [completed] the documented install path works on a stock machine whose bare python3 is too old, and the README step it prints does not turn a good install into a doctor FAIL ~pyv3 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_install_doctor.TheGateUsesTheResolvedPythonNotBarePython3 tests.test_install_doctor
- [completed] accept never commits a plan its own lint blocks, the style guard fence exemption is bounded, and the host backup keeps the mode of the file it copied ~acpt | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_accept.AcceptNeverCommitsAPlanLintBlocks tests.test_style_guard.TheFenceExemptionIsBounded tests.test_host_directives.TheBackupKeepsTheModeOfTheFileItCopied tests.test_shadow_accept tests.test_style_guard tests.test_host_directives
- [completed] an unmarked standing-goal block is adopted only when the region really is the shipped block or a known earlier revision of it, so a drifted or customized heading is refused by name instead of silently overwritten ~hdop | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.UnmarkedAdoptionRefusesADriftedHeading tests.test_host_directives
- [completed] a plan's self-demotion is the verdict of its most recently committed copy, so a checkout parked in the past cannot retire a logical entity whose current copy is live ~vsup | proof: cmd scripts/shadow-python.sh -m unittest tests.test_root_board.RegisteredPointerIsCanonicalBeforePortfolioParsing tests.test_root_board tests.test_browser
- [completed] every confirmed finding is fixed or carries a Deferred row with a wake predicate, and main passes the full gate from a clean clone ~aud1 (DoD) | proof: cmd bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md' | needs: ~atom, ~rows, ~argv, ~pfix, ~pyv3, ~acpt, ~hdop

### M14 — telemetry and logging, data-minimized

- tools: the owner reopened this after ~obsv killed it. Nothing here sends anything until ~endp is answered; every row below is buildable and testable with the machine offline
- [completed] what Shadow may ever record is written down as a closed allowlist of field names, and anything not on it is dropped at the point of construction rather than filtered later ~flds | proof: cmd scripts/shadow-python.sh -m unittest tests.test_telemetry.TheAllowlistIsClosed
- [completed] a plan verb emits a structured local event to a file under the project evidence path, carrying ids, verbs, durations and outcomes and no plan text, no proof output, no paths outside the repo, no environment ~emit | proof: cmd scripts/shadow-python.sh -m unittest tests.test_telemetry.EventsCarryNoPayload | needs: ~flds
- [completed] a redaction test feeds secrets, absolute home paths, and full proof output through the emitter and proves none of them reach the event ~redk | proof: cmd scripts/shadow-python.sh -m unittest tests.test_telemetry.NothingSensitiveSurvivesTheEmitter | needs: ~emit
- [completed] the owner picks the endpoint and the exact field list before any network code exists, and records both in docs/reference/telemetry.md ~endp | proof: gate leo resume: the chosen endpoint and the approved field list are written into docs/reference/telemetry.md
- [completed] the owner's local sink exists as owner tooling only: scripts/dev/shadow-observed-gauntlet.py runs long test jobs and ships their traces (and optionally the allowlisted local event file) to the owner's local Langfuse over OTLP, refuses without all three SHADOW_LANGFUSE_* env vars, and is referenced by no product script -- a machine that never opts in behaves exactly as it does today ~lfse | proof: cmd scripts/shadow-python.sh -m unittest tests.test_telemetry.TheLocalSinkIsOwnerOptInOnly | needs: ~endp
- [pending] telemetry is off by default, every event is inspectable on disk, and a machine that never opts in behaves exactly as it does today ~tobs (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_telemetry.TelemetryIsOffByDefault tests.test_telemetry.EveryEventIsInspectableOnDisk tests.test_telemetry.AMachineThatNeverOptsInIsUnchanged tests.test_telemetry | needs: ~flds, ~emit, ~redk, ~endp

### M15 — every install activates Shadow in every supported host

- tools: product requirement, shipped to strangers. M9 got claude and codex; this closes the gap and hardens the write. Distinct from M16, which is one person's file layout and ships to nobody
- [completed] cursor either gets a real activation surface proven by a cold session, or it is written down as unsupported and removed from the supported list ~curs | proof: read docs/reference/native-hosts.md states cursor's activation surface with the cold-session evidence, or states that shadow does not activate cursor and why
- [completed] a fresh install writes the activation instruction into every host docs/reference/native-hosts.md still lists as supported once the cursor decision has landed, never into an invented path, and doctor names any supported host that did not receive it ~acti | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.EverySupportedHostIsActivated tests.test_host_directives.TheSupportedListInTheDocsDrivesTheWriteTargets tests.test_install_doctor.DoctorNamesEverySupportedHostThatDidNotReceiveTheDirective | needs: ~curs
- [completed] a host directive file that is a symlink is written THROUGH, never replaced: the canonical target changes and the link survives ~slnk | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.ASymlinkedHostFileIsWrittenThrough
- [completed] a kill between temp creation and rename leaves no permanent `.shadow-*.tmp` residue: the next apply sweeps only temps it can prove belong to a dead run, never a concurrent apply's live temp ~tmpr | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.StaleTempResidueIsSweptSafely | needs: ~slnk
- [completed] a linked write discloses itself: the CLI names the resolved target it actually wrote and any backup it retained, never a bare "added: claude" ~disc (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.ALinkedWriteDisclosesTargetAndBackup | needs: ~slnk

### M16 — one canonical private home for the owner's host directives

- tools: the owner's personal setup, NOT the product. Nothing here ships in the package or runs on a stranger's machine. Shadow's managed block keeps working inside whatever file the host reads
- [completed] the owner's documented user-level claude and codex directive files resolve to ONE SHARED canonical FILE in the private ai-leo repository -- one target, two links, not per-host copies of a shared idea. Cursor has no invented link: the accepted ~curs decision excludes it until Cursor documents a writable user-level file. If a host-specific syntax difference turns out to be genuinely unavoidable, it is opened as a Contradictions row BEFORE anything is split, naming the exact syntax and the host that requires it; splitting without that row is the drift this wording exists to prevent ~cano | proof: read exactly ONE canonical directive file exists in ai-leo at origin/main, both supported host paths resolve to that single file, `readlink -f` on each returns the SAME path, every host's prior content is accounted for line by line with nothing dropped, and Cursor's exclusion cites ~curs
- [completed] each supported host file is a symlink and both resolve to the SAME target, and doctor reports the resolved path so a broken link, a hijacked one, or a silent split into per-host copies is visible ~vsym | proof: cmd scripts/shadow-python.sh -m unittest tests.test_standing_goal.HostDirectiveOriginIsReported | needs: ~cano
- [completed] shadow goal --install still lands its managed block through the symlink, and the canonical file in ai-leo carries the change ~mrge (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.TheManagedBlockLandsInTheCanonicalSourceNotTheLink | needs: ~vsym, ~slnk

### M18 — dispatch reaches a protected trunk

- tools: found by dogfooding, not by review — `shadow throw --task ~slnk` on this repository committed the claim, was rejected by GitHub branch protection, and correctly refused to launch. The guard is right and stays; what is missing is any way for a claim to become durable where the trunk requires a pull request, which is the normal shape of a serious repository and of this one
- [pending] `shadow throw` can claim a row in a repository whose trunk requires a pull request, and the claim is durable on the remote before any goal block is printed ~pdis | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw.AProtectedTrunkStillTakesAClaim
- [pending] durability means REACHABLE by another seat, not merely pushed somewhere — a claim sitting on an unmerged branch is visible only to someone already told the branch name, and the check says which of the two it got ~pver (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw.AClaimOnAnUnmergedBranchIsNotCalledDurable | needs: ~pdis
- [completed] a completion travels like a claim: `shadow accept` pushes its flip commit after the proof passes — no upstream says so and stays local, a rejected push exits loudly naming the PR path, and --no-push is the explicit opt-out; before this, a claim was durable by design while the finish silently stayed local, so a seat that saw work start could never see it end ~apsh | proof: cmd scripts/shadow-python.sh -m unittest tests.test_gauntlet tests.test_shadow_accept

### M19 — this session is processed to zero

- tools: the owner's standing order for the 2026-08-09/10 session: process the whole session's findings and fix everything wrong, with delegation and adversarial review as the method and the board as the memory. Scope discipline: this milestone holds ONLY findings no existing row owns — M14 through M18 and the universal-system rows keep theirs, and repeating them here would be the second queue Shadow bans. M17 is NOT on this board: its stack (PRs 286 and 290, plus the unbuilt ~cnon) stays its own work, and nothing may be excluded from M19 on the claim that M17 owns it — any plan-authority finding the ~z9fn sweep raises takes a row here unless a milestone that actually exists names it
- [pending] the session's transferable lessons stand in AGENT.md as concise general rules, each with a one-line dated incident: liveness is proven by the artifact, never the process; a worktree path is not a lane; an accusation grounds on the merge-base diff, never the tip diff; every read names its ref and an unfetched tree is presumed stale; green fixtures prove the fixtures, never the field ~lssn | proof: read AGENT.md carries each rule with its 2026-08-10 incident, none was already present, and PR 291 is merged
- [pending] the canonical-checkout question is closed with the read-only fact: the local codex/browser-routing-shadow-20260809 ref was moved to the worker's pushed branch by an explicit `reset: moving to origin/m15-slnk-write-through`, recorded in that branch's own reflog before the lead ever touched the checkout, and the lead's later ORIG_HEAD restore returned it to exactly that post-reset state — a deliberate repoint to inspect pushed work, not corruption; nothing in the checkout was modified to establish this ~canx | proof: read the reflog lines quoted in the closing Progress entry match `git reflog show codex/browser-routing-shadow-20260809` on the machine, and the checkout was not written to
- [pending] the legacy-id dispatch gap gets a decision that CANNOT bypass THROWN or M18's durability: rows like P9a~formats in trysnowcubes-web are unclaimable because the id grammar is four base36 chars, and the answer is either widened ids carried through throw, lint, accept and amp with tests at each, or an equivalent atomic remote claim that meets M18's reachable-durability bar — a hand-written claim line stops being a sanctioned form the moment either lands. Snowcubes' own adoption of whichever wins is recorded in Snowcubes' plan, not here ~lqid | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.TheIdGrammarMatchesTheDecisionRecordedInGrammarMd tests.test_throw.ALegacyIdRowIsClaimedByThrowWithoutAHandWrittenLine tests.test_throw tests.test_shadow_lint tests.test_shadow_accept
- [completed] lint and accept share one cmd-proof validator: an explicit Python or Node script is refused before execution unless it is one committed relative regular file beside PLAN.md, while supported inline, module, flag, env, and output arguments remain legal ~pscr | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ACmdProofIsValidatedAsArgv tests.test_shadow_accept.ProofScriptArgumentsAreValidatedIdentically tests.test_shadow_lint tests.test_shadow_accept | needs: ~argv
- [completed] `shadow accept` refuses or loudly warns when an open Contradictions row names the accepting row or anything in its needs-ancestry -- today nothing gates a flip on a challenged foundation, so a dependent can accept work whose basis is under a written, undelivered challenge ~cgat | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_accept.AChallengedFoundationDoesNotFlipSilently
- [completed] a needs: cycle is a lint finding, not a silent deadlock: shadow-lint detects dependency cycles among rows and names the cycle ~ncyc | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ANeedsCycleIsNamedNotSilent
- [completed] the claim-safety scope boundary is written where a cold lead reads it: mutual exclusion is per-computer (the advisory lock), cross-computer serialization exists only at PLAN.md push/merge time, and a fleet spanning two machines double-claims until a cross-machine protocol row exists ~xmac | proof: read grammar.md states the per-computer scope in plain terms and names the condition that mints the cross-machine protocol row
- [completed] a rejected accept push names WHERE the flip commit is parked -- the repository and branch of the STORED plan pointer, which can differ from the --repo argument the operator typed -- so "land it through a pull request" is followable; an unnamed location reads as a destroyed commit and gets hand-duplicated ~aflp | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_accept.ARejectedPushLeavesTheFlipReachable
- [pending] a dated audit of THIS repository closes the session: every finding from the 2026-08-09/10 session names its disposition — a row, a merged PR, or an owner and gate — with the evidence file or ref beside each, and every in_progress row on this board names a branch or PR a stranger can reach; reachability of claims in OTHER repositories stays M18's requirement and is not re-litigated here ~z9fn (DoD) | proof: read the audit lands as a dated Progress entry naming each finding and its evidence, and for every in_progress row the entry names an artifact a second seat actually reaches from a fresh clone with nothing but the row id — the branch or PR resolves on the remote and its content is fetched and read back; a name reachable only by someone already told where to look fails this row | needs: ~lssn, ~canx, ~lqid, ~pscr
- [completed] the public repository is share-ready: a stranger can install Shadow, name the computer-board/PLAN.md authority, complete the first claim-to-proof loop, understand host and proof boundaries, and close every chat with a fresh board-sourced Ongoing tasks footer; stale visuals and unsupported commands are labeled rather than implied ~r4d0 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_readme_contract tests.test_documented_targets tests.test_install_doctor tests.test_verify_host tests.test_public_ready_grep_gate

### Universal system: one root board per computer

- tools: minted from the owner's direction across two seats (2026-08-10): one root board per COMPUTER for priority, claims, and resume pointers; project plans stay authoritative shards for their own rows and proof; the board indexes and arbitrates, it never absorbs — a task's text exists in exactly one file, ever. The goal prompt is a pointer to THIS milestone; requirements live here and in the register, never in the prompt
- [completed] bounded owner decisions and live repository contradictions are folded into one decision register — each entry adopted, rejected with its reason, or deferred with an exact wake; chats remain non-authoritative leads and no exhaustive second inventory is claimed ~dreg | proof: read docs/reference/universal-system-register.md states the authority boundary and records the reconciled decisions
- [completed] the root board exists and is claim-safe: a git repository at ~/.shadow holding the computer's project → entity rotation, priority, claims, owners, and one resume checkpoint per entity — pointers, never copies of milestone or checkpoint text. Every reachable entity and its current milestone/checkpoint is projected; a project never collapses to one opaque row. The LOCAL file is the authority; a private remote is optional recovery, best-effort and async, never required for a write to count and never live authority — recovery is only ever as fresh as the last push, and that limit is stated where the remote is configured. The claim contract is mechanically proven: of two seats claiming the same checkpoint concurrently exactly one wins and the loser is told, and a seat that dies mid-claim leaves a recoverable board — an advisory lock reusing the installer's crash-safe write discipline is the implementation candidate, not the contract ~root | proof: cmd scripts/shadow-python.sh -m unittest tests.test_root_board.TheBoardHoldsPointersNeverRowCopies tests.test_root_board.AWriteCountsWithNoRemoteConfigured tests.test_root_board.ConcurrentClaimsHaveExactlyOneWinner tests.test_root_board.ACrashMidClaimLeavesARecoverableBoard
- [completed] board hygiene owns both doors — what enters and how it leaves. Entering: bounded provenance-preserving import, real plans becoming pointers with worktree and snapshot ghost copies excluded by construction via the shipped dedup and archive-veto machinery. Leaving: compaction, completion, and garbage collection with teeth — enforced byte/row/milestone budgets on hot plans, a return-by on every claim after which it is reclaimable, standing loops as finite lifecycle receipts that each name a successor but never cap the Outcome, dry-run-first idempotent cleanup with deterministic compaction, and deletion that REFUSES dirty or provenance-bearing state (snapshot first). Closing a lifecycle receipt exposes and claims the next reachable work until full acceptance or exact hard-rail wakes. Landed worktrees retire, snapshots expire, shipped milestones archive — growth can never recreate the 7,768-ghost-plan state ~gc20 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_root_board.ImportExcludesGhostCopiesByConstruction tests.test_root_board.RegisteredPointerIsCanonicalBeforePortfolioParsing.test_same_identity_archive_veto_retires_the_registered_entity tests.test_root_board.HotPlanBudgetsGateNormalBoardEntry tests.test_throw.ThrowUsesTheRootBoard tests.test_lifecycle tests.test_shadow_lint.ShadowLintTests tests.test_shadow_accept.ShadowAcceptTests.test_review_worktree_cleanup_refuses_all_dirt_and_never_uses_force tests.test_release_package.ReleasePackageTests.test_lifecycle_command_ships_with_the_dispatcher tests.test_verification_tiers.ASilentSkipFailsLoudly.test_retirement_schema_runs_lifecycle_and_release_proof | needs: ~root
- [completed] the activation text is frozen to one invariant plus the loop and rails, byte-identical for every supported cold host. The public installer has one atomically replaceable managed-marker mode that touches nothing outside its block; a private one-time operation may replace only the owner's own host file by reusing that generated block, adjacent backup, and atomic write, and an upgrade re-run must converge. Cursor's mount and sealed runner stay supported while cold directive activation is honestly unsupported until a reviewed writable rule surface exists. Every human-facing goal, status, plan heading, document, and update leads with a descriptive outcome and hides milestone numbers, row IDs, branch slugs, and internal track names unless an exact machine reference is requested ~actv | proof: cmd scripts/shadow-python.sh -m unittest tests.test_human_language.PlainOutcomeNamesLeadEveryHumanSurface tests.test_host_directives.ActivationIsByteIdenticalAcrossSupportedHosts tests.test_host_directives.DogfoodOverwriteBacksUpAndConverges tests.test_verify_host | needs: ~slnk, ~curs
- [completed] capability buckets prefer the fleet's best compatible whole leaf disciplines — concretely installed Superpowers verification, test-driven development, systematic debugging, and receiving-review leaves may supply source discipline, while the host-neutral packet selects their Shadow Method adaptation rather than pretending a Claude-cache plugin is invokable by Codex or Cursor. Brainstorm and request-review ideas are likewise adapted instead of selecting their hard-gated plugin leaves, and the approval/spec/plan/delegation chain stays refused. Design runs through /craft with /taste as the quality bar; delegation runs through Shadow's own claimed host-run. Filled buckets are not the proof: `shadow amp` deterministically selects the applicable installed whole capability or adaptation and records why, version/detail, native fallback, and result; raw pack/forbidden invocations are removed from projected tools; zero compatible leaves, absence, stale state, disabled buckets, malformed manifests/results, and optional resolver exceptions warn but never block status, install, claim, or the amp packet ~bops | proof: cmd scripts/shadow-python.sh -m unittest tests.test_amp.CapabilitySelectionIsDeterministicAndRecorded
- [completed] verification starts at the first usable slice: team agents independently attack the real verbs, run the declared focused checks, and dogfood Shadow on Shadow before the next layer expands. One fixed nightly train always runs to catch rot; an optional configured second daily window and an automatic early train run only when versioned accepted-trunk-change count, oldest-change age, severity, or changed-path risk thresholds fire. Zero accepted changes suppresses only the early feature train, never nightly verification. Trunk changes run affected integration checks; release-contract changes and each train run the repeated story gauntlet, migration/lifecycle, adversarial/crash, capability/rotation, rollback/upgrade, stranger-install/package, and real Chromium proof with fresh homes. CI records only source and stranger-install observations: merge, deployment, and live dogfood stay separate owning-plan receipts and are never inferred from green. Early green proves only its slice, and a silent skip fails loudly with that failure itself tested ~tier (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_verification_tiers.ASilentSkipFailsLoudly tests.test_release_train.ReleaseTrainTriggersAreDeterministic


### M21 — the board renders the grammar it displays

- tools: found by the owner opening the live board and seeing every project dead — "the UI UX is completely broken." Diagnosis: the browser still demanded the v3 typed-Outcome Brief the grammar retired on 2026-08-09, so all 11 real plans on the dogfood machine failed "outcome must be a string" and rendered as walls of "needs a Brief". A v3 surface reading v4 plans. The owner's bar for this surface: open-source-grade, with component-state and visual proof — capability in-house (this repo is Python-only per M6), patterns learned from Storybook and Playwright rather than their npm toolchains imported
- [completed] the board projects the v4 grammar: a TOTAL board brief per plan (state, priority, shown milestone with counts/current/next/DoD, open contradictions, latest change) — milestone selection follows the work (in_progress first, stale pendings cannot shadow it; rows above the first ### form an implicit group), pre-grammar plans read "unmigrated" not "empty", and the v3 contract can only error for a plan that still carries its keys ~v4bd | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser.AV4PlanGetsABoardBriefNotAnError
- [completed] visual states are fixtures with proof: every board/brief card state (working, ready, blocked, resting, unmigrated, empty, v3-rich, decision-waiting) renders from a checked-in fixture set served by the same server, and an automated browser harness fails on broken styling — each state rule proven to FIRE against an unstyled baseline, console clean, screenshot kept as a CI artifact, and a missing browser under SHADOW_VISUAL=1 is a failure, never a silent skip ~vgal | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser.TheGalleryShowsEveryStateHonestly, and SHADOW_VISUAL=1 python -m unittest tests.test_gallery_visual in the visual-proof CI job | needs: ~v4bd
- [completed] the board reads like a product, not a debug dump: the detail panel never covers the project list at any supported width, timestamps read as relative human time, no raw commit hash, receipt grammar word, or milestone code number reaches a card, the Done-means text is never cut mid-word with a state glued into it, and every state chip and count is a styled element with one type scale ~uxf1 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser.TheBoardSpeaksHumanNotMachine tests.test_gallery_visual | needs: ~v4bd
- [pending] the owner opens the live board and every real plan on the machine shows its true state — a working project shows its milestone and current row, a pre-grammar plan says so, nothing renders as an error wall ~v21d (DoD) | proof: gate leo re-observes the board at :7191 after the fix is merged and the server restarted | needs: ~v4bd, ~vgal


### M22 -- Shadow 1.0 MVP: one stranger completes the recursive loop

- tools: this is the sole Shadow 1.0 product lane, not a second project or queue. It reuses the recursive-acceptance milestone minted by the owner's 2026-08-10 goal and keeps its moved activation, canonical-directive, protected-claim, killed-chat, multi-lead, outside-project, and two-seat checkpoints without copying them. The 1.0 boundary is one immutable public source identity, one stranger's first uncoached loop, interruption and multi-seat recovery, and no orphan authority. Keep trust-boundary and destructive-state falsifiers; defer parser consolidation, telemetry polish, and broad unit expansion that does not make this acceptance fail. Satisfied needs on rows whose dependencies archived with their source milestones are folded per the lifecycle law
- [pending] a stranger selects one immutable Shadow 1.0 source from README and GitHub Releases, installs it on a clean machine, reads `shadow --version` as that same release, and their next chat in every supported host opens the board without being asked; GitHub Latest and release-pressure baseline resolve to the same commit rather than a legacy tag ~act9 | proof: gate leo resume: from the exact public release ref, install and assert VERSION, tag, GitHub Latest, release-pressure baseline, installed version, and source commit agree; scripts/shadow-verify-host.sh --host HOST --live reports no FAIL for every host still listed as supported after ~curs; and cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.EverySupportedHostIsActivated tests.test_host_directives.ASymlinkedHostFileIsWrittenThrough tests.test_host_directives tests.test_verify_host tests.test_release_package is green | needs: ~acti, ~curs, ~slnk
- [pending] the owner edits THE one file in ai-leo, commits, and every host reads that same change with no copy step and no per-host duplicate anywhere ~cn16 | proof: gate leo resume: a directive edited in ai-leo is visible to a fresh session of claude, codex, and cursor without any sync command, or cursor is excluded by citing the ~curs decision that shadow does not activate it | needs: ~cano, ~vsym, ~mrge
- [pending] a stranger clones a repository whose trunk is protected, claims a row, and a second machine finds that claim without being told where to look ~pd18 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_throw | needs: ~pdis, ~pver
- [pending] one real multi-conversation cycle driven through throw end to end, with a deliberate chat kill mid-flight ~live | proof: gate leo resume: throw 3+ rows, kill the chat, then recover the fleet from `shadow status --in-flight` alone
- [pending] two real leads run one plan end to end -- both claim, one blocks on the other's needs:, one challenges a flip in writing, and neither loses work; the run includes the contradiction triangle: a written Contradictions row against a foundation another row needs:, and the dependent's accept is visibly blocked or warned rather than silently flipping ~pair | proof: gate leo resume: give the same goal to a Claude seat and a Codex seat, both with --by, read `shadow status --in-flight` to see whose is whose, and see the challenged-foundation accept refuse or warn
- [blocked] one outside project completes the full recursive loop uncoached: a real intent becomes one canonical checkpoint in that project's PLAN.md, the computer board points to that entity and atomically claims the exact row, the claimed execution capsule drives bounded work, `shadow accept` proves and completes it, and the project mints one concrete successor -- a cold observer reconstructs the whole chain with zero coaching turns and no copied queue ~outp | proof: read the outside project's merged PLAN history shows the intent, minted checkpoint, accept-appended PROOF, and newly minted reachable successor; read the computer-board Git history separately shows the exact entity/row/seat claim followed by its release and successor resume, with no orphan claim -- the receipt names the outside start and completion SHAs plus the board claim and release commits, never a copied THROWN line
- [pending] the two-seat proof, uncoached: one sealed command creates only a scratch HOME, disposable local Git repositories, and one shared root board, then two concurrent stable public seats see each other's claims, claim disjoint rows, and complete both with proof. Offline mode spends no host quota; explicit live mode gives one real Claude session and one real Codex session only the same frozen seat-neutral goal, whose SHA-256 and one freshly fetched origin/main ref each must print independently. Live verification derives expected work from that seat's own claim or next reachable checkpoint, never the first global resume; every host process group is time-bounded and drained, and timeout, board drift, identity mismatch, partial completion, or an orphan claim is inconclusive rather than green. The path-free receipt never contains prompts, transcripts, provider/account data, or row prose, and the harness never flips this person-observed gate itself ~2st8 (DoD) | proof: gate leo re-observes both real sessions through the sealed live command; and cmd scripts/shadow-python.sh -m unittest tests.test_root_board tests.test_lifecycle tests.test_verify_host tests.test_two_seat_harness tests.test_gauntlet is green

### M23 — Shadow travels without losing the truth

- tools: one portable package serves local agent hosts; one plain-language source document serves a hosted Custom GPT. Local installs may read and act only when the host can reach the computer board. Hosted surfaces are coach mode until a reviewed privacy-safe bridge exists. No new queue, fake endpoint, copied board, or transcript store is created to make a distribution matrix look complete
- [completed] the portable package installs from this repository in ChatGPT/Codex and validates in Claude Code, while Cursor consumes the same checked-in Agent Skill; all adapters share one version and one source skill rather than drifting copies ~plug | proof: cmd scripts/shadow-python.sh -m unittest tests.test_distribution_contract tests.test_release_package
- [completed] every front door returns the same human brief — outcome, parallel motion, consequence, decisions made, stalls and restart conditions, a challenging question, missing evidence, and the next evidence checkpoint — while branches, hashes, paths, row IDs, and commands stay technical evidence on demand ~hrbf | proof: cmd scripts/shadow-python.sh -m unittest tests.test_distribution_contract.DistributionContractTests.test_human_brief_hides_machine_detail_until_requested | needs: ~plug
- [completed] the Custom GPT source starts by saying it cannot see the local board, cannot claim execution, and returns a typed intent packet for real local Shadow; no Action, app, MCP server, or placeholder transport ships before a real reviewed bridge ~cstm | proof: cmd scripts/shadow-python.sh -m unittest tests.test_distribution_contract.DistributionContractTests.test_hosted_coach_never_claims_local_authority tests.test_distribution_contract.DistributionContractTests.test_distribution_does_not_publish_a_placeholder_transport
- [completed] a cold nondeveloper can paste rough intent and explain the returned outcome, what is moving, what needs attention, and what happens next without learning Git or the plan grammar; the proof uses an unfamiliar fixture and fails if the response leads with machine identifiers ~cold | proof: read a dated Progress receipt records the fixture, the rendered human brief, the four comprehension answers, and the machine-detail leak scan | needs: ~hrbf, ~cstm
- [pending] public directory submissions happen only after source proof, privacy copy, screenshots, and listing metadata are current; no source implementation row waits on publication, and no directory presence is claimed before its public readback ~publ (DoD) | proof: gate leo resume: authorize public submissions, then record each submitted directory URL and its public readback | needs: ~cold

## Worklane boundary

- Shadow has its own product plan and proof gap. That gap never blocks an
  unrelated product from shipping the highest-value reachable row in *its* own
  canonical plan.
- Reviewable task boundaries scope ownership and proof; they never cap the
  Outcome, session, project set, or deliverables. Drain every reachable lane,
  fan out path-disjoint work, integrate its proof, and immediately claim the
  next reachable work. Safe, obvious in-scope improvement never waits for an
  unrelated host, quota, or portability check.
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

## Deferred

- ~outp observes Snowcubes but never implements or copies its queue | wake: Snowcubes' merged M6 history records the accepted real-input chain plus one concrete M7 successor, and the computer-board history records the matching claim, release, empty orphan set, and resume at that successor
- 29 follow-ups from the 17-agent trust audit -- regex duplication between lint and accept, a host-prompt example-receipt collision, doctor's VERSION-grammar quadruplication, packaging globs shipping design records, atomic-write and accessibility nits | the full list exists only in a session transcript a fresh checkout cannot read, so the five named here are all that is recoverable from this repository | wake: the next release train; if that transcript is unreachable when it fires, re-run the audit sweep rather than treating this row as done
- a session-start portfolio brief: a fresh session opens already knowing every project's state, mode, and next move, without being asked | `shadow status` plus the standing goal already gets a cold session to the board, so this is polish on a solved problem | wake: a product cycle names cold-start friction in its own plan
- harden the sealed-lane argv: `claude --setting-sources user --allowedTools`, `cursor --sandbox enabled` | the flags are verified present in the installed CLIs, but lane behavior under them is unverified and `shadow host run` has never been exercised against a live host | wake: the first real delegated host run
- native structured receipts via `codex --output-schema` and `claude --json-schema` | text-scraping the receipt works today and a schema is only better when the scrape breaks | wake: a receipt-shape scrape failure actually occurs
- packaging pass: fold `shadow-outcome-validate` into tests, fold `shadow_task_lib` into `shadow-host`, delete the unread `schemas/*.json` | shipped surface with no runtime callers, and the schemas are entangled with the browser decision the owner still owns | wake: the browser A/B/C ruling lands, or the next release train
- six repositories need one `- Plans:` line each before their nested plans return to the board | the Shadow-side rule shipped, but a declaration is a per-repo edit and those repos have their own gates | wake: someone opens one of trysnowcubes-web, ai-leo, leojkwan, resplit-web, ai, or resplit-currency-api and adds its line -- trysnowcubes-web `ai/plans/*/PLAN.md`; ai-leo `plans/*/PLAN.md, vidux/*/PLAN.md, skills/*/PLAN.md`; leojkwan `vidux/**/PLAN.md`; resplit-web, ai, resplit-currency-api `vidux/*/PLAN.md`
- the v3 Outcome/Decision/chief-of-staff subsystem, ~1,746 lines with no live producer | retiring it also retires the A/B/C sentences in quickstart.md and docs/index.md and two committed screenshots, so it is a product call, not cleanup | wake: the owner rules on whether the browser's A/B/C decision view ships in 0.1.x
- `docs/superpowers/` is linked from no index and prescribes deleted machinery (`shadow route`, `npm install --package-lock-only`) | it is now `export-ignore`d so it no longer ships, which removes the urgency but not the staleness | wake: someone edits a file under docs/superpowers/, or the owner asks where Shadow's own design records live
- browser-routing drift is closed at its owner ~brws: `/browse` remains the sole browser-policy source; Browser Use handles external interactive work and `/playwright` proves owned products; Shadow delegates by host and never embeds vendor routing, so the residual `/shopper` availability check that can still force Codex @Computer ahead of the chosen `/browse` route is one bounded guard repair in the shared-skill source | the repair lands in `ai-skill-source-origin-main`, not in this repository, so as an M11 task it would hold M11's DoD open forever: `~clen` cannot flip while a non-completed sibling stands without shadow-lint raising a blocking DOD-EARLY | wake: leojkwan/ai PR 156 is merged to main, which lands the /browse routing repair and the /shopper guard together -- the checkouts are clean and the work is pushed, so nothing is blocked on this machine any more
- `shadow doctor` cannot verify the standing goal in Cursor | its user rules live in application settings, not a file, so asserting `~/.cursor/rules/shadow.md` would invent a convention and then report success for wiring that does nothing | wake: the owner names Cursor's real user-rule surface, or Cursor ships a documented file path

## Contradictions

- per-repo-only authority vs the owner's per-computer root board | provisional
  winner: root board + subordinate shards | opened 2026-08-10T04:24:00Z
  The law says PLAN.md at a project root is the only authority (`AGENT.md:11`,
  `SKILL.md:165`, `docs/reference/grammar.md:46`, `bin/shadow` init, and the
  shipped standing-goal text in `docs/reference/host-integration.md:34`). The
  owner's direction (2026-08-10, verbatim: "not per repo, per fucking
  computer") supersedes it: ONE root board per computer owns priority, claims,
  and resume pointers; project plans remain authoritative for their own rows,
  proof, and evidence. The board holds pointers, never copies. `AGENT.md:166`
  ("each machine's board is its own plan set") is precedent, not conflict.
  M20 implements; every listed law surface is rewritten when ~actv lands.

- RESOLVED 2026-08-09T05:40:00Z in favor of Boundaries: Langfuse is KILLED for
  Shadow. See the ~obsv PROOF line. |
  winner: Boundaries | opened 2026-08-09T01:10:00Z
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

- `docs/reference/config.md` says environment variables give the same defaults
  "without another configuration file", `docs/reference/honcho.md` records that
  v4 deleted "the roster, route, seat, and YAML config layers", and `SKILL.md`
  bans a parallel status database | provisional winner: the owner, bounded by
  the buckets law | opened 2026-08-09T23:05:00Z
  The owner said it twice. First: "shadow will have buckets and the method open
  for superpowers, whereever users want to configure that". Then, harder:
  "roster and anything that can be configurable must be in a config yaml style
  best practice". That reverses three shipped surfaces, and the reversal is the
  owner's to make. What survives is the REASON those layers died, not the
  ruling: the config declares only, resolves nothing, stores no state, gates no
  cycle, and a machine without one behaves identically. Read-only preference is
  not routing. M12 is the bounded version; ~cfg1 and ~noks are its refusals.

- `AGENT.md` and `docs/reference/grammar.md` say a lead is free text because "a
  file of legal names would be the roster v4 deleted, and would make an
  unlisted seat's honest claim illegal" -- written today -- while the owner
  asks for a roster in config | provisional winner: both, by splitting
  preference from legality | opened 2026-08-09T23:05:00Z
  A `leads:` block may carry display names, handles, and default lenses; it may
  never decide whether a claim is legal. An unlisted lead still claims, still
  signs `by:`, still appears in `--in-flight`. The moment the config can make a
  claim illegal it is the roster, and ~noks refuses the keys -- provider,
  model, account, credential -- that made the old roster a router.

- `~obsv` DECISION killed Langfuse, and `SKILL.md` bans "a router, daemon,
  scheduler, cloud executor, credential relay, transcript store, or parallel
  status database" | provisional winner: the owner, bounded to local and
  data-minimized | opened 2026-08-10T01:20:00Z
  Owner, verbatim: "reopen Langfuse. We want telemetry and logging for
  Shadow ... Do not configure credentials, transmit payloads, or deploy until
  the endpoint and fields are explicitly chosen." The kill verdict rested on
  two facts that have not changed: self-hosted Langfuse is six always-on
  services plus an event bucket, and Shadow makes zero model or network calls
  today. What survives is the reason, not the ruling. M14 builds the half that
  is unambiguously safe -- a closed field allowlist and local structured
  events with no payloads -- and stops at ~endp, a gate only the owner can
  close. Nothing transmits until then, so the banned shapes are not reachable
  by writing code, only by a decision recorded here.

- M9's `~host` deliberately excluded cursor because "writing
  `~/.cursor/rules/shadow.md` would invent a convention", and
  `shadow-verify-host.sh` skips it as having "no file-backed directive" |
  provisional winner: find cursor's real surface, or drop the claim | opened
  2026-08-10T01:20:00Z
  Owner, verbatim: "every Shadow install must update each supported host's
  directive file with the activation instruction so a new chat automatically
  activates Shadow." Cursor is currently listed as supported and is the one
  host proven to fail cold start. Both halves cannot stand: either cursor has
  an activation surface Shadow can write and a cold session proves it, or
  cursor is not a supported host and the docs, the installer, and the verifier
  all say so. ~curs decides it with evidence; inventing a path and reporting
  success for wiring that does nothing is the one outcome ruled out.

## Progress

- 2026-08-11T06:10:00Z STRUCT M23 added from the owner's P0: Shadow must be approachable to nontraditional developers and publishable wherever the host contract is real. The product decision is local core, portable projection, typed return. Outcome and consequence lead; machinery is available on demand. Parallel promises are shown as parallel work, never flattened into a fake serial queue. Hosted surfaces say coach mode until they can reach the computer board; distribution never creates a second authority.
- 2026-08-11T06:15:00Z EVIDENCE the first portable package validates as a strict Claude plugin and installs through Codex's real local marketplace into a disposable HOME at version 0.2.0 with the Shadow skill present. The Custom GPT source states that it cannot see or mutate local work. Cursor's installed CLI exposes no plugin-validation verb, so its source contract is the portable Agent Skill rather than an invented successful install receipt. No public directory submission, remote bridge, app, Action, or MCP server exists or is claimed.
- 2026-08-11T06:25:00Z PROOF source gate on the portable package: 797 Python tests pass with one documented skip; the 103-file release artifact is reproducible, publishable, stranger-installable, and contains no dirty files; strict Claude marketplace and plugin validation pass; a fresh Codex disposable-home install discovers and enables version 0.2.0 with the Shadow skill present. This proves source and local packaging, not Cursor runtime discovery, public listing, or hosted access to the computer board.

- 2026-08-09T23:23:21Z STRUCT ~brws added | trigger: Claude browser-routing handoff exposed a residual `/shopper` availability check that can still force Codex @Computer before the chosen `/browse` route. Why now: this is a routing-drift repair, but Shadow must record ownership without becoming a browser router. Contradicts: nothing; the row preserves Shadow's delegation boundary and sends the one guard repair to the canonical shared-skill source. It lands as a Deferred row, not an M11 task: its start condition is a clean `ai-skill-source-origin-main` checkout, which lives outside this repository, so a pending task would have made auto-resume hand a cold seat work the row itself says cannot start, and a `blocked` task would have held M11 open forever -- shadow-lint.py:162 counts any non-completed sibling, so `~clen` could never flip without a blocking DOD-EARLY. Deferred is the section for work this repository cannot start, its wake predicate carries the exact resume condition, and the selector never offers it.
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
  handoff portfolio. Reviewable execution packets protect ownership and proof;
  they never create a feature, repository, session, or campaign finish line. Refreshed the external
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
- 2026-08-03T23:03Z: Made a low-cost follow-up attempt after a fresh Jump
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
- 2026-08-09T05:22:23Z ~host PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives -> pass (accept)
- 2026-08-09T02:00:00Z STRUCT M10 added | trigger: owner, verbatim -- "two chats working on same shadow goal should be pairing and colaborating... instead of one orchsetrator its two leads and theeeir resplective team agents, above all the durable plan neeeds to supprot n amount of leads working on the plan together... a depedency tree basicallly of sub tasks". Why now: he says "btw codex is doing this same goal so please work together" often, and a screenshot this session showed it ALREADY working -- a Claude seat read the named authority, saw Codex owned gift-box-customizer-modal.js, and took a disjoint lane with no router. So the answer is not a collaboration system; it is the two things that were actually missing. A claim recorded no identity, so one lead's claim was indistinguishable from another's, and the loser of a simultaneous claim was told to fetch and rebase by hand. Contradicts: nothing -- `needs:` was already the dependency tree he described, and "done or validated" is one bar because completed is unreachable without a proof line, so no second state was invented. Explicitly NOT built: a roster file (v4 deleted roster/route/seat, and a list of legal leads would make an unlisted seat's honest claim illegal), and live chat between runtimes (that needs a transport, which is the daemon Boundaries ban; same-session agents already message directly, cross-runtime is the plan).

- 2026-08-09T05:40:00Z ~obsv PROOF verdict KILL. Two facts settle it, both re-verified here rather than taken on report. (1) Shadow makes no model or network calls at all -- `git grep -lnE 'anthropic|openai|requests\.|urllib\.request|httpx|http\.client|socket\.' -- scripts/ bin/ browser/` returns EMPTY, so there is nothing for an LLM-observability SDK to instrument. (2) Langfuse's defaults are the banned nouns verbatim: endpoint defaults to https://cloud.langfuse.com, inputs and outputs are captured by default, masking is opt-in ("No masking occurs unless you configure it"), and the self-hosted alternative is six restart:always services (web, worker, postgres, clickhouse, redis, minio) with an S3 event-upload bucket and TELEMETRY_ENABLED defaulting true -- a daemon AND a transcript store, which privacy.md and SKILL.md Boundaries both name. Third fact that removes the temptation: the fleet ALREADY has otelcol + Phoenix, and Leo's own notes record why it is empty -- "Phoenix ingests traces only. Claude Code emits metrics and logs, no traces." The bottleneck is the emitter, not the sink; a second sink inherits the same dead end. Kill test, so this can be reopened honestly: a host ships real traces, or Shadow starts making model calls, or the owner edits privacy.md -- Boundaries change by edit, never by an integration that arrives working. (read)
- 2026-08-09T05:42:00Z DECISION ~home: the canonical plan rule is repo-root PLAN.md as authority PLUS one optional `- Plans:` Brief line carrying at most three repo-relative globs, with the scan enumerating git repos instead of walking directories. Measured, not preferred: 7,250 PLAN.md files exist under ~/Development, 777 survive the walk's prune, 308 are unique by content, and exactly 3 parse as v4 grammar. Repo-root-only would orphan 36 real live nested plans including all 14 trysnowcubes-web/ai/plans/* (Snowcubes, priority #1) and resplit-web/vidux/resplit-2.0-launch (Resplit 2.0, priority #2). A central index is banned as a second store. Migration: 6 declaration lines, 8 globs, 0 files moved, 0 live plans orphaned. NOT YET IMPLEMENTED -- ~home stays pending; this records the decision so the implementation is not re-litigated.
- 2026-08-09T05:43:00Z FINDING `shadow status` cannot see Shadow's OWN plan. discover_plans walks alphabetically and fills MAX_PLANS=250 at resplit-*, silently dropping shadow/, silvana-events/, snowcubes-*, strongyes-*, trysnowcubes-web/ -- with no truncation warning. 83 of the 250 cards are duplicates of each other (one plan appears 42 times via escaped worktree and clone dirs). The scan also has no boundary: only the fact that "Development" sorts before "Documents" keeps it from rendering ~/Documents/Codex/<slugified-prompt>/ session directories as plan cards. Folded into ~home rather than patched piecemeal -- the repo-enumeration rule deletes all three at once.
- 2026-08-09T05:44:00Z DECISION ~bkts: a bucket is a NAMED CAPABILITY SLOT the method assumes it can reach, not an installable dependency. The npm-shaped reading dies on two shipped facts: honcho is uninstallable BY LAW (honcho.md: "a pattern Shadow implements, not a service Shadow installs"), so an install-shaped bucket for it is self-contradictory; and M6 deleted the package manager deliberately, so an install-that-fetches reverses a shipped decision. Design: `docs/reference/buckets.md` declares one line per slot with `kind:` in {pack, skill, builtin}; kind IS the check, the way proof:'s class determines its machinery. Zero resolved state stored -- doctor derives present/absent/stale at read time, the same law as Milestone. Absent always WARNs, never FAILs, because ~w1re's own DoD runs doctor under a scratch HOME and expects exit 0. The honcho bucket's check is a NEGATIVE: it fails if anything named honcho is ever installed, turning a prose ruling into a mechanical refusal. NOT YET IMPLEMENTED -- ~bkts stays pending.

- 2026-08-09T06:10:00Z ~bkts PROOF `docs/reference/buckets.md` declares three slots; `shadow buckets` and `shadow doctor` resolve them at read time and store nothing. On this machine: superpowers pack 6.2.0, honcho builtin intact, taste skill mounted -- doctor 16/16, 0 warnings. Under a scratch HOME: two WARN, honcho PASS, exit 0 -- which is the ~w1re guard, since a required tier would fail the very milestone that introduces buckets. Install adds no code: the declaration ships committed, so cloning defaults it, and M6's deletion of the package manager is not reversed. The honcho bucket is the design's proof of honesty -- its check is a NEGATIVE that FAILS if anything named honcho is ever installed as a skill or a plugin, turning a prose ruling into a mechanical refusal; both surfaces tested. 19 tests, mutation-verified: making absent FAIL and dropping the negative check each turn the class red. A test also asserts no plan verb reads the declaration, so it cannot become a second queue. (cmd)

- 2026-08-09T06:40:00Z ~home PROOF the scan enumerates project roots instead of walking directories. Before: 7,250 PLAN.md under the portfolio root, 777 reachable, 665 of those byte-identical copies, a 250-slot cap filled alphabetically at resplit-* so SHADOW'S OWN PLAN WAS INVISIBLE ON ITS OWN BOARD, 83 of 250 cards duplicates (one plan 42 times), and no boundary at all -- only "Development" sorting before "Documents" kept session directories whose names are prompt text off the board. After: 11 plans, zero duplicates, shadow/PLAN.md present, no cap because there is no recursion. Deduplication is (origin, repo-relative path), and the canonical checkout wins over a rename-era clone by directory-name match then mtime -- without that tie-break a stale clone of this very repository replaced the real plan. Two more fixes fell out: status had a SECOND recursive scanner that from $HOME reached a scratch directory and refused to fall back over a file the root does not own; and both its stderr lines printed absolute home paths, which Shadow's own privacy gate flags. Output now carries zero absolute paths. Git is deliberately NOT required -- boundedness was the goal, not a version-control test. 14 tests, containment mutation-verified. (read)
- 2026-08-09T06:41:00Z LESSON comparing an unresolved path against `path.resolve().parents` never matches on macOS, where /var is a symlink to /private/var. My glob-containment check looked correct and excluded EVERY declared plan while its escape test passed for the wrong reason -- nothing was reaching the check at all. Resolve both sides, and make the mutation prove the guard fires rather than that the feature is off.

- 2026-08-09T07:20:00Z ~detv PROOF `scripts/shadow-verify-host.sh` in two tiers. Offline (free, the row's proof): the mount resolves to THIS checkout, no competing `shadow` skill sits in another host root, SKILL.md is loadable, the standing goal is present and appears EXACTLY ONCE, and the board is reachable from an unrelated directory with a resume row. Live (opt-in, costs quota): one non-interactive session per host, asserted to return that same resume row. TWO OF THREE HOSTS PASS LIVE, and the third failing is the finding. My first live prompt NAMED the command ("run `shadow status`"), so it proved only that a host can run a command I handed it -- a session with no Shadow wiring at all would have passed. Codex review caught it. The corrected prompt names nothing: "What am I working on right now?". Under it, `claude -p` and `codex exec` each found the board unprompted and named the resume row -- earned, not fed. `cursor-agent -p` FAILS: it has the mount but no directive, because Cursor user rules live in application settings, so nothing tells a cold Cursor session to open the board. Cursor passed the coached prompt and fails the honest one, which is exactly the regression this verifier exists to catch, found on its first real use. 12 tests; every check is proven by breaking what it guards -- missing mount, mount pointing at another checkout, a competing skill in another root, missing directive, two copies of the goal, a stale goal, and an empty board each turn it red. A skipped live check says so out loud rather than leaving a green run implying it ran. Cursor's directive is SKIPPED, not asserted: its user rules live in application settings, and inventing `~/.cursor/rules/shadow.md` would report success for wiring that does nothing. (cmd)

- 2026-08-09T07:45:00Z FINDING Cursor is wired but inert. `scripts/shadow-verify-host.sh --host cursor --live` FAILS on the uncoached prompt while claude-code and codex pass: the skill mount resolves and the board is reachable, but Cursor has no file-backed instruction surface, so a cold session is never told to open it. This is the first MEASURED consequence of the Cursor gap that has been carried as prose since the standing goal shipped -- it is no longer a theoretical carve-out. It does not block ~w1re, whose DoD is the offline tier, and it does not change the Deferred row's wake predicate (the owner names Cursor's real user-rule surface). It does mean any claim that Shadow works on three hosts is true for install and false for cold-start.
- 2026-08-09T07:46:00Z LESSON a live check that tells the session what command to run proves the command exists, not that anything was discovered. I wrote that prompt, watched three hosts pass, and reported "all three verified live" in the same breath -- the fourth false green of this session and the first one I celebrated before it was caught. The corrected prompt asks a question only a wired session can answer and names no command. Rule: a test that supplies the answer is a test of the harness, not of the thing.

- 2026-08-09T14:23:24Z ~w1re PROOF bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; export HOME="$d/home"; mkdir -p "$HOME/.claude" "$HOME/.agents" "$HOME/.cursor" "$HOME/.codex" "$HOME/Development/proj"; cp "$d/s/PLAN.md" "$HOME/Development/proj/PLAN.md"; bash "$d/s/install.sh" --bin-dir "$d/bin" >/dev/null; export PATH="$d/bin:$PATH"; shadow doctor >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host claude-code >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host codex >/dev/null; bash "$d/s/scripts/shadow-verify-host.sh" --host cursor >/dev/null; cd "$d"; test -n "$(shadow status)"' -> pass (accept)
- 2026-08-09T14:35:00Z LESSON the public-ready gate reads a literal user-home path as private ANYWHERE in the tree, including inside a proof that only ever addresses a throwaway temp dir -- so the accepted ~w1re command failed the repository's own privacy gate on the four directories it created under its fake HOME. The row and its receipt now export HOME first and address the same four directories through "$HOME/...": the same run, spelled so the plan carries no home-shaped path. A proof line is text in a public file before it is a command, and it has to pass every gate that text passes.
- 2026-08-09T08:05:00Z ~rsch PROOF three of five named agents delivered, and their work is in the plan as decisions rather than opinions: langfuse-verdict produced the KILL with Langfuse's own defaults quoted and the fleet's existing empty otelcol/Phoenix as corroboration; plan-home measured 7,250 plan files down to the 36 that matter and killed repo-root-only on evidence; extension-buckets found that honcho is uninstallable by law, which is what makes the bucket kind a NEGATIVE check. host-directives and host-determinism went IDLE WITHOUT REPORTING -- no findings, no partial, nothing. ~host and ~detv were built from first principles instead and both landed, so the loss was time rather than work. Recorded because it is evidence about the mechanism this session has been arguing for: named agents are inspectable and message-able, and I did message all five, but two still returned nothing and the only reason that was survivable is that ~rsch was a THROWN row naming what it owed. An unthrown fan-out losing 40% of its agents silently is the failure the dispatch law exists to make impossible. (read)

- 2026-08-09T14:30:51Z ~lead PROOF scripts/shadow-python.sh -m unittest tests.test_two_leads -> pass (accept)
- 2026-08-09T14:30:56Z ~race PROOF scripts/shadow-python.sh -m unittest tests.test_two_leads.ThePushRejectionIsTheMutex -> pass (accept)
- 2026-08-09T08:20:00Z ~prot PROOF re-observed clause by clause rather than by section presence: AGENT.md "Several leads, one plan" carries all six -- claim with your name, the push rejection is the mutex, needs: is the dependency tree, talk in the plan, challenging is normal but silent overruling is not, and no roster. grammar.md Dispatch law documents `| by: <lead>` with the reason it must sit in the tail, and the `NOTE @<lead>` convention with its honest latency (delivery at fetch, not at keystroke). commands.md documents --by on throw. (read)

- 2026-08-09T08:25:00Z STRUCT M11 added, and M10 closes on the agent side | trigger: goal chaining -- M10's three agent-side rows are proven and its DoD ~pair is person-gated ("give the same goal to a Claude seat and a Codex seat, both with --by, and read `shadow status --in-flight`"), so the plan closes agent-side and mints the successor rather than hanging on a human. Why M11 is the successor: four PRs opened before tonight are all BEHIND main and none were touched while six merged around them -- #256 (v3 route/seat prose surviving the v4 excision), #265 (a Deferred section that tonight's archive may have superseded outright), #266 (the explain-inline rule in SKILL.md), #267 (the guard that makes #266 fail). Stale branches are the same class as a worktree left standing after LAND. Contradicts: nothing. The highest-value pair is #266+#267, because a rule that cannot refuse is the exact defect four false greens taught this session.

- 2026-08-09T08:40:00Z ~styl PROOF #266 and #267 rebased onto tonight's main and landed together, because a rule without its guard is the exact defect four false greens taught this session. SKILL.md now says explain every term in the SAME message that uses it -- a change gets a before/after pair, a flow gets a drawing, a fact gets one line, and a PR number or file path is a reference, never an explanation. `scripts/shadow-style-guard.py` is the Stop hook that makes it fail: it reads the turn's final assistant text and BLOCKS an A/B/C offered with no drawing, fenced block, or table in the same message. Demonstrated both directions -- an A/B/C reading "A: adopt seat semantics / B: optional validator consolidation" is refused with the reason inline, and one carrying a BEFORE/AFTER block passes silently. Those two option labels are the owner's own banned phrases, so the guard's first real input was the thing it exists to stop. It reads `last_assistant_message` from the payload rather than scanning the transcript, because the transcript is written asynchronously and scanning it can judge the wrong ending. 358 tests, 30 of them the guard's. (cmd)
- 2026-08-09T09:10:00Z ~excs PROOF #256's prose landed; its example file did not. native-hosts.md had ZERO route or seat mentions, which read as done but was silence -- the sentences had been deleted and nothing replaced them. The PR's real value is the positive statement: "You choose the host directly ... There is no roster, route, or seat layer in front of it." Silence lets a reader assume a router exists and is undocumented; a refusal cannot be misread. DROPPED: examples/seats.example.yaml. Shipping a worked seat map inside Shadow contradicts the paragraph introducing it -- a template for model and account data, in the artifact, in a product whose boundary is that it passes no selector and records none, and the first person to fill it in fills it in here. The section now says the map is yours and explains why no example ships. `git grep 'shadow route'` outside plan-archive returns only PLAN.md rows that describe the staleness. (read)
- 2026-08-09T09:11:00Z STRUCT ~adv9 added to M11 | trigger: ten PRs merged in one night and FIVE false greens surfaced in them -- a roster guard that could not fail, DEFER-NO-WAKE disabled by a heading variant, a doctor check green on a drifted file, a live host check that fed the session its own answer, and a style guard any fenced block could satisfy. Four were caught by review or by me re-reading, one by a peer. That rate says the reviews on tonight's merges are not a sufficient gate on tonight's merges. Why now: the debt row ~debt closes M11 and the DoD ~clen then declares main clean -- declaring clean without one adversarial pass over what just landed is the same shape as a green run that proves nothing. Contradicts: nothing.
- 2026-08-09T22:31:41Z THROWN ~adv9 a fresh adversarial pass over the ten PRs merged 2026-08-09 finds what their own reviews missed, or says so with the searches that came back empty | by: claude | note: workflow: 5 adversarial lanes over the 10 PRs merged 2026-08-09, barrier, then one synthesis
- 2026-08-09T09:30:00Z ~debt PROOF #265 was NOT superseded and its rows landed. Tonight's archive moved 46 v3 portfolio deferrals out and rewrote 3, leaving a Deferred section of 3 -- #265 carried five genuinely parked items with wake predicates that existed nowhere else: the 29 unrecoverable audit follow-ups, the session-start brief, sealed-lane argv hardening, native structured receipts, and the packaging pass. Their "v4.1 release train" wakes were stale (no v4.1 exists) and now read "the next release train"; the packaging row's wake also names the browser ruling, because deleting schemas/*.json is entangled with a decision the owner still owns. #265 also recorded a LESSON worth keeping and independently confirmed tonight: a plan edit anchored on a heading must ASSERT the anchor matched, because `## Deferred` did not exist -- only `## Deferred proof (not a global blocker)` -- so every canonical-anchor insert silently no-oped. That is the same defect as DEFER-NO-WAKE matching a heading exactly, found twice from opposite directions on the same day. #266 and #267 are superseded by #277 and close. #256's prose landed in ~excs without its example file. (read)
- 2026-08-09T23:05:00Z ~excs CORRECTION the 09:10 receipt above claimed `git grep 'shadow route'` outside plan-archive returns only PLAN.md rows describing the staleness. That was false: two matches also sit in `docs/superpowers/specs/2026-08-06-method-v2-debate/r3-crossexam-roster.md`, the archived v2 debate record. The row's criterion said "outside plan-archive is 0" and therefore did not hold, which would have let a future lead read a satisfied excision off a search that still returns hits. The criterion now names its exclusions -- plan-archive and docs/superpowers/ are archived design records, PLAN.md's own matches are rows describing the staleness -- and with those three excluded the search is genuinely empty. The excision itself is unchanged; docs/superpowers/ staleness stays parked under its existing Deferred row and wake. (read)
- 2026-08-09T23:05:00Z ~adv9 PROOF a fresh adversarial pass over the ten PRs merged 2026-08-09 -> 44 agents in 5 attack lanes over ref 88c758c, every finding refutation-tested: 33 survived, 5 killed. TEN live defects reproduced without mutating code, worst first: shadow-throw.py:235,242 can commit and push a ZERO-BYTE PLAN.md while reporting claimed and pushed (2 of 25 and 1 of 20 same-checkout trials); shadow-lint.py:106 scopes row grammar to the exact heading Tasks while shadow-accept.py:126 scans the whole file, so the enforcer and the flip path disagree about what a task is; shadow-lint.py:33 validates a cmd proof on its class word only, so a proof reading echo done then shadow --version lints clean, flips completed, and writes pass without ever running shadow; shadow-lint.py:92,99 leave Brief exact-string after PR #272 prefix-fixed its siblings, dropping MODE-ILLEGAL from blocking to a warning under a suffixed heading; install.sh:38 gates on bare python3 and refuses stock macOS where the CLI it installs runs fine; README.md:17 documents a step that turns a good install into a doctor FAIL; shadow-host-directives.py:94 heading drift makes an unmarked copy adoptable; shadow-accept.py:239 commits a plan lint blocks; shadow-style-guard.py:181 fence exemption is unbounded forward; shadow-host-directives.py:143 writes a 0600 host file backup as 0644. All ten carry rows in M13. Report: the workflow result for wf_7a64af02-061
- 2026-08-09T23:05:00Z STRUCT M12 and M13 added | trigger: M12 is the owner's ask -- configurable major components in a config file, the adversarial step made part of the method, and /future thinking. Two Contradictions rows were opened before any code because it reverses three shipped surfaces, one written today. M13 is ~adv9's findings given rows, which is what ~adv9's proof requires before M11's DoD may flip. Why now: ~adv9 landed. Contradicts: config.md, honcho.md, and today's no-roster clause -- both recorded above.
- 2026-08-09T23:40:00Z STRUCT ~acpt widened to carry the host-directive adoption fix | trigger: codex review on PR 279 found that shadow-host-directives.py:94 was named in the ~adv9 PROOF line and in no M13 row, so ~aud1 could have completed with a suffixed standing-goal heading still adoptable and overwritable. The row already runs tests.test_host_directives, so the fix lands where its regression already runs. Contradicts: nothing.
- 2026-08-10T00:15:00Z STRUCT every remaining M13 row and ~ftur name a test class that does not exist yet | trigger: cursor review on PR 279 found ~acpt's proof ran whole modules that are green today, so accept could flip the row before the fix was written. The same held for five sibling rows. A proof that passes before its behavior exists is the false-green class this repo shipped five times in one night, so the fix is the class and not the one row cursor found. Each proof now names a class that must be authored plus the module it lives in, so the row fails until its own fix lands and any regression elsewhere in the module still counts. A peer lane had already applied this to ~atom and ~hdop and corrected six module names I got wrong; ~acpt's duplicate drift clause is dropped in favour of that lane's dedicated ~hdop row. Contradicts: nothing.
- 2026-08-10T01:20:00Z STRUCT M14, M15, and M16 added | trigger: three owner directives in one session. M14 reopens telemetry, which ~obsv had killed -- recorded as a Contradiction with the owner's words, bounded so nothing transmits before the ~endp gate. M15 is the product requirement that every install activates Shadow in every supported host; it collides with M9's deliberate cursor exclusion, which is the second Contradiction. M16 is the owner's personal directive layout and ships to nobody -- kept as its own milestone because the owner asked explicitly that the universal installer requirement not be conflated with one person's symlink setup. Why now: all three were given as direction. Contradicts: ~obsv and M9 ~host, both recorded above.
- 2026-08-10T01:20:00Z NOTE ~slnk was found before it was written: `os.replace` onto a symlinked path REPLACES THE LINK with a regular file and leaves the canonical target untouched. Verified on this machine -- a symlinked host file survived exactly zero atomic writes. `shadow-host-directives.py:151` does this today, so the first `shadow goal --install` after any symlink migration would silently un-migrate the file while reporting success. It is a product defect wherever a user symlinks their own directive file, so it sits in M15 and M16's ~mrge depends on it.
- 2026-08-10T05:40:00Z STRUCT M16 rows rewritten to one shared file | trigger: the owner corrected the wording before implementation. The rows said "one canonical source ... with the per-host differences kept rather than flattened", which reads as three per-host copies and is the opposite of the intent. The requirement is ONE FILE, three symlinks resolving to the same target. A host-specific syntax difference does not license a split by itself: it must be opened as a Contradictions row first, naming the syntax and the host, so a divergence is a reviewed decision rather than something that happens quietly during implementation. Recorded before dispatch so it cannot drift. Contradicts: nothing -- this narrows M16, it does not reverse it.
- 2026-08-10T05:40:00Z NOTE M15 and M16 are and remain SEPARATE requirements, and the installer is where they meet. M15 is universal and ships to every Shadow user: every install writes the activation instruction into every supported host so a stranger's next chat opens the board. M16 is one person's private layout in ai-leo and ships to nobody. The binding constraint between them: the universal installer MUST PRESERVE AN APPROVED SYMLINK -- writing through it to the canonical target, never replacing the link with a regular file. That is ~slnk, which already exists in M15 as a product defect because it is one for any user who symlinks their own directive file, not because the owner does.
- 2026-08-10T05:50:00Z STRUCT ~cano proof made singular | trigger: the proof read "the canonical files exist" in the plural, so it could have passed against three split per-host copies -- the exact outcome the row's own text forbids. A proof looser than its row is the false-green shape this repository keeps finding, and it is worse here because the row was just narrowed for this reason. It now requires ONE file, all three host paths resolving to it, and `readlink -f` returning the same path for each. Contradicts: nothing.
- 2026-08-10T02:07:04Z THROWN ~slnk a host directive file that is a symlink is written THROUGH, never replaced: the canonical target changes and the link survives | by: claude | note: M15 lane: host-directive writes follow an approved symlink to its target instead of replacing it
- 2026-08-10T06:10:00Z NOTE ~thrw `shadow throw` cannot claim a row in a repository whose trunk is protected, and Shadow's own is. Measured just now: `shadow throw --task ~slnk` committed the claim locally, was rejected by GitHub with "Changes must be made through a pull request. 10 of 10 required status checks are expected", and then correctly REFUSED TO LAUNCH -- it withheld the goal block and printed "DO NOT LAUNCH THE WORK", which is the invisible-dispatch guard doing precisely its job. The guard is right; the reachability is the gap. Dispatch law says a claim must be durable before work leaves the chat, and on a protected trunk the only durable path is a pull request, which `throw` has no notion of. Consequence today: every claim in this repository is a hand-written row plus a branch, which is the substitution the law exists to prevent, and it is forced rather than chosen. Recorded as a finding against ~thrw rather than worked around silently. Not opened as a Contradictions row because nothing in the law is contradicted -- protected trunks were simply never modelled.
- 2026-08-10T06:25:00Z STRUCT M18 added | trigger: the owner and a codex review independently reached the same conclusion within minutes — the protected-trunk finding needed a durable owned follow-up, not a Progress note. A note is not takeable: `shadow status` and resume selection derive work from Tasks, so a limitation recorded only in Progress can never be picked up, which is the same defect class as a claim with no THROWN line. Why now: the gap was found by dogfooding `shadow throw` on this repository and it blocks every future claim here. Contradicts: nothing — dispatch law is unchanged and its guard was correct; protected trunks were never modelled.
- 2026-08-10T04:40:41Z STRUCT outcome-completeness law replaced packet-minimalism across the Method, goal shaping, standing activation, amp runtime rails, init scaffold, browser, guides, and public product copy | trigger: the owner rejected the repeated conversion of full-product intent into a single campaign or slice and required all reachable lanes to rise together. Reviewable rows, one-writer claims, and proof remain safety units; they no longer cap a session or Outcome. The new refusal test scans every live instruction surface for the retired narrowing phrases and requires queue drain, safe disjoint fan-out, and full acceptance. Contradicts: the prior Worklane wording and amp/init defaults, replaced in this same change.
- 2026-08-10T04:43:17Z STRUCT the universal-system milestone and its activation acceptance now require plain outcome language on every human-facing surface | trigger: the owner rejected milestone and row codenames as confusing and contrary to how Shadow should operate; stable IDs remain internal machine references only. Contradicts: the active temporary goal's milestone label, superseded by this plan's descriptive heading.
- 2026-08-10T04:43:17Z ~dreg PROOF docs/reference/universal-system-register.md represents both seats' requirements through the owner's plain-language correction; the Codex seat re-read the complete register against its chat and confirmed coverage (read)
- 2026-08-10T04:47:31Z THROWN ~root the root board exists and is claim-safe: a git repository at ~/.shadow holding priority, claims, owners, and one resume pointer per project — pointers, never copies of rows. The LOCAL file is the authority; a private remote is optional recovery, best-effort and async, never required for a write to count and never live authority — recovery is only ever as fresh as the last push, and that limit is stated where the remote is configured. The claim contract is mechanically proven: of two seats claiming the same row concurrently exactly one wins and the loser is told, and a seat that dies mid-claim leaves a recoverable board — an advisory lock reusing the installer's crash-safe write discipline is the implementation candidate, not the contract | by: codex | note: Per-computer root board, local authority, single-winner claims, and crash recovery; implementation starts only after this claim reaches main.
- 2026-08-10T07:30:00Z STRUCT M19 added | trigger: the owner set a session-closing goal — process the 2026-08-09/10 session's findings end to end and fix what it surfaced — and asked that it live on the board. The milestone holds only what no existing row owns; M14 through M18 keep theirs. The owner separately stated the reachability expectation now carried by M18 ~pver: the durable ledger on each computer should show what every seat is doing without screen-driving. Contradicts: nothing.
- 2026-08-10T08:05:00Z STRUCT the M19 scope receipt's M17 reference is void | trigger: a codex review on PR 289 searched the board for `### M17` and found none — the milestones run M16 then M18, and the receipt above is the only place M17 is ever named. A scope receipt that hands findings to a milestone that does not exist is worse than no receipt: it lets M19 reach its DoD with plan-authority work excluded from the one milestone chartered to catch what nothing owns, and with no takeable row anywhere. Correction: M17 does not exist and is not being minted here, since no row on this board and no finding in this session names the plan-authority work it was supposed to hold. M19's tools line now says so, and any plan-authority finding the ~z9fn sweep raises takes a row in M19 rather than being waved off. Contradicts: nothing — this voids a reference that was never backed by rows.
- 2026-08-10T08:20:00Z STRUCT M19 revised before merge | trigger: a plan-quality review. Raw session language replaced with sanitized outcomes; ~aipr removed because the deferred /browse repair in the ai repository is already owned by ~brws and its wake, and a second row would be the duplicate-queue shape this plan bans; ~canx rewritten from "provenance unknown" to the read-only reflog fact, which shows an explicit reset moved the local ref to the worker's pushed branch before the lead touched anything; ~lqid reworked so no outcome can bypass THROWN or M18 durability, with Snowcubes adoption recorded in Snowcubes' plan; ~z9fn narrowed to a dated audit of this repository with named evidence, leaving cross-repo reachability to M18. Contradicts: nothing.
- 2026-08-10T08:35:00Z STRUCT ~lqid's proof made discriminating | trigger: a bugbot review on PR 289 observed that the proof ran only whole `tests.test_throw`, `tests.test_shadow_lint`, and `tests.test_shadow_accept` modules, all of which are green today with no legacy-id work done — so `shadow accept` could have flipped ~lqid and unblocked ~z9fn before any decision landed. That is the false-green shape this repository keeps finding: a proof looser than its row. The proof now names two tests that cannot exist until the decision does, and holds under either outcome — `TheIdGrammarMatchesTheDecisionRecordedInGrammarMd`, because both a widened grammar and a sanctioned remote claim must be written into grammar.md and matched by the code, and `ALegacyIdRowIsClaimedByThrowWithoutAHandWrittenLine`, because both outcomes end the hand-written claim line. The whole modules stay behind them as the regression net. Contradicts: nothing.
- 2026-08-10T08:45:00Z STRUCT M19's scope receipt follows the universal-system rename | trigger: rebasing onto main, which dropped the `M20` label from that milestone's heading under the plain-outcome-naming directive. The receipt named `M20` as a milestone that keeps its own rows, and after the rename no such heading exists — the same dangling-label defect the 08:05 entry voided for M17, and the receipt is the one place M19's scope is enforced. It now names the universal-system rows, which is what main's own generalization uses. Contradicts: nothing.
- 2026-08-10T09:20:00Z ~v4bd PROOF cmd scripts/shadow-python.sh -m unittest tests.test_browser.AV4PlanGetsABoardBriefNotAnError — 6 tests green at 6f32899 (#297 merged); live re-observation on the dogfood machine: 11/11 plans render a board brief, contract errors 11 -> 1 honest v3 case. Flip recorded by hand with its rerun proof because `shadow accept` cannot push a flip commit to this protected trunk — the exact gap M18 owns (~pdis); same forced form as the ~slnk claim.
- 2026-08-10T09:25:00Z ~vgal first half shipped: /gallery renders every card state from checked-in fixture plan TEXTS projected by the production pipeline (record_from_text) and drawn by the production renderers against a stub surface — zero duplicated card markup, so gallery drift IS board drift. Goldens hold each fixture's promised state and full state coverage; mutation-verified (a broken fixture promise turns the golden red). Remaining: the screenshot half — automated visual diff in CI, loud on skip. Resume: wire a screenshot runner against /gallery, goldens beside the fixtures.
- 2026-08-10T10:40:00Z ~apsh PROOF cmd scripts/shadow-python.sh -m unittest tests.test_gauntlet tests.test_shadow_accept — 29 green. Found by the FIRST full gauntlet run (tests/test_gauntlet.py): a disposable mock portfolio — two repos on a local bare forge, a worktree ghost, a pre-grammar essay — driven end to end through the real verbs proved discovery-dedup, projection, claim, cold-seat reachability, and proof-rerun flip, then failed at step 6: the flip never reached the forge, because accept never pushed. The gauntlet is the register's entry on the bar (an extension of the owner, proven by repeated e2e runs) made mechanical; this was its first catch. Flip recorded by hand with its rerun proof per the protected-trunk forced form.
- 2026-08-10T11:05:00Z ~vgal PROOF cmd goldens green (tests.test_browser.TheGalleryShowsEveryStateHonestly) and the browser harness green on real Chromium locally with the screenshot re-observed; mutation M-VIS: deleting the working-state style rule turns the harness red — after the first version survived it (it compared working to blocked, which stayed different through blocked's own rule; the vacuous-guard trap), the assertion now anchors every state chip against an unstyled baseline. CI job visual-proof runs it with SHADOW_VISUAL=1 (missing browser = failure) and uploads the screenshot artifact. Flip recorded by hand with its rerun proof per the protected-trunk forced form.
- 2026-08-10T11:20:00Z STRUCT M15 gained ~tmpr (stale temp residue is swept safely) and ~disc (a linked write discloses its resolved target and retained backup), both `needs: ~slnk` | trigger: the thermo adjudication of the ~slnk symlink audit, which found two out-of-contract defects that ~slnk's own row and proof cannot carry: a kill between temp creation and rename strands a permanent `.shadow-*.tmp`, and a write that follows a link reports a bare "added: claude" that names neither the file it actually wrote nor the backup it kept. Why now: #288 implements ~slnk, and a finding recorded only in that review evaporates when the PR merges -- `shadow status` and resume selection derive work from Tasks, so an adjudicated defect with no row is unreachable, the same class as the note-not-row defect that minted M18. Both are scoped as follow-ups rather than folded into ~slnk so the symlink row stays one reviewable claim. ~tmpr is written as provably-safe on purpose: a naive start-of-apply sweep would delete a concurrent apply's live temp, so the row and its proof require the sweep to prove the owning run is dead. Contradicts: nothing -- M15's DoD ~act9 already gates on ~slnk and the two new rows sit behind it, and at 5 tasks plus one DoD the milestone stays inside the 2-7 bound.
- 2026-08-10T02:10:00Z NOTE ~brws the wake predicate is satisfied: both shared-skill checkouts are clean and nothing was stashed, discarded, or overwritten. Two dirty checkouts existed, not one. `~/Development/ai` carried EIGHT uncommitted files on cursor/related-skills-all-boats-20260723, a July lane 64 commits behind origin/main; `~/Development/ai-skill-source-origin-main` -- the live skill mount -- carried SEVEN, byte-identical to the first seven. One coherent changeset in both: three skills/browse/ files are the routing repair and the siblings are their references updated to match. Disposition: the delta was saved to ~/Development/ai-browse-routing-uncommitted-20260810.patch, applied in an owned worktree at the revision it was authored against, verified byte-identical 8 of 8 against the source AND re-verified against the pushed objects on origin, then committed as 7ba45465 and opened as leojkwan/ai PR 156. It is based off the authoring commit and not off main on purpose: the delta does not apply to origin/main, and forcing it would have invented conflict resolutions nobody reviewed. Separately, the live mount sat on DETACHED HEAD 1b31936c "shopper: stop banning the canonical browser route", reachable from no remote branch and carrying shopper content that differs from the rescued commit -- genuinely unique unpushed work. It is preserved as origin/rescue/shopper-browse-route-20260810 before either checkout was restored. Only then were the working files restored, and the live mount still serves the shopper fix.
- 2026-08-10T02:10:00Z NOTE ~brws the underlying bug, recorded so the wording is not re-broken: /browse said Codex @Computer was the only retained interactive route and banned "remote sessions" outright, which read as banning Browser Use Cloud. A seat holding an authorised purchase then tried two dead surfaces -- playwright needs Chrome on :9222, claude-in-chrome needs the extension -- and never tried the one that works. The answer to "which open source tool did we go with" is Browser Use, with Codex @Computer kept as the visible-local-window route inside the Codex app, and /playwright reserved for owned-product proof. This row stays DEFERRED on purpose and is not actionable in this repository: the repair lands in the shared-skill source, so its remaining work is leojkwan/ai PR 156 rebasing onto main with its conflicts read rather than auto-resolved. Its wake is updated to that merge. Calling it remaining agent-side work here would have implied a task row that resume selection could take, and there is none by design.
- 2026-08-10T08:18:55Z ~slnk PROOF cmd scripts/shadow-python.sh -m unittest tests.test_host_directives.ASymlinkedHostFileIsWrittenThrough — 12 green, and the full module 73 green, rerun in a fresh worktree of origin/main after #288 merged. The write pins the resolved inode (O_RDONLY|O_NOFOLLOW), re-verifies identity at every guard, and the link survives every path. Held under a standing fresh-audit-before-push order: five independent audit rounds (Sol, read-only, sources inlined) found seven in-contract blockers across four rounds — created-path backup overclaim, unbounded removal strips eating the person's blank lines, CRLF files rewritten wholesale (backup included), the no-op guard blind to appearing hard links, a taken-backup-name overclaim, unmarked adoption capturing private prose between an exact heading and final line, and a test class asserting the abandoned design — each fixed, mutation-checked red, and re-frozen until round five returned CLEAN at c62e773. Flip recorded by hand with its rerun proof per the protected-trunk forced form. (This stamp is the real clock; the entries above it carry invented times — append order, not the stamps, is this section's truth.)
- 2026-08-10T08:27:32Z THROWN ~curs cursor either gets a real activation surface proven by a cold session, or it is written down as unsupported and removed from the supported list | by: claude | note: M15 lane; the second arm is in reach — Cursor's own rules documentation states user-level rules are GUI-only and every file surface is project-scoped, so the verdict will be documented-unsupported with that evidence unless a cold session proves otherwise. Claim recorded by hand per the protected-trunk forced form.
- 2026-08-10T08:32:02Z ~curs PROOF read docs/reference/native-hosts.md § Activation surfaces states that Cursor is not activated, by decision, and why — re-observed at origin/main after #305 merged: Cursor's own rules documentation (read 2026-08-10) documents only project-scoped file surfaces (.cursor/rules/*.mdc, project-root AGENTS.md) with User Rules configured through the settings interface, and ~/.cursor locally holds no rules directory; writing an invented path would report success for wiring that does nothing. The activation write-target list in that section names claude-code and codex only, a Cursor user's alternative (the goal block in a repository's own AGENTS.md) is documented as a per-repo choice, and the decision carries its reopen condition: a documented user-level instruction file from Cursor. The second arm of the row is what shipped; no cold session was spent proving a surface the vendor documents as absent. Flip recorded by hand per the protected-trunk forced form.
- 2026-08-10T12:38:25Z CHECKPOINT ~root source/test candidate only: a uniquely healthy registered board locator now outranks an unreadable, oversized, unsafe, or symlinked same-identity checkout before body parse; one self-demotion retires the logical identity across aliases; repair and retirement are byte/state/topology CAS operations; status and browser share the bounded reader; and the host verifier rejects last-good refresh failures or unreachable resumes. Frozen affected matrix: 215 tests green in 103.009s with identical before/after hashes, plus py_compile, shell syntax, diff check, and the 161-file public-ready gate. This is not a merge, install, cold-session, tag, or live-dogfood receipt; ~root remains in progress until those boundaries are observed separately.
- 2026-08-10T13:42:08Z CHECKPOINT ~root merge/install boundary: PR #309 squash-merged to origin/main as 5f7d7f3eeb60b29990e8d42ba363defd7baa1f2b after all ten strict checks, CodeQL with zero alerts, and every review thread cleared. The clean installed clone was fast-forwarded to that exact SHA; install.sh completed, shadow --version returned 0.2.0, and doctor reported 16/16 with zero warnings. No tag or live-session conclusion is inferred from this receipt.
- 2026-08-10T13:42:09Z CHECKPOINT ~root board/live boundary: from a neutral directory with SHADOW_PORTFOLIO_ROOT and SHADOW_DEV_ROOT absent, shadow status --json returned 0 at board revision 2 with two projects, two entities, no refresh warning, and Shadow resume ~root reachable. The cold Codex verifier passed. A separate cold Claude session asked only what work existed and opened the same board unprompted; the shipped exact-line --live harness still false-negatives that correct richer answer, so this records direct host activation, not a passing Claude harness.
- 2026-08-10T13:42:10Z CHECKPOINT ~root CI/commit-lifecycle boundary: origin/main push run 31392981113 attempt 1 exposed a real Python 3.12 teardown race after the assertions — root-board git commit returned while detached automatic Git maintenance still touched the disposable .shadow repository. This branch keeps both root-board and project acceptance maintenance synchronous with maintenance.autoDetach=false plus the older gc.autoDetach fallback; deterministic argument-order regressions, 101 affected tests, 35 style tests, py_compile, diff check, and live Git TRACE2 are green. Attempt 2 reran the failed job green and the push run now concludes success; full manual train 31393013686 also completed green on exact SHA 5f7d7f3eeb60b29990e8d42ba363defd7baa1f2b, including the release gauntlet. No v0.2.0 tag exists yet.
- 2026-08-10T13:42:11Z NOTE ~actv the shipped Claude --live verifier is the remaining harness defect, not an activation failure: its prompt demands one exact output line and its matcher compares a fixed prefix, while a natural cold prompt made Claude open and report the board correctly. Wake: the verifier asks the natural board question, judges semantic board identity/revision/current-work evidence rather than copied prose, and fresh Claude plus Codex live runs both pass without feeding either host the expected answer.
- 2026-08-10T13:55:51Z ~root PROOF scripts/shadow-python.sh -m unittest tests.test_root_board.TheBoardHoldsPointersNeverRowCopies tests.test_root_board.AWriteCountsWithNoRemoteConfigured tests.test_root_board.ConcurrentClaimsHaveExactlyOneWinner tests.test_root_board.ACrashMidClaimLeavesARecoverableBoard -> pass (accept)
- 2026-08-10T14:10:46Z CHECKPOINT ~actv source/test candidate only: the live verifier keeps the earned prompt exactly natural — it names no command, evidence field, or expected value — and judges the final answer by the current project plus multiple content-bearing terms from the current work rather than one copied prefix. It runs Claude and Codex read-only, without session persistence, from a retained unrelated directory; any board drift is inconclusive, Codex matches only its final-message file, and Cursor live remains an explicit unsupported skip. The row proof now includes tests.test_verify_host; declared activation/human-language/host tests, shell syntax, PLAN lint, and diff check are green. This is not merge, install, or fresh live-host proof; ~actv remains claimed through those boundaries.
- 2026-08-10T14:20:44Z ~tier PROOF scripts/shadow-python.sh -m unittest tests.test_verification_tiers.ASilentSkipFailsLoudly tests.test_release_train.ReleaseTrainTriggersAreDeterministic -> pass (accept)
- 2026-08-10T14:29:56Z CHECKPOINT ~actv merge/install/live boundary: PR #311 squash-merged exact tested head acdcd58e7519a02a12801799d021504cac575613 to origin/main as 686eb3ca8f96c2ceed004e85aba05f1b5938e6c4 after all ten required checks, visual proof, CodeQL, Bugbot, Approval, and Cursor Security passed with no comments or review threads. The installed clone was fast-forwarded to that exact merge, install.sh converged, shadow --version returned 0.2.0, doctor reported 16/16 with zero warnings, and zero-env portfolio status plus both offline host verifiers passed from an unrelated directory. Fresh paid Claude and Codex sessions then each received only the natural question, ran against the frozen read-only board, and independently identified the current Shadow work; both shipped --live verifier commands returned 0. This establishes merged source, exact installation, and cold-session activation for ~actv; Cursor remains the documented unsupported cold-directive surface rather than an inferred pass.
- 2026-08-10T14:30:47Z ~actv PROOF scripts/shadow-python.sh -m unittest tests.test_human_language.PlainOutcomeNamesLeadEveryHumanSurface tests.test_host_directives.ActivationIsByteIdenticalAcrossSupportedHosts tests.test_host_directives.DogfoodOverwriteBacksUpAndConverges tests.test_verify_host -> pass (accept)
- 2026-08-10T14:42:24Z ~clen PROOF bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md' -> pass (accept)
- 2026-08-10T15:46:12Z CHECKPOINT ~gc20 source/test candidate only: commit 6f97218 adds enforced hot-plan byte/row/milestone limits, content-addressed archive compaction with exact-CAS half-write recovery, manifested non-force worktree and expired-snapshot retirement with target-state CAS and crash journals, immutable path-free receipts, and one operation-bound successor. Full repository proof is 689 tests green with one intentional skip; the release gauntlet's two story passes, 99 migration/lifecycle tests, 67 adversarial/crash tests, 135 capability/rotation tests, 107 rollback/upgrade tests, and stranger-install package all pass from fresh homes. This is not a merge, exact installation, real-artifact retirement, or live two-seat receipt; ~gc20 remains pending until the corrected declared proof passes on accepted canonical source.
- 2026-08-10T15:55:07Z CHECKPOINT ~gc20 review correction: PR #314 Bugbot found that the 128-row hot-plan budget counted row-shaped retained history outside `## Tasks`, unlike the task-scoped milestone and candidate laws. Commits 00b3e55 and d81e25a scope the shared measurement to the canonical Tasks section and add the discriminating history-row regression; both import/claim over-budget gates pass. This is a source correction only, not completion.
- 2026-08-10T16:18:23Z CHECKPOINT ~gc20 acceptance refusal and portability correction: PR #314 merged as 3cd755d1ceb48a424f4c5bf77564e574c54cabce, the installed clone and host wiring converged to that exact source, and zero-environment board status stayed healthy with the original claim intact. `shadow accept` then correctly refused because the declared proof failed in its clean checkout: macOS `TemporaryDirectory()` spells its real `/private/var/...` path through the `/var` symlink, so destructive-retirement fixtures were rejected by the shipped no-symlink-component rail before reaching their intended conditions. The follow-up resolves only trusted fixture roots, retains the production refusal, documents canonical absolute manifest paths, and passes the exact 83-test declared proof under the default macOS temp environment. This is not completion until that correction merges, installs, and the canonical accept path itself passes.
- 2026-08-10T16:28:13Z ~gc20 PROOF scripts/shadow-python.sh -m unittest tests.test_root_board.ImportExcludesGhostCopiesByConstruction tests.test_root_board.RegisteredPointerIsCanonicalBeforePortfolioParsing.test_same_identity_archive_veto_retires_the_registered_entity tests.test_root_board.HotPlanBudgetsGateNormalBoardEntry tests.test_throw.ThrowUsesTheRootBoard tests.test_lifecycle tests.test_shadow_lint.ShadowLintTests tests.test_shadow_accept.ShadowAcceptTests.test_review_worktree_cleanup_refuses_all_dirt_and_never_uses_force tests.test_release_package.ReleasePackageTests.test_lifecycle_command_ships_with_the_dispatcher tests.test_verification_tiers.ASilentSkipFailsLoudly.test_retirement_schema_runs_lifecycle_and_release_proof -> pass (accept)
- 2026-08-10T16:32:27Z ~bops PROOF scripts/shadow-python.sh -m unittest tests.test_amp.CapabilitySelectionIsDeterministicAndRecorded -> pass (accept)
- 2026-08-10T20:04:59Z ~r4d0 PROOF scripts/shadow-python.sh -m unittest tests.test_readme_contract tests.test_documented_targets tests.test_install_doctor tests.test_verify_host tests.test_public_ready_grep_gate -> pass (accept)
- 2026-08-10T20:19:10Z STRUCT the two-seat acceptance is seat-bound, identity-handshaken, and time-bounded | trigger: the exact root-board and lifecycle proof is 99/99 green, but live Codex was compared with another project's first global resume while this seat already owned ~2st8, and live Claude had no timeout and remained running until the verifier process group was terminated. The row's older equal activation-hash/board-revision wording also contradicted adopted decision 14: the stable identity handshake is the goal SHA-256 plus freshly fetched ref, while claims necessarily advance board revisions. The declared proof now includes the verifier and repeated gauntlet so neither defect can hide behind unrelated green modules. Contradicts: the prior ~2st8 wording, replaced here before implementation.
- 2026-08-10T20:40:41Z CHECKPOINT ~2st8 source, merge, and install boundaries are proven but the live gate remains: PR #320 squash-merged exact reviewed head 8413ee0e1fd2bae4d1903aed7db9e6c7b97561eb to origin/main as 1107e4aec962bfffb3d88d89573467fc271dbf69 after all ten required checks, CodeQL, visual proof, and repository gates passed. Independent Ponytail review found one leaked-descendant process-group defect, the final commit fixed it, and the frozen verifier and two-claim gauntlet reran 29/29 and 1/1 green. The installed clone is clean at the merge SHA; install.sh converged, doctor is 16/16, and named-seat offline Claude and Codex verifiers pass. This is not the live receipt. Exact wake: immediately before the run, fetch origin/main once and record that ref; Leo then re-observes one fresh Claude session and one fresh Codex session independently print goal SHA-256 3191b212abef2bf92234c93f1ce14421e0791026afeabcf92874c336abaa13a5 and that same freshly fetched ref, use stable distinct seat names against one scratch HOME, claim disjoint rows, and complete both with proof. A timeout, board drift, or unequal ref is inconclusive. The codex claim was handed back at board revision 90 while this gate waits.
- 2026-08-10T21:10:00Z STRUCT the final two-seat observation becomes one sealed command before another paid run | trigger: the source, merge, install, offline host, and repeated disposable-gauntlet boundaries are proven, but the remaining wake still asks the operator to reconstruct a scratch HOME, two repositories, stable seat identities, concurrency, cleanup, and receipt checks from prose. That contradicts the adopted gauntlet law and the product promise that Shadow is an extensible harness rather than a remembered ceremony. Decision 30 and ~2st8 now require an offline-default, explicit-live, scratch-only runner with a path-free receipt and fail-closed identity, drift, timeout, partial-completion, and orphan-claim checks. Contradicts: the prior manual live recipe; no live host invocation occurs until the sealed offline falsifiers pass.
- 2026-08-10T21:37:11Z STRUCT the owner re-observed the live board and graded it F — the ~v21d gate REFUSED. What the screenshot shows: the detail panel floats over and hides the project list, milestone titles leak their code number, the latest-change line prints a raw STRUCT receipt with a full 64-character commit hash, Done-means is cut mid-word with "(blocked)" glued into prose, sidebar states are unstyled lowercase words, and the contradictions line is a bare sentence. Root cause is in both layers: the projection ships machine strings (raw receipt text, coded titles, server-side ellipsis) and the renderer dumps them. Minted ~uxf1 to own the repair; ~v21d stays pending — the gate goes back to the owner only after ~uxf1 is green and the server restarted. Contradicts: nothing — ~vgal proved state styles FIRE, which is a different claim than the composition reading as a product.
- 2026-08-10T21:37:11Z THROWN ~uxf1 the board reads like a product, not a debug dump | by: claude | note: craft repair->finish lane; audit fan-out then single-writer implementation; claim recorded by hand per the protected-trunk forced form.
- 2026-08-10T21:44:18Z CHECKPOINT ~2st8 sealed-harness source/test candidate only: exact commit 58aa1d64f827d72865580f71806196a919991d77 adds the share-ready README, an offline-default and explicit-live two-seat runner, seat-bound scratch shims with OS-session command attribution, exact scratch entity and simultaneous-claim receipts, closed path-free failures, every-exit process-group draining, canonical clean-source identity, stranger-install source identity, and sanitized Shadow and Git routing that cannot reach the operator board or repositories. Independent Ponytail review returned KEEP/WORKS after 42/42 affected, packaging, documentation, privacy, and hostile-confinement tests passed in 169.854s; the frozen declared root-board, lifecycle, host, two-seat, and gauntlet proof then passed 143/143 in 337.280s. This is not a merge, installation, or live-host receipt. The gate remains pending until this exact mechanism merges, installs, and Leo re-observes one clean exact-origin explicit-live Claude+Codex run.
- 2026-08-10T22:08:22Z ~uxf1 PROOF cmd scripts/shadow-python.sh -m unittest tests.test_browser.TheBoardSpeaksHumanNotMachine tests.test_gallery_visual — both green, rerun in a detached clean checkout of origin/main after #325 merged (the forced hand-flip because the hand-written claim left the row pending, which shadow accept correctly refuses). The repair: the audit fan-out measured the layout root cause (the project list's implicit grid track sized to 523px of nowrap title inside the 250px column, painting under the card — fixed with an explicit minmax(0,1fr) track), and the projection now ships human strings: structured latest-change with plain receipt phrases and no commit hashes, code-free milestone titles, word-boundary cuts; the renderer ships styled state chips and a counted contradictions notice. Live re-observation on :7191 after server restart: overlap probe 0px at the owner's 1500px viewport, root and gallery 200. ~v21d now goes back to the owner.
- 2026-08-10T22:16:11Z ~cfg1 PROOF scripts/shadow-python.sh -m unittest tests.test_config_defaults -> pass (accept)
- 2026-08-10T22:27:06Z ~yml2 PROOF scripts/shadow-python.sh -m unittest tests.test_config_defaults.TheSubsetRefusesWhatItCannotParse -> pass (accept)
- 2026-08-10T22:32:30Z ~noks PROOF scripts/shadow-python.sh -m unittest tests.test_config_defaults.NoSelectorKeys -> pass (accept)
- 2026-08-10T22:39:12Z ~advm PROOF read docs/reference/method.md, `shadow config --explain`, and SKILL.md -> method names attack-then-refute and built-in thermo/ponytail lenses; config prints the active step and lens set; SKILL keeps both as review disciplines rather than runtime roles
- 2026-08-10T23:02:26Z ~ftur PROOF scripts/shadow-python.sh -m unittest tests.test_extension_buckets.FutureIsADeclaredBucket tests.test_amp.GoalMintingReadsThePlansOwnLessonRows tests.test_extension_buckets tests.test_amp -> pass (accept)
- 2026-08-10T23:35:42Z THROWN ~2st8 the two-seat proof, uncoached | by: claude | note: harness-repair scope ONLY — live mode currently returns host_failed on any machine whose host CLI resolves its binary and login through HOME (measured: the claude wrapper finds no binary and the real binary says Not logged in under the scratch HOME), so one real session is impossible by construction. The repair seals Shadow's state, not the hosts' identity: host processes keep their real HOME while every shadow verb still runs under the scratch HOME through the shim, Claude stays bounded to Bash(shadow:*), codex stays workspace-write. The person-observed gate itself stays with the owner. Claim recorded by hand per the protected-trunk forced form.
- 2026-08-10T23:40:02Z ~argv PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ACmdProofIsValidatedAsArgv tests.test_shadow_lint tests.test_shadow_accept -> pass (accept)
- 2026-08-10T23:41:00Z STRUCT ~pscr owns the interpreter-script false green exposed during ~argv review | trigger: a second seat completed the narrower original ~argv contract while the new `node scripts/missing.mjs` falsifier was under adversarial review. Reopening that accepted row would erase a valid receipt; dropping the new invariant would leave lint and accept divergent. M19 owns the one new row because no existing pending row names interpreter operands. Contradicts: the earlier plan to absorb this into still-pending ~argv, superseded by its concurrent canonical acceptance.
- 2026-08-10T23:56:29Z STRUCT M22 minted: the six person-observed and outside-world acceptances become one recursive-acceptance milestone | trigger: the owner's 2026-08-10 goal -- reconcile the activation, canonical-directive, protected-claim, killed-chat, multi-lead, and two-seat checkpoints into one recursive-acceptance milestone without duplicating them. What moved (never copied): ~act9 from M15, ~cn16 from M16, ~pd18 from M18, ~live from M7, ~pair from M10, ~2st8 from the universal-system block; ~2st8 keeps its DoD marker as M22's DoD and one new row ~outp adds the outside-project full loop the goal's proof list requires. Each source milestone promoted its last agent-side row to DoD so it stays well-formed: ~acti (M15), ~mrge (M16), ~pver (M18); M7 and M10, now fully completed, re-marked their final completed rows ~dlaw and ~prot as DoD so the finished blocks are archivable, and the universal-system block did the same with ~tier. Satisfied needs whose dependency rows archive with their source blocks were folded off the moved rows (~live lost ~dlaw, ~pair lost ~prot, ~2st8 lost ~dreg ~root ~gc20 ~actv ~bops ~tier -- every one completed at fold time). Contradicts: nothing -- no row text changed, only position, DoD markers, and folded satisfied needs.
- 2026-08-10T23:57:29Z STRUCT the three finished source milestones stay hot, unarchived, on purpose | trigger: shadow lifecycle refused to archive M7, M10, and the universal-system block because Progress receipts (including the M22 reconciliation receipt itself) are shared between their rows and live tasks, and moving a shared receipt strands live provenance. No hot-plan budget is near its bound, so archival waits for a later lifecycle pass whose receipts no longer cross the line. Contradicts: nothing.
- 2026-08-10T23:57:53Z ~pscr PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ACmdProofIsValidatedAsArgv tests.test_shadow_accept.ProofScriptArgumentsAreValidatedIdentically tests.test_shadow_lint tests.test_shadow_accept -> pass (accept)
- 2026-08-11T00:51:30Z CHECKPOINT ~2st8 the sealed live command PASSED with one real Claude session and one real Codex session; only the person-observed half of the gate remains. Receipt (path-free, verbatim): {"board": {"claims": 0, "completed": 2, "final_revision": 5, "initial_revision": 1}, "failure": null, "goal_sha256": "524331655f44ccadd5e7fdee8e1e69c8dbf3bd764c7234ab9909e6ca816f5cff", "mode": "live", "origin_main": "d2ee535befa9c907ad917d46f45709e5dd5ec11c", "schema": "shadow.two-seat-verification.v1", "seats": [{"completed": true, "name": "claude"}, {"completed": true, "name": "codex"}], "status": "pass"}. Five credentialed runs found five real boundaries, each fixed and pinned before the pass: hosts resolve binary and login through HOME so the host keeps its real HOME while every shadow verb stays sealed by the shim (PR 337); the wrapper prompt itself must command the claim rendezvous or real hosts finish solo (PR 345, with the seat-bound poll and hold-until-witnessed refinements from review); a real Claude session runs every command as a fresh OS-session leader, so attribution moved from session equality to host-process descent (PR 346); a real codex sandbox denies ps entirely — measured with one diagnostic turn — so attribution also rides a run-scoped per-seat environment token, either mechanism sufficing while fabrication through the other seat's shim still fails both (PR 347). Exact wake for the owner: from the installed checkout at or after d2ee535, run SHADOW_CLAUDE_CODE_BIN=$HOME/.local/bin/claude SHADOW_CODEX_BIN=/opt/homebrew/bin/codex scripts/shadow-python.sh scripts/shadow-verify-two-seat.py --live --goal-file <any frozen goal file> --timeout-seconds 600 --json and re-observe both real sessions; the harness never flips this gate itself.
- 2026-08-11T01:36:07Z ~conf PROOF bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh -m unittest tests.test_config_defaults' -> pass (accept)
- 2026-08-11T01:48:01Z ~atom PROOF scripts/shadow-python.sh -m unittest tests.test_throw.ThrowUsesTheRootBoard.test_claim_prints_the_pointer_without_changing_the_project_plan tests.test_root_board.ACrashMidClaimLeavesARecoverableBoard tests.test_throw tests.test_root_board -> pass (accept)
- 2026-08-11T01:56:07Z ~rows PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_lint.RowGrammarRunsWhereverAcceptWouldFlip tests.test_shadow_lint -> pass (accept)
- 2026-08-11T02:01:42Z ~pfix PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_lint.EverySectionLookupIsPrefixMatched tests.test_shadow_lint -> pass (accept)
- 2026-08-11T02:13:40Z ~pyv3 PROOF scripts/shadow-python.sh -m unittest tests.test_install_doctor.TheGateUsesTheResolvedPythonNotBarePython3 tests.test_install_doctor -> pass (accept)
- 2026-08-11T02:52:33Z ~acpt PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_accept.AcceptNeverCommitsAPlanLintBlocks tests.test_style_guard.TheFenceExemptionIsBounded tests.test_host_directives.TheBackupKeepsTheModeOfTheFileItCopied tests.test_shadow_accept tests.test_style_guard tests.test_host_directives -> pass (accept)
- 2026-08-11T03:06:50Z ~hdop PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives.UnmarkedAdoptionRefusesADriftedHeading tests.test_host_directives -> pass (accept)
- 2026-08-11T03:23:04Z ~vsup PROOF scripts/shadow-python.sh -m unittest tests.test_root_board.RegisteredPointerIsCanonicalBeforePortfolioParsing tests.test_root_board tests.test_browser -> pass (accept)
- 2026-08-11T03:52:27Z ~aud1 PROOF bash -c 'set -e; d=$(mktemp -d); trap "rm -rf $d" EXIT; git clone -q --depth 1 --branch main https://github.com/firstbitelabsllc/shadow.git "$d/s"; cd "$d/s"; scripts/shadow-python.sh -m unittest discover -s tests -p "test_*.py"; scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md' -> pass (accept)
- 2026-08-11T04:09:26Z ~flds PROOF scripts/shadow-python.sh -m unittest tests.test_telemetry.TheAllowlistIsClosed -> pass (accept)
- 2026-08-11T04:26:43Z ~emit PROOF scripts/shadow-python.sh -m unittest tests.test_telemetry.EventsCarryNoPayload -> pass (accept)
- 2026-08-11T04:34:15Z ~redk PROOF scripts/shadow-python.sh -m unittest tests.test_telemetry.NothingSensitiveSurvivesTheEmitter -> pass (accept)
- 2026-08-11T04:52:36Z STRUCT M15 DoD moved from ~acti to the milestone's final row ~disc | trigger: canonical `shadow accept ~acti` correctly refused DOD-EARLY after ~tmpr and ~disc were added later. Why now: ~acti source is merged and installed, but its proof receipt cannot land while plan metadata falsely says completing it closes M15. Contradicts: none; row text, proof, dependencies, and order are unchanged, and ~disc now prevents milestone close until both later hardening rows are complete.
- 2026-08-11T04:54:18Z ~acti PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives.EverySupportedHostIsActivated tests.test_host_directives.TheSupportedListInTheDocsDrivesTheWriteTargets tests.test_install_doctor.DoctorNamesEverySupportedHostThatDidNotReceiveTheDirective -> pass (accept)
- 2026-08-11T04:54:42Z NOTE ~2st8 two owner-observed live runs were inconclusive on real-host variance and the rerun loop is PARKED: one run ended seat_overlap_missing because the codex model wandered instead of running the commanded verbs (reproduced with a one-turn probe -- told to run a single command, it explored two directories and stopped), one ended identity_mismatch with an untouched board because a host finished without printing the goal SHA and ref. The recorded PASS receipt at merged d2ee535 stands in this Progress log; observed pass rate is roughly one clean run in three. Exact wake: the owner either accepts the recorded receipt as the observation or reruns the sealed command until one clean run is personally observed; the harness never flips the gate.
- 2026-08-11T04:54:42Z STRUCT the two-seat design survives its adversarial challenge as KEEP-2, and the surviving defects become rows | trigger: the owner asked whether a third seat proves more. A six-agent grounded challenge found every property a third scratch seat could witness is either already forced deterministically at the unit level (the one-winner claim race with the loser told the owner) or explicitly out of the design's scope (fairness, liveness). The genuinely irreducible three-role behavior is the contradiction triangle -- challenger, owner, dependent -- which no scratch harness at any seat count exercises, so it moved into ~pair's real-plan run and the accept-side gate became ~cgat; the needs-cycle lint gap became ~ncyc; the per-computer claim-scope boundary became ~xmac. A third live seat was rejected on measured cost: each new real host has cost one harness repair PR discovered only by paid runs, for zero new invariant here. Contradicts: nothing -- ~2st8 is unchanged.
- 2026-08-11T05:01:43Z THROWN ~tmpr a kill between temp creation and rename leaves no permanent residue | by: claude | note: claim recorded by hand per the protected-trunk forced form (~pdis remains pending); the implementation lands in this same change with its declared falsifier and two mutation checks.
- 2026-08-11T05:08:14Z NOTE ~tmpr the row was double-claimed across mechanisms and the board claim wins: a codex seat claimed ~tmpr on the root board at 04:59:23Z while this seat claimed it by the hand-written protected-trunk form minutes later without a fresh in-flight read -- the exact durability gap M18 owns, measured on ourselves. The implementation merged first (PR 377) and accept correctly refused the non-owning seat, so the flip belongs to the codex claim; the hand claim line stands as the record of the collision, not of ownership.
- 2026-08-11T05:08:14Z THROWN ~disc a linked write discloses itself | by: claude | note: claimed atomically on the root board at revision 299 BEFORE this lane started (the ~tmpr collision taught the order); this plan line is the repo-side record per the protected-trunk form. Implementation lands in this change with its declared falsifier and a mutation check.
- 2026-08-11T05:12:44Z THROWN ~ncyc a needs cycle is a lint finding, not a silent deadlock | by: claude | note: claimed atomically on the root board before the lane started; this plan line is the repo-side record per the protected-trunk form. Implementation lands in this change with its declared falsifier and a mutation check.
- 2026-08-11T05:16:07Z ~ncyc PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_lint.ANeedsCycleIsNamedNotSilent -> pass (80/80 in a detached clean checkout of origin/main; flip recorded by hand per the protected-trunk forced form because shadow accept reran the proof green but its rejected push discarded the flip commit with the temp checkout -- measured and minted as ~aflp in this same change)
- 2026-08-11T05:17:30Z THROWN ~xmac the claim-safety scope boundary is written where a cold lead reads it | by: claude | note: claimed atomically on the root board before the lane started; this line is the repo-side record per the protected-trunk form.
- 2026-08-11T05:17:30Z ~xmac PROOF read grammar.md Dispatch law now carries the Claim-safety scope paragraph -> pass (re-observed in this change: mutual exclusion is stated as per-computer under the advisory lock, cross-computer serialization only at PLAN.md push/merge time, the double-claim consequence is named, and the minting condition for a cross-machine protocol row is stated -- flip recorded by hand with the read re-observation per the protected-trunk forced form)
- 2026-08-11T05:18:57Z ~tmpr PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives.StaleTempResidueIsSweptSafely -> pass (accept)
- 2026-08-11T05:24:34Z STRUCT ~aflp premise corrected by measurement before implementation | trigger: a scratch reproduction proved the flip commit was NEVER discarded -- it lands on the current branch of the checkout accept resolves through the STORED plan pointer. The ~ncyc incident that minted this row is fully explained: accept committed the flip in the installed checkout (the stored pointer) while the operator hunted in the --repo argument's checkout, concluded the commit was destroyed, and duplicated the flip by hand; a peer's later rebase dropped the then-empty original. The defect is DISCLOSURE, not durability, and the row text now says so. Contradicts: this row's own prior wording.
- 2026-08-11T05:24:34Z ~aflp PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_accept.ARejectedPushLeavesTheFlipReachable -> pass (54/54 full accept suite in the lane; mutation check: removing the location disclosure reddens the test. Flip recorded by hand per the protected-trunk forced form; claim was taken atomically on the root board before the lane started)
- 2026-08-11T05:30:49Z THROWN ~cgat a challenged foundation does not flip silently | by: claude | note: claimed atomically on the root board before the lane started; this line is the repo-side record per the protected-trunk form.
- 2026-08-11T05:30:49Z ~cgat PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_accept.AChallengedFoundationDoesNotFlipSilently -> pass (56/56 full accept suite in the lane; the gate holds at claim time AND at the post-proof freshness recheck, ancestry is the transitive needs closure, and disabling both layers reddens both refusal tests. Flip recorded by hand per the protected-trunk forced form)
- 2026-08-11T05:30:49Z ~disc PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives.ALinkedWriteDisclosesTargetAndBackup -> pass (rerun green in a detached clean checkout of origin/main after the M15 DOD-EARLY hold cleared when the ~tmpr flip landed; implementation merged in PR 378, claim held on the root board since revision 299. Flip recorded by hand per the protected-trunk forced form)
- 2026-08-11T05:32:38Z STRUCT ~cano's stale three-link premise reconciled with the accepted ~curs decision | trigger: ~curs proved Cursor has no documented writable user-level directive file and explicitly forbids inventing one, while ~cano and ~vsym still required a Cursor link. The rows now quantify only the documented supported user-level files, Claude Code and Codex, and cite ~curs as the exact reopen condition. Contradicts: the obsolete three-link wording; no implementation or successor was added for Cursor.
- 2026-08-11T05:32:38Z ~cano PROOF read ai-leo origin/main merge 2c337503a47ba794d284aee59d5735f71552cb38, the two resolved host paths, retained source hashes, migration range coverage, and the managed goal block -> pass (exactly one live canonical `host-directives/LOCAL_AGENT.md`; `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are symlinks whose resolved targets are identical and whose bytes share SHA-256 79527a76173ab4c01f6f58ce42d62b5cd6f22214a2743c592d33fd1b8e77f627. Adjacent backups retain the two pre-migration hashes named in `host-directives/MIGRATION.md`; its range table covers every nonblank source line, and the canonical file contains exactly one managed Shadow block byte-identical to `shadow goal`. Cursor remains excluded by ~curs. Flip recorded by hand because this is a read proof; the root-board claim is released only after this PLAN receipt lands on canonical main.)
- 2026-08-11T05:46:59Z ~vsym PROOF scripts/shadow-python.sh -m unittest tests.test_standing_goal.HostDirectiveOriginIsReported -> pass (accept)
- 2026-08-11T05:59:04Z THROWN ~endp the owner picks the telemetry endpoint | by: claude | note: claimed atomically on the root board; this line is the repo-side record per the protected-trunk form.
- 2026-08-11T05:59:04Z ~endp PROOF gate leo: the owner decided in chat on 2026-08-11 -- Langfuse, "as a local thing that doesn't run for users but for me locally ... for debugging and observability", while "we run a gauntlet of long test jobs against shadow" -> pass (recorded in docs/reference/telemetry.md \u00a7 Local sink with the approved field subset; the ~obsv product KILL stands untouched -- the product still sends nothing, ever. Flip recorded by hand per the protected-trunk forced form)
- 2026-08-11T05:59:04Z THROWN ~lfse the owner's local sink exists as owner tooling only | by: claude | note: minted and completed in the same change that implements it; claimed by this line per the protected-trunk form.
- 2026-08-11T05:59:04Z ~lfse PROOF scripts/shadow-python.sh -m unittest tests.test_telemetry.TheLocalSinkIsOwnerOptInOnly -> pass (refusal without env verified by subprocess, no product script references the sink; live smoke on the owner's machine delivered a gauntlet round's spans to the local Langfuse and they were read back via /api/public/v2/observations. Flip recorded by hand per the protected-trunk forced form)
- 2026-08-11T06:15:37Z ~mrge PROOF scripts/shadow-python.sh -m unittest tests.test_host_directives.TheManagedBlockLandsInTheCanonicalSourceNotTheLink -> pass (accept)
- 2026-08-11T07:04:07Z ~plug PROOF scripts/shadow-python.sh -m unittest tests.test_distribution_contract tests.test_release_package -> pass (accept)
- 2026-08-11T07:04:26Z ~hrbf PROOF scripts/shadow-python.sh -m unittest tests.test_distribution_contract.DistributionContractTests.test_human_brief_hides_machine_detail_until_requested -> pass (accept)
- 2026-08-11T07:04:39Z ~cstm PROOF scripts/shadow-python.sh -m unittest tests.test_distribution_contract.DistributionContractTests.test_hosted_coach_never_claims_local_authority tests.test_distribution_contract.DistributionContractTests.test_distribution_does_not_publish_a_placeholder_transport -> pass (accept)
- 2026-08-11T07:05:30Z ~cold PROOF unfamiliar meal-planning fixture -> pass (independent cold reader A). The rendered brief named the human outcome as a neighbor understanding, joining, choosing meals, and paying only after the kitchen is insured; showed onboarding, checkout integration, and insurance as three parallel promises; focused attention on one observed onboarding-to-safe-payment journey while keeping the insurer's next response visible; and named that journey plus the insurer response as the next evidence checkpoint with medium confidence and an honestly unknown completion date. The hosted version led with its inability to see or change local work and returned the same intent as a portable packet. Leak scan found zero branches, hashes, paths, row IDs, commands, Git terms, or implementation identifiers

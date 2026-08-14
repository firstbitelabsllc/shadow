# The configurable method profile, and why memory is the user's own business

Status: **DESIGN — ruled by the owner in-session 2026-08-12; implemented.**

Design record for `### M25`. Every measurement below was taken on the dogfood
machine on 2026-08-12 against `origin/main@c9618ea`, and every document quoted
is byte-identical at that ref.

Two later corrections are folded in and marked where they land: the memory
verdict became **delete, not amend**, and the rails diagnosis in the original
draft was **wrong about its cause**. Fable was consulted at ultraplan time and
its input is recorded; an earlier draft claimed it was unreachable.

## What was asked, and what already shipped

The ask had two halves: define a configurable Shadow method profile, and
objectively evaluate optional memory integrations — especially Honcho — for
contextual recall, without granting them plan, proof, ownership, or
hidden-state authority.

Both halves are narrower than they read, because M12 already shipped the
configurable half and `~hnch` already ruled on memory:

- `shadow.yaml` exists, at a repository's Git root, version 1, holding exactly
  **one** key: `adversarial-lenses`. A repository without the file behaves
  identically (`~cfg1`). An unsupported key is refused by file and line rather
  than misread (`~yml2`). Any provider, model, account, or credential key
  anywhere in the file is refused outright (`~noks`).
- `buckets.md` declares four capability slots and states plainly that **there
  is no bucket configuration file**; bindings are overridden only by
  `SHADOW_BUCKET_<NAME>` in the environment.
- `honcho.md` rules that Honcho is *a pattern Shadow implements, not a service
  Shadow installs*, and the `honcho` bucket enforces it mechanically: its kind
  is `builtin`, whose check is a **negative** — it goes stale, which is doctor
  FAIL, if anything named honcho is ever installed as a skill or plugin.

So this is not a request for more keys. It is a request for the **rule** that
decides whether a second key may ever exist, plus an honest re-test of a
ruling made on 2026-08-07.

## Part 1 — the dial test

**A method dial may be declared only when a wrong value costs quality, never
truth.**

That single sentence closes the set. It is not invented for this document; it
is the principle the three shipped surfaces already follow, stated out loud so
the next dial request is decided by a test rather than by preference.

| Candidate dial | A wrong value costs | Verdict |
|---|---|---|
| `adversarial-lenses` | a weaker review | **declarable** — shipped |
| verification-tier thresholds | a train that runs early or late | **candidate** |
| hot-plan byte and row budgets | a plan that bloats or churns | **candidate** |
| proof classes (`cmd`, `read`, `gate`) | a completion nobody proved | **fixed** |
| `accept` as the only flip path | a row that flips unproven | **fixed** |
| bucket bindings | a capability that resolves to the wrong thing | **fixed — environment only** |
| a memory-adapter binding | recall mistaken for authority | **refused** |
| provider, model, account, credential | not a method dial at all | **refused** — `~noks` |

Two entries deserve their reasoning, because both are places a well-meaning
"make the method configurable" change would quietly do damage.

**Bucket bindings stay out of the file.** The asymmetry is already shipped and
is the whole argument: an *absent* bucket WARNs, but a *present-but-wrong*
bucket FAILs. A committed file that asserts presence can drift from the
machine; an environment variable is evaluated fresh every time. So the
declaration file may say what the method *would* use, and may never say what
is *there*. `buckets.md` is right, and the profile must not reverse it.

**The dial test is about cost, not about importance.** Proof classes are the
most important thing in the method, which is exactly why they are not
configurable: a repository that could redefine what counts as proof could
manufacture a true-looking completion. Adversarial lenses are also important,
and a bad choice there produces a worse review — bad, recoverable, visible.
Quality degrades loudly. Truth degrades silently.

## Part 2 — the memory evaluation

### The four categories, and the one with no home

`grammar.md` § *Sections, in order* defines exactly five sections: `Brief`,
`Tasks`, `Deferred`, `Contradictions`, `Progress`. Read that list against the
four recall categories:

| Category | Git-durable home in Shadow today |
|---|---|
| Recurring context (what this work needs) | Yes — the milestone `- tools:` line, and `LESSON` / `DECISION` Progress lines |
| Cross-session recall (what is in flight, what is next) | Yes — the computer board plus entity plan pointers, read by `shadow status --by <seat>` |
| **User preferences** | **No section can hold one** |
| **People** | **No section can hold one** |

This is the finding the standing ruling does not name. `honcho.md`'s
function-map table maps six honcho ideas to six Shadow homes, and every one of
them is a *work* fact — coordination, work detail, tools, continuity, lessons.
The table silently omits *person* facts. That omission is why the question
keeps coming back and keeps costing a re-derivation: the ruling answers a
question narrower than the one being asked.

### Arm 2 — plan-only memory, as measured

Enforcement is the distinguishing property, and it is real. While preparing
this document, `shadow return` refused to release a completed claim because
four unrelated rows in that plan lacked PROOF receipts. That refusal was
inconvenient and correct: the plan layer will not let an unproven row pass
quietly. Its coverage of preferences and people is nil; its trustworthiness
where it does apply is mechanically enforced by `shadow lint` and
`shadow accept`.

### Arm 3a — the opt-in read-only adapter already running here

Claude Code's auto-memory is a live instance of exactly the arm the ask
describes: opt-in, read-only with respect to plan authority, surfacing recall
as background context. Measured on this machine:

- **197** memory files; **145** reachable from the `MEMORY.md` index; **52
  orphans**, or **26%**, that exist on disk but are absent from the index that
  is loaded each session.
- The leak is **active, not a legacy backlog**: 29% orphan rate for July
  (26 of 89), 16% for August (9 of 58), newest orphan dated **2026-08-11**.
- Coverage spans all four categories, including the two Shadow cannot hold:
  four `type: user` preference facts and several person files.
- **Nothing detects the loss.** No lint, no doctor check, no gate.

Its honesty properties, however, are genuinely good, and this document would be
dishonest to omit them. Two recalls surfaced in this very session were
materially **wrong**: one asserted Shadow v4.0.0 with `shadow --version → 3.0.0`
and doctor 11/11, against an actual 1.0.1 and 17/17; another named
`~/Development/shadow/PLAN.md ### M9` as plan authority, when that file does not
exist and the registered pointer is `~/.shadow/plans/shadow/PLAN.md`. Both were
caught immediately, because each recall arrived with **its source file and an
explicit age caveat telling the reader to verify against current state**. A
third recall — the pointer to `honcho.md` itself — saved a full re-derivation,
which is precisely the cost that document exists to prevent.

So arm 3a preserves source and preserves uncertainty. It also silently loses a
quarter of its writes. Those are separable properties, and the distinction
matters for the verdict.

### Arm 3b — Honcho, as it actually is today

Grounded in `plastic-labs/claude-honcho` rather than in memory of the
2026-08-07 discussion:

- The default endpoint is **hosted**, `https://api.honcho.dev`. Self-hosting is
  supported via `endpoint.baseUrl`.
- `saveMessages` defaults to **true**, so raw conversation content egresses by
  default.
- It stores Messages, Peers, Sessions, and **Conclusions/Representations**
  derived asynchronously by background reasoning models the documentation
  describes as **opaque to the agent**.
- Retrieval is the dialectic `peer.chat({query})` endpoint, which returns a
  **generated answer** rather than a citation.
- Authority resolves **server-side peer configuration first**, then the user
  file, then environment, then "most permissive" plugin defaults.
- Real opt-outs exist: `enabled`, `saveMessages: false`, `rememberTool: false`,
  `saveToolUse: false`, `saveGitEvents: false`.

Score that against the ask's own four guardrails. Honcho does **not** claim
plan authority, does **not** claim proof, and does **not** claim ownership of
decisions — three passes, and they are honest passes. It fails the fourth.
Opaque background reasoning surfaced through a generated dialectic answer is
**hidden-state authority by construction**: the agent cannot see which premises
produced a conclusion, cannot cite a line, and cannot bound its own
uncertainty.

The decisive point is that **read-only-ness does not fix opacity.** A maximally
restricted Honcho — self-hosted, `saveMessages: false`, read-only — is not the
shape the 2026-08-07 ruling refuted, and it deserved this re-test. It still
fails, on a different and narrower axis than the ruling states: not "a second
store becomes authority by convenience", but "a synthesized answer cannot carry
its source or its confidence." That axis is the product's core value
proposition, not a configuration flag, so no configuration reaches it.

One mechanical consequence is worth stating plainly, because it constrains how
this question may ever be explored: anything named honcho installed as a skill
or plugin turns the `honcho` builtin bucket stale, which is doctor FAIL. Arm 3b
therefore **cannot be built in order to be tested** without either evading a
shipped guard or promoting the spike first. Evading the guard was refused. The
spike is the sanctioned route, and `honcho.md` § *If the ruling should change*
pre-authorizes exactly it.

### Recommendation

**Delete the surface. Do not keep the ruling and amend it.**

An earlier draft of this spec recommended keep-and-amend. That was wrong, and
the reason it was wrong is the more useful finding: I was defending a surface
that should not exist.

The `honcho` bucket's check was a NEGATIVE — it read a person's own skill roots
and hard-failed `shadow doctor` if it found anything named honcho. A doctor
failure over a user's own memory tool is Shadow policing unrelated user
configuration. That is true regardless of whether the underlying ruling is
correct.

The measurements below still stand, and they *support* the ruling's substance:
Honcho's retrieval is a dialectic `peer.chat()` returning a generated answer
over reasoning its own docs call opaque, so it preserves neither source nor
uncertainty. Honcho genuinely does not serve Shadow core. But "this does not
serve us" is a reason to say **nothing** about it, not a reason to enforce a
ruling about it on someone else's machine.

1. `docs/reference/honcho.md` is **deleted**, with `buckets.md`'s declaration
   in the same commit — `_resolve_builtin` hard-fails on a missing default, so
   removing either alone breaks the CLI with the same red that *installing*
   honcho produced. The guard could not distinguish "ruling deleted" from
   "ruling violated".
2. The `builtin` kind goes with it. honcho was its only user, so
   `_resolve_builtin`, `_installed_namesake`, the `KINDS` entry, and the
   dispatch key are all dead on removal.
3. One plain sentence replaces all of it, in `buckets.md` and `SKILL.md`: which
   recall or memory tooling a person runs is their own configuration — the same
   boundary `config.md` already draws when it says which provider a native host
   uses is that host's business.
4. **No new configuration key.** A memory binding is refused by the dial test
   in Part 1, because a wrong value there costs truth.

The overreach was wider than the ruling described. `_installed_namesake` used
`.exists()`, not `.is_dir()`, so a single **zero-byte file** named honcho in
any of three skill roots turned the CLI red on any machine — measured across
all three roots on 2026-08-12. The plugin-cache branch correctly used
`.is_dir()`, so the defect was specific to the skill-root loop.

The four bucket tests are **inverted, not deleted**. A deleted test proves
nothing; `NoBucketPolicesUnrelatedUserTooling` asserts that a namesake
directory, a bare namesake file, and a namesake plugin each leave Shadow green.

This reverses `~bkts`, a completed and accepted receipt that called the negative
check "the design's proof of honesty ... mutation-verified". That reversal is
recorded in the plan's Contradictions rather than made silently.

**Who ruled, and how.** The owner ruled kill in-session on 2026-08-12, and Sol
agreed on the same reasoning. Fable was consulted at ultraplan time and
confirmed the framing. An earlier draft recorded Fable as unreachable; that is
corrected here rather than left standing.

## The rails finding — corrected, because the first diagnosis was wrong

Writing `### M25` into the plan surfaced a real deadlock. The original draft of
this section named the wrong cause, and the correction matters more than the
original claim did.

**What the first draft said:** four of Shadow's mechanisms assume a Git-tracked
plan and all four fail on the plan that governs Shadow; `shadow lint` reports 70
blocking `PROOF-ARGV0` because the proofs are invalid for the store they live
in; `~lmig` was wrong to move the plan local.

**What is actually true, measured:**

| Claim | Verdict |
|---|---|
| 70 blocking = invalid proofs | **FALSE RED.** `shadow lint <plan>` → 70 blocking, rc=1. `shadow lint --repo <source checkout> <same plan>` → **0 blocking, rc=0** |
| a category error; the plan must move | **NOT ESTABLISHED.** `commands.md:18` documents that *a registered machine-local plan uses `--repo` to check proof scripts at its source checkout's committed HEAD* — the supported arrangement, not a mistake |
| one unhealthy plan freezes the board | **MISATTRIBUTED.** `shadow-status.py:98` calls `lint_plan(text)` with no root, and `PROOF-ARGV0` is gated on `root is not None`, so the health gate never saw those 70 |
| four mechanisms are broken | **ONE is.** throw, return, status, and accept all route a local plan through `frozen_plan_snapshot`; only `shadow lifecycle` lacked that branch |
| `shadow lifecycle` refuses | **TRUE** — *project plan is not present at the current Git HEAD* |
| the byte remedy is unreachable | **TRUE**, and it follows from lifecycle alone |
| plan sat 506 bytes under budget | **TRUE, exactly** — 261,638 of 262,144 |

The real freeze mechanism is `HOT-PLAN-BYTES`, which is text-only and therefore
root-independent, so it *does* reach the health gate. Proven by applying the
M25 rows to a copy and re-linting with no root: blocking goes **0 → 1**, detail
`bytes is 269240 (limit 262144)`.

**`~lmig` is substantially exonerated.** Its row names *lint, throw, return, and
accept* — four verbs, and lifecycle is not among them. Lint resolves correctly
with `--repo`; accept's local path lints against `--repo`. The gap was the one
verb it never claimed. The original draft accused it on the strength of a lint
run that omitted the flag.

**A trap worth recording, because the obvious fix causes the disease.** Making
the health gate root-aware — "unify the lint verdict" — would push this plan
from 0 to 70 blocking in the text-only variant, hit
`shadow_board_import.py:540`, and freeze the portfolio import for *every*
project. The proposed fix would have manufactured the exact deadlock it was
written to remove. The narrow correct fix is instead to default `--repo` for a
registered local plan; PR #458 already shipped the capability, only the default
is missing.

**What shipped.** `shadow lifecycle` gained the local branch its siblings
already had, plus a widened tombstone regex — the reader pinned bare hex, and a
local head is `local:<sha256>`, so rerouting alone would have minted receipts
its own parser rejects. `head_plan_snapshot` was deliberately left untouched:
it still backs tracked-plan accept and interrupted-write recovery, neither of
which has a replacement. Measured after: archiving one proven milestone
reclaimed **16,890 bytes** on the real plan, and the minted tombstone parses
with its own reader.

A hand-forged archive receipt would have cleared the byte budget in one edit and
was refused: fabricating a `shadow:lifecycle:…:sha256:…:cas:…` provenance
comment is the backdated-receipt failure `~lgrf` closed.

## Method note: the spike has teeth, verified both directions

The spike is the right instrument because its deadline is enforced, and that
was confirmed rather than assumed. Controlled A/B against the real plan:

| Plan state | `shadow lint` result |
|---|---|
| baseline | no spike findings |
| open spike, `ends:` in the future | **no findings** — legal under `Mode: ship` |
| expired spike, no decision | **2 blocking** — `SHIP-OVER-OPEN-SPIKE`, `SPIKE-EXPIRED-NO-DECISION` |
| expired spike, with a `DECISION` | **no findings** |

An initial reading that an open spike would immediately red a `ship`-mode plan
was wrong, and the positive control is what showed it. A dated spike is a real
commitment: let it lapse undecided and the whole plan goes red, and only a
written keep, kill, or promote clears it.

## What this design deliberately does not do

- It adds **no** key to `shadow.yaml`. Part 1 is the test that governs future
  keys; building one before the owner rules would be the reversal the
  Contradictions rows exist to prevent.
- It does **not** edit `config.md` or `honcho.md`. Those amendments are
  `~pdec`'s, after the ruling.
- It installs **nothing**. Honcho was read from an indexed source only.
- It does **not** claim the memory question is settled. The spike is open until
  the owner rules, and its `ends:` date is enforced.

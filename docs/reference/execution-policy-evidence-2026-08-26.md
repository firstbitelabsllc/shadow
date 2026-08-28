# Shadow native execution policy: four-harness evidence and cold takeover

**Date:** 2026-08-26
**Status:** source-tested implementation; merge, installation, and live-dogfood
receipts remain separate

**Source base:** `7a59292ff30435cc4fd7738192063ee98f81633f`

**Evaluation scope:** 12 scenarios × Claude Code, Codex, Cursor, and Grok

**Authority:** this report explains evidence; the local Shadow board and the
owning `PLAN.md` remain the only priority, claim, and acceptance authority.

This is a ten-part handoff rather than a transcript. Each numbered part is one
logical page so another computer can resume cold from the repository. Physical
page count depends on the Markdown renderer.

## Page 1 of 10 — decision and human outcome

The audit confirms the central suspicion: before this change, Shadow did not
implement the claimed model roster. A lead could choose `claude-code`, `codex`,
or `cursor`, but the sealed host runner passed no model selector and persisted
no requested-model field. It also had no explicit distinction between work a
parent should do directly and work that must create a native child lane. A
successful host receipt therefore proved task execution, not that Fable planned,
Opus or Sol coded, Luna handled bounded work, or any subagent existed.

The winning change is intentionally smaller than an automatic router. The
driving lead chooses three semantic facts that it is already responsible for:

1. the native host (`claude-code`, `codex`, `cursor`, or `grok`);
2. the work class (`planning`, `coding`, `review`, or `lightweight`); and
3. the execution shape (`direct` or `required`).

Shadow deterministically maps the host/class pair to a native model selector
and configures the host's real child capability when `required` is requested.
It never reads prompt keywords, selects an account, invents a fallback, retries
on another provider, or hides a quota failure. A request is not an observation:
the private attempt records the requested model and requested child capability,
while the owner-local gauntlet separately proves what the native stream reported.

This matters because the roster is meant to return attention, not produce
routing theater. If frontier models silently do trivial work, scarce reasoning
is wasted. If cheap models silently receive hard implementation, quality falls.
If a parent says “I delegated” without native child lineage, the system may be
serial while reporting leverage. All three defects force Leo to supervise the
machinery. Explicit choices, fail-closed capability checks, and observable
outcomes let agents handle sequencing while Leo retains direction, protected
decisions, and publication.

The source result is promising but not universally green. The corrected
48-cell verdict is **30 pass / 18 fail**. Codex and Grok are 12/12. Cursor is
6/12 because its Fable/Opus calls hit a provider usage limit and because no
verified structured native-child surface was found. Claude Code is 0/12 under
the deliberately strict grade because it performed the tasks but omitted the
exact terminal sentinel; one mutation scenario also exited nonzero. Those reds
are preserved. Weakening the sentinel, pretending Cursor Auto reveals its
underlying model, or treating a selector as execution proof would recreate the
original bug.

## Page 2 of 10 — the ten problems being solved

The audit was organized around ten concrete failure modes. They are ranked by
how easily they can manufacture a false claim of intelligent delegation.

1. **Host selection masqueraded as model selection.** Choosing Codex never
   proved Sol, and choosing Claude never proved Fable or Opus. Provider defaults
   can drift without a source diff.
2. **Requested and observed models were collapsed.** A CLI flag proves intent;
   an init record, native event, or trace proves what the provider reported.
   Aliases, account catalogs, and compatibility layers can resolve differently.
3. **Parent and helper models were conflated.** A native run can report more
   than one model. The parent initialization record is the route witness;
   helper usage is supporting evidence, not a replacement identity.
4. **Cursor Auto looked more precise than it is.** `Auto` can be a useful
   lightweight choice, but the headless result does not reveal the underlying
   model. Shadow must say “Auto observed,” not guess a provider model.
5. **Static argv tests stood in for real work.** A unit test can show that
   `--model` appears. It cannot prove authentication, quota, tool execution,
   file mutation, model observation, usage, or final completion.
6. **Telemetry delivery stood in for durable observation.** An accepted OTLP
   request is not a stored trace. Every gauntlet row needs exact trace-ID
   readback from Langfuse.
   The writer records a red provisional span first, performs that exact
   readback, and only then writes the final adjudication to the same trace. A
   readback failure therefore cannot leave a green final record behind.
7. **Delegation prose stood in for child lineage.** A parent mentioning an
   agent or claiming it used one is insufficient. Required-delegation rows need
   a structured native `Agent`, `spawn_agent`, or `spawn_subagent` witness.
8. **Exit zero stood in for a finished job.** A row also needs exact changed
   paths, a fresh deterministic verifier, structured usage, and the exact
   completion sentinel in the final model response rather than an echoed prompt.
9. **Capability and quota failures had no stable wake.** Missing auth, exhausted
   quota, unavailable models, and absent child capabilities must stay red with
   one precise wake. Silent fallback corrupts both cost and quality evidence.
10. **Source, merge, install, and live behavior were called one thing.** A
    source test cannot prove GitHub merged the code, the installed command came
    from that merge, or a live host used the installed path.

These are important as a system, not ten isolated bugs. If any early link is
implicit, later observability can faithfully measure the wrong thing. If any
late link is inferred, a correct source design can be mistaken for operational
reality. The resulting supervision burden lands on Leo: checking which model
ran, reopening chats, reconciling provider errors, and guessing whether a
“delegation” was actually parallel work.

The adversarial standard is therefore asymmetric. A green row needs every
predicate. A red row needs only one falsifier. That makes the report less
flattering but far more useful for an overnight successor: the successor can
work the exact failing predicate instead of interpreting a transcript.

## Page 3 of 10 — winning architecture

The new execution flow is:

```text
local Shadow board
  -> owning PLAN checkpoint and atomic claim
  -> lead chooses host + semantic class + direct|required
  -> checked-in deterministic model policy
  -> sealed native CLI in one clean worktree
  -> private host attempt and bounded native receipt
  -> owner-local Langfuse evaluation observation
  -> lead reproduces proof and accepts through Shadow
```

The board remains the source of priority and ownership. The plan contains the
reason for the work and its proof. The execution policy is only a small mapping;
it does not become a scheduler or a second board. The host runner remains a
sealed transport: clean Git root, frozen task hash, exact allowlist, bounded
receipt, fail-closed scope checking, no provider prompt or transcript in the
portable receipt.

The four semantic classes avoid a large, brittle prompt classifier. `planning`
is for contradiction resolution, architecture, and proof design. `coding` is
for implementation and debugging. `review` is for an independent falsifier.
`lightweight` is for bounded summaries, documentation repair, and cold-resume
reproduction. The class is named by the driving lead because difficulty is an
intent decision, not a keyword fact.

Execution shape is orthogonal. `direct` disables child spawning where the CLI
offers a control. `required` configures and demands an observable native child:
Claude Code `Agent`, Codex `multi_agent`, or Grok `spawn_subagent`. Cursor
currently rejects `required` before launch with the wake “Cursor CLI exposes
observable native child lineage.” Shadow does not launch a hidden second Cursor
process and rename that native delegation.

The policy is deterministic:

| Class | Claude Code | Codex | Cursor | Grok |
| --- | --- | --- | --- | --- |
| planning | Fable | Sol | Fable High | Grok 4.6 |
| coding | Opus | Sol | Opus High | Grok 4.6 |
| review | Fable | Terra | Cursor Grok 4.6 High | Grok 4.6 |
| lightweight | Sonnet | Luna | Auto | Grok 4.5 |

There is deliberately no automatic provider fallback. Current quota, custody,
and authorization are live host facts. The lead can make a new explicit claim
for another host, but one failed packet never mutates into a different model or
billable provider behind the receipt.

Langfuse is downstream evaluation tooling on the owner's machine. It receives a
closed summary only: policy version, random run ID, host, scenario, class,
requested shape, requested and observed model labels, exit/timeout, bounded
usage and cost when supplied, native-child count, stable error code, and grade.
It receives no raw prompt, transcript, tool payload, file content, repository
path, credential, account, or session identifier. It owns no claim and accepts
no checkpoint.

## Page 4 of 10 — evaluation standard and scenario design

The checked-in gauntlet expands twelve scenarios across all four native
harnesses for 48 real headless CLI jobs. Every scenario contains a prompt, an
explicit goal, a multi-step long-job instruction, a tiny disposable Git
fixture, exact allowed paths, a deterministic verifier, and a unique terminal
sentinel. The fixtures are intentionally small so the evaluation measures
routing and execution contracts rather than repository complexity.

The scenarios are:

| Scenario | Class | What it falsifies |
| --- | --- | --- |
| `contradiction-plan` | planning | superficial reading of conflicting requirements |
| `architecture-plan` | planning | plans without boundaries or proof design |
| `exact-code` | coding | prose-only completion and wrong-path edits |
| `debug-code` | coding | diagnosis without a verified repair |
| `adversarial-review` | review | agreeable review that misses a planted defect |
| `false-green-audit` | review | accepting output without checking the witness |
| `protected-wake` | review | inventing authority at a protected boundary |
| `light-summary` | lightweight | expensive or unbounded handling of a small task |
| `docs-contract` | lightweight | documentation that drifts from executable behavior |
| `cold-resume` | lightweight | dependence on transcript-only context |
| `delegation-lineage` | planning | parent prose without a native child record |
| `mutation-trap` | coding | claiming success after the verifier rejects mutation |

A row passes only if all eleven predicates pass: requested model matches the
policy; observed model matches the policy pattern; structured usage exists;
process exits zero before timeout; stable error is absent; changed paths equal
the allowlist; a fresh deterministic verifier passes; the exact terminal
sentinel appears in the final response; required delegation has native child
lineage; Langfuse accepts the closed summary; and the exact trace ID can be read
back.

The grader has independent mutation controls. Tests replace the observed model,
remove model observation, remove child lineage, echo the sentinel outside the
final response, suppress Langfuse delivery or readback, add an out-of-scope
path, force timeout/nonzero/verifier failure, and mark a capability unavailable.
Each mutation must make the grade red. The verifier disables Python bytecode so
its own `__pycache__` cannot manufacture an out-of-scope edit; an initial
correction run documents that exact false negative rather than erasing it.

The approach follows two useful open-source patterns: run coding-agent work in
disposable environments with explicit scoring, as shown by the UK AI Security
Institute's [Inspect tutorial](https://inspect.aisi.org.uk/tutorial.html), and
separate experiments from evaluators, as documented by Langfuse for
[SDK experiments](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
and [code evaluators](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators).
Shadow adopts the proof shape, not either tool as authority.

## Page 5 of 10 — harnesses, versions, and native capabilities

The matrix used authenticated owner-local CLIs, not mocked provider APIs. The
observed tool versions were:

| Surface | Version or source identity |
| --- | --- |
| Claude Code | `2.1.246` |
| Codex CLI | `0.146.0` |
| Cursor CLI | `2026.08.25-3e8eec8` |
| Grok CLI | `1.0.5` (`5115b46bc909`) |
| Langfuse | `4.21.0`, source commit `362ef39abb298824b187e8e964d21460a1d03e98` |
| Shadow base | `7a59292ff30435cc4fd7738192063ee98f81633f` |

Claude Code supports built-in and custom subagents through its native `Agent`
tool and allows a custom agent definition to name its own model. The gauntlet
supplied one bounded read-only evidence agent for the required-delegation row.
See Claude's [subagent documentation](https://code.claude.com/docs/en/sub-agents).
The parent initialization event was used for observed-route identity so helper
model usage could not replace the parent model.

Codex's locally installed feature inventory reported `multi_agent` as stable.
Because the gauntlet deliberately ignores user configuration for reproducibility,
the required row explicitly enabled the feature. Its native collaborative tool
event supplied child lineage. The upstream [`spawn_agent` specification](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/multi_agents_spec.rs)
provides the structured contract.

Grok documents native subagents and the `spawn_subagent` tool, including
built-in and custom subagent behavior. The final correction used an exact
`spawn_subagent` instruction and a 20-turn allowance; the resulting structured
child event made the row green. See Grok's [subagent guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/16-subagents.md)
and [official build overview](https://docs.x.ai/build/overview).

Cursor's [headless CLI documentation](https://docs.cursor.com/en/cli/headless)
supports non-interactive agents and explicit model selection. Neither the
documented surface nor local help exposed a structured native-child capability
that this audit could prove. The Fable and Opus rows also met the account's
usage ceiling. Cursor Auto and Cursor Grok review still ran and produced six
valid greens. The policy therefore supports Cursor direct work, treats Auto as
opaque, and refuses `required` rather than simulating lineage.

The local Langfuse instance was built from the tagged
[v4.21.0 release](https://github.com/langfuse/langfuse/releases/tag/v4.21.0).
Every terminal run wrote a randomly identified trace through the local endpoint
and then queried the event store for that exact ID. The local stack is not a
Shadow dependency and its credentials, compose files, and volumes stay outside
the repository.

## Page 6 of 10 — raw runs, corrections, and adjudicated result

Four immutable JSON summaries form the source evidence. They are not committed
because they contain owner-local evaluation records; their names and hashes are
recorded so the work computer can verify an authorized copy byte-for-byte.

| Run | Cells | Raw verdict | SHA-256 |
| --- | ---: | ---: | --- |
| `full-48-v1.json` | 48 | 24 pass / 24 fail | `d42f6bdeeffa1c541a57e2c4b2b3e457b240b8e61fe84556e4fc3f5802eab50e` |
| `correction-code-v2.json` | 8 | 4 pass / 4 fail | `04b8035fdec64c205daae83084f7b89eca5042503bfe7b09fa891e5205ee24f8` |
| `correction-delegation-v3.json` | 4 | 1 pass / 3 fail | `a743996184a28e1ecb650dbe916a7104ef4d57ceea3c85390a1618f45a6c3f72` |
| `correction-grok-delegation-v4.json` | 1 | 1 pass / 0 fail | `faef72266dccf43f91e5310d34e9f9f28807dec42434d8c5f371d2d1544d837d` |

The first correction reran the two code fixtures across four hosts after the
verifier was changed to suppress its own bytecode. The second used the exact
native child surfaces discovered during source and CLI inspection. The third
corrected only Grok's child prompt/turn budget. Corrections replace the same
host/scenario cell; they do not add extra wins to the denominator.

The adjudicated matrix is therefore:

| Host | Pass | Fail | Main remaining cause |
| --- | ---: | ---: | --- |
| Claude Code | 0 | 12 | exact final sentinel absent; one mutation run nonzero |
| Codex | 12 | 0 | none in this matrix |
| Cursor | 6 | 6 | Fable/Opus usage ceiling; no verified child lineage; one observed alias mismatch |
| Grok | 12 | 0 | none after exact native-child correction |
| **Total** | **30** | **18** | strict unresolved predicates preserved |

By work class, planning is 6/12, coding 6/12, review 9/12, and lightweight
9/12. Across the final 48 cells, false predicates are: terminal completion 12;
deterministic checks 7; exact changed paths 7; no error 7; terminal exit 7;
usage observation 6; delegation lineage 1; observed policy model 1. A single
red cell can contain several false predicates.

All 48 baseline rows reached terminal state, wrote to Langfuse, and passed exact
trace-ID readback. The corrections brought total native executions to 61 with
61 unique trace IDs. This proves storage/readback coverage; it does not upgrade
the 18 failing behavioral grades.

The original suspicion is now proven in two layers. Static inspection proved
that pre-change Shadow passed no model selector. Real execution proved that
explicit selectors and native child surfaces are observable on Codex and Grok,
partly observable on Cursor, and behaviorally incomplete under Claude's exact
terminal contract. The source policy is an evidence-backed improvement, not a
claim that every provider currently behaves identically.

## Page 7 of 10 — what each harness taught us

**Claude Code:** Requested Fable, Opus, and Sonnet routes were observed correctly
in parent initialization records, and the required-delegation correction showed
one native child. The model generally completed the file work and verifiers.
However, all twelve final answers omitted the exact sentinel, so all twelve stay
red. This is not evidence that Claude cannot do the work; it is evidence that
Shadow cannot call a strict long-job contract complete when its terminal
acknowledgement is missing. The mutation scenario also produced a nonzero run.
The next improvement should capture or enforce a structured final contract at
the adapter boundary—not waive the requirement after reading persuasive prose.

**Codex:** All twelve final cells passed after `multi_agent` was explicitly
enabled in the reproducible configuration. Sol handled planning/coding, Terra
handled review, Luna handled lightweight work, and the required row emitted two
child events. This supports the four-class policy and demonstrates why feature
configuration must be part of the command rather than assumed from a user's
global settings.

**Grok:** Direct rows observed Grok 4.6 or 4.5 as intended. Initial delegation
did not produce lineage, but the official native `spawn_subagent` vocabulary
plus a 20-turn allowance produced one structured child event and a green row.
The lesson is not to add an invented Shadow subprocess; it is to express the
native capability precisely and grade its event.

**Cursor:** Cursor Grok review and Auto lightweight rows passed. Planning and
coding rows failed at the provider usage ceiling, which also removed verifier,
mutation, usage, and terminal witnesses. One correction reported `Claude Fable
5 1M Thinking (NO ZDR)` rather than the policy's expected Fable High label, so
model mismatch stayed red too. No structured native-child surface was verified.
The adapter therefore refuses required delegation and records one wake rather
than assuming Cursor's internal agent implementation is an observable child.

**NIA research:** The requested NIA source workflow was attempted, but the local
index/credit path was unavailable. The research lane fell back to current
primary documentation and local CLI/source inspection, and the limitation is
recorded rather than calling NIA green. The wake is restored NIA credits/index
availability, followed by a source-backed recheck of any model or CLI claim
that may have changed.

Across providers, the strongest design lesson is that “automatic router” is the
wrong unit. Shadow should make policy deterministic after the lead chooses the
live host, then let each native CLI expose its own authentic execution and
child semantics. Provider differences belong in small adapters and evidence
parsers. They should not grow into accounts, hidden queues, retry graphs, or a
second source of work ownership.

## Page 8 of 10 — source changes and release boundaries

The implementation has four parts.

First, `scripts/shadow_execution_policy.py` is a small sealed table. It exposes
four hosts, four work classes, two execution shapes, model observation patterns,
and the three currently verified native-child capabilities. It reads no prompt,
account, environment, or quota. Unsupported host/class/shape combinations raise
a stable error.

Second, `scripts/shadow-host.py` now requires `--work-class` and
`--delegation direct|required`. It passes the checked-in native `--model` value,
disables child tools for direct runs when supported, enables the verified native
surface for required runs, and refuses required Cursor delegation before
launch. Its private attempt records policy version, work class, requested model,
requested child capability, and empty observed fields. It still freezes the task
hash, bounds allowed paths, scrubs receipts, and leaves lead acceptance false.

Third, `scripts/dev/shadow-routing-gauntlet.py` owns the real evaluation. It
builds disposable fixtures, invokes authenticated headless CLIs, parses only
bounded native facts, runs a fresh verifier, grades all predicates, writes the
closed summary to owner-local Langfuse, and reads back the exact trace. Its
paired mutation suite prevents the most tempting false greens.

Fourth, the README, command help, skill contract, privacy/telemetry references,
native-host guide, and these two execution-policy documents explain the public
surface. The release package must include the policy module because the
installed host runner imports it. The developer gauntlet and tests remain source
tools rather than product runtime dependencies.

Privacy is preserved by construction. The portable host receipt excludes raw
prompts, transcripts, provider payloads, account/session/billing identifiers,
and absolute operator paths. Langfuse receives only the closed evaluation
summary, runs locally under explicit owner credentials, and the gauntlet
refuses non-loopback endpoints. No product command
gains a network call. No credential, compose file, trace dump, or evaluation
fixture output is committed.

Completion must be reported as four separate receipts:

1. **Source-tested:** focused/mutation suites and the release train pass in the
   isolated worktree.
2. **Merged:** GitHub `origin/main` contains the exact reviewed commit.
3. **Installed:** the normal installer installs from merged `origin/main`, and
   doctor/help read back the new surface.
4. **Live dogfood:** an installed command produces the expected policy/receipt
   behavior against a real native host or records one exact environmental wake.

The 30/18 matrix is source evaluation evidence. It is not a merge, install, or
live receipt. A cold successor must never infer those later states from this
report's existence.

## Page 9 of 10 — safe reproduction runbook

Start from a clean isolated worktree created from freshly fetched `origin/main`.
Do not modify a dirty primary checkout. Read the local Shadow status and the
owning plan before claiming a successor. Then run focused source proof:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_observed_routing_gauntlet tests.test_shadow_host
python3 scripts/shadow-ci.py --paths \
  scripts/shadow_execution_policy.py scripts/shadow-host.py \
  scripts/dev/shadow-routing-gauntlet.py \
  tests/test_observed_routing_gauntlet.py tests/test_shadow_host.py
python3 scripts/shadow-release-package.py --root "$PWD" --allow-dirty --json
```

Run the real matrix only on an owner machine with all four CLIs already
authenticated and an explicitly provisioned local Langfuse endpoint. Keep the
endpoint and keys outside Git. Do not `source` a compose `.env` whose generated
values may contain spaces; load exact `KEY=value` lines with a parser and pass
them to the process environment without printing them. The gauntlet help is the
authoritative option list:

```bash
python3 scripts/dev/shadow-routing-gauntlet.py --help
```

Use a new random run tag and a new summary file. A full run is intentionally
nonzero if any row is red; inspect the JSON rather than treating nonzero as a
missing result. Require `matrix_total == 48`, `terminal_results == 48`, 48
unique trace IDs for the baseline, and both Langfuse booleans true per row.
Never reuse an earlier trace as a readback witness.

For one product packet, create a frozen task file that contains no secrets and
name exact allowed paths:

```bash
shadow host run --host codex --work-class coding --delegation direct \
  --repo /absolute/clean/worktree \
  --task-file /absolute/frozen-task.txt \
  --task-id bounded-change --allowed-path src/bounded.py \
  --out /absolute/clean/worktree/.shadow/evidence/bounded-change.json
```

For required delegation, change only the shape to `required` and make the
frozen task name one bounded child evidence lane. Cursor must refuse until it
has a verified native lineage contract. After a run, reproduce the tests and
changed paths outside the model process; do not flip acceptance because the
provider's prose sounds confident.

Before publishing, inspect `git diff --check`, exact staged paths, focused tests,
affected integration, full release/package proof, and public-ready secret/path
gates. Push a focused branch and merge only after GitHub checks agree. Install
from the merged commit, not the feature worktree. Finally stop the local
Langfuse containers without deleting their volumes; evaluation preservation
and product installation are separate operations.

## Page 10 of 10 — work-computer overnight cold takeover

The work computer should be able to begin with only merged Git source, its own
local Shadow board, and this page. It must not inherit this computer's claims,
Langfuse credentials, traces, compose project, provider sessions, or plan tree.

Cold sequence:

1. Fetch `origin/main`; confirm the commit containing this report. Preserve any
   dirty primary checkout and create a clean worktree.
2. Run `shadow status --by <stable-work-computer-seat>` from anywhere. Continue
   any claims owned by that seat, then atomically claim the highest-value
   reachable Shadow execution-policy checkpoint. Do not copy a claim from this
   Mac.
3. Read `README.md`, `docs/reference/execution-policy.md`, this report, the
   smallest installed Shadow skill, and the owning local `PLAN.md`.
4. Reproduce the focused tests and release package from page 9. If the merged
   source differs from the source base above, review the diff before trusting
   old line-level assumptions.
5. Install from merged `origin/main` through the normal Shadow installer. Record
   the installed source ref, `shadow doctor` result, and `shadow help host`
   readback separately.
6. Run one low-cost installed live packet, ideally Codex Luna lightweight direct,
   in a disposable clean fixture. Prove requested policy fields, exact scope,
   deterministic verification, and lead acceptance. This is live dogfood, not a
   substitute for the 48-cell source evaluation.
7. If an explicitly provisioned local Langfuse is available, run a fresh 48-cell
   matrix with new trace IDs. Keep credentials and raw summaries local. Compare
   by predicates, not aggregate score alone.
8. Record every surviving failure in the work computer's owning `PLAN.md` as a
   checkpoint or one exact wake. Accept only through Shadow; then continue the
   next reachable row.

Current wakes, each intentionally singular:

- **Cursor Fable/Opus:** wake when the provider usage window resets or Leo
  explicitly changes spend; rerun the six red Cursor planning/coding cells.
- **Cursor required delegation:** wake when Cursor CLI exposes structured,
  observable native-child lineage.
- **Claude terminal completion:** wake when the adapter can prove the exact
  final completion sentinel from structured output without accepting prompt
  echo or persuasive prose.
- **NIA:** wake when source index/credits are available; rerun the primary-source
  research check for drift.

Success is not “the overnight job ran.” Success is: the work computer cold
resumes from its local board, reproduces the merged source, installs that exact
source, proves one installed live packet, records red provider predicates
without guessing, accepts proven rows, and reaches the recorded successor with
no transcript routing or supervision from Leo.

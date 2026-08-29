# Shadow pivot — three better problems

Status: **DECISION.** Kill Shadow as a bundled local control plane. Build an
independent acceptance gate as the company bet, publish a continuity capsule as
the free adoption wedge, and keep evidence-backed decision intelligence as a
downstream interface rather than a standalone company.

## Verdict

Do not keep expanding Shadow as a general local chief of staff.

The differentiated asset is narrower and more valuable: **reliable
continuation plus trustworthy acceptance for work performed by autonomous
agents.** The board, plan grammar, claims, and host routing are implementation
experience. They are not automatically the product.

The pivot must turn that experience into a problem a buyer already feels. It
must not ask people to adopt another task manager, another agent launcher, or
another private operating system before receiving value.

The product sequence is:

1. **Sell independent acceptance.** An agent cannot certify its own work.
2. **Distribute through continuity.** A free neutral evidence envelope makes
   agent work portable and gives the paid gate something standard to verify.
3. **Render one decision later.** The brief becomes the human view over trusted
   evidence, not a separate data platform.

## What Shadow actually learned

### 1. The intended person interface is much smaller than the product

`AGENT.md` says the person should do exactly three things:

1. Set a goal.
2. Read one brief.
3. Answer one decision.

It also defines the only three 10x measures:

- a cold agent resumes without re-explanation;
- one brief carries the outcome, risk, and one decision without agent jargon;
- the person never performs recovery.

Shadow's own current assessment is blunt: cold resume is partial, the brief
fails, and the product still leaks recovery mechanics to the person. The
document calls the brief the 10x lever.

### 2. The product repeatedly optimized infrastructure before the human outcome

The repository contains deep, useful engineering around plan storage,
transactional board writes, claim recovery, remote coordination, source
binding, lifecycle replay, bounded reads, and hostile Git configuration.

That work found real failure modes. It also became the center of gravity.
Recent history keeps making remote claims and recovery more correct while the
person-facing brief remains doctrine rather than a proven product surface.

The open upstream-binding change continues that pattern: more exact remote
identity, more fail-closed Git behavior, and more adversarial claim tests. That
is strong infrastructure work. It is also evidence that the current product
can keep consuming engineering indefinitely without proving that a person
gets a better outcome.

### 3. The brief experiment was expensive, then correctly deleted

The deterministic brief producer accumulated guarded sources, reader-first
formatting, receipt checks, scheduling, and delivery semantics. It was later
deleted as 17,492 lines whose actual job was a twice-daily personal email.

That deletion was the right decision. The lesson is not that briefs do not
matter. The lesson is that **a large private workflow is not product proof**.
A brief earns its place only if it improves a measured decision for an
independent user.

### 4. Correct software can still be useless

The most important negative result was not a crash. A separate held-out
usefulness test found a locally green surface that helped none of six test
cases. The surface was cut instead of polished again.

That becomes the pivot standard: repository health, safety, and internal
dogfood are necessary evidence, never evidence of demand or usefulness.

### 5. Engineering depth is not adoption

As of 2026-08-29, the public repository has 716 non-merge commits since
2026-07-21, 214 tracked files, 64,365 lines of Python, and 1,188 Python test
methods. It has zero stars, one fork, and zero watchers.

Those numbers prove unusually deep single-user dogfood. They do not prove that
another person wants the bundle. The next product must earn external repeated
use before the repository earns another large subsystem.

## Product laws worth carrying forward

These are the reusable discoveries. Everything else is negotiable.

1. **A proposal is not acceptance.** A worker may prepare a change without
   gaining authority to declare it complete.
2. **Acceptance reruns proof.** A receipt from the worker is evidence, not the
   trusted verdict.
3. **Every proof names its surface.** Source-tested, reviewed, merged,
   installed, deployed, and live are different claims.
4. **Resume state is explicit and portable.** A cold worker should recover the
   goal, exact source state, latest proof, blocker, and next move without a
   transcript.
5. **The human interface is an outcome, a risk, and at most one decision.**
   Agent identifiers, branches, hashes, paths, commands, and recovery verbs
   stay behind the interface.
6. **Recovery is system work.** The product may refuse unsafe work, but it may
   not turn repair into user homework.
7. **Hidden history is not authority.** Transcripts and model memory may help,
   but neither silently decides what is true.
8. **Refusal is a feature.** Ambiguous authority, stale source, missing proof,
   and conflicting ownership should fail closed with one actionable reason.

## What the pivot must delete

Every candidate starts by removing, not preserving, these assumptions:

- Shadow must own the user's portfolio.
- Shadow must be the task system.
- Shadow must launch or select the coding agent.
- Shadow must keep a private board on every computer.
- Shadow must teach users a plan grammar.
- Shadow must expose claim and recovery verbs.
- Shadow must win by supporting more hosts or models.
- Shadow must retain transcripts or become a memory service.

Any candidate that needs most of those assumptions is Shadow with new
positioning, not a pivot.

## The three angles

These are business directions, not feature names.

### A. Independent engineering change acceptance

A provider-neutral acceptance firewall for agent-authored code. Workers can
propose changes; a separately trusted verifier owns policy, fresh proof,
provenance, refusal, rollback, and the final acceptance record.

The buyer would be an engineering platform, application security, or regulated
software team already allowing coding agents to create branches and pull
requests.

### B. Proof-carrying work continuity

A portable continuation capsule that lets work move between coding agents and
computers without replaying a conversation. It carries the exact goal, source
state, accepted evidence, open risk, blocker, and next checkpoint.

The buyer would be a team using more than one coding agent, or a tool vendor
that wants its users to leave and return without losing trustworthy state.

### C. Evidence-backed decision intelligence

A decision compiler that turns parallel agent activity into one ordinary-
language outcome, the material risk, the decisions already made, and at most
one decision that still belongs to a person.

The buyer would be an engineering leader whose review burden grows as agents
produce more changes, reports, and conflicting recommendations.

## Market reality on 2026-08-29

The broad versions of all three hypotheses are already occupied. The
opportunity, if one exists, is a smaller trust contract that incumbents do not
yet make explicit.

### Agent execution and orchestration are not open territory

[GitHub Copilot cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent)
already researches repositories, makes changes on branches, runs tests in
ephemeral environments, and opens pull requests. [GitHub Agent
HQ](https://github.blog/news-insights/company-news/welcome-home-agents/)
explicitly positions GitHub as the place to assign, steer, and track agents
from OpenAI, Anthropic, Google, Cognition, xAI, and others. It also promises
agent identity, branch controls, code review, governance, and organizational
metrics.

[Cursor Cloud Agents](https://cursor.com/docs/cloud-agent) likewise run from
desktop, web, mobile, Slack, GitHub, Bitbucket, Linear, and an API, then push a
branch back for handoff. Cursor owns the VM, network controls, environment
history, transcripts, and run diagnostics.

**Implication:** Shadow must not compete as a command center, launcher, host
router, worktree manager, or agent dashboard. GitHub and the coding-agent
vendors own those surfaces and distribute them inside existing subscriptions.

### Conversation and session handoff are rapidly commoditizing

[VS Code sessions and
handoff](https://code.visualstudio.com/docs/agents/concepts/sessions) can
discover sessions created in Claude Code, Codex, Copilot CLI, and the GitHub
Copilot app. It can hand a live session from one harness to another with the
full conversation and context, and sync sessions across devices through the
user's GitHub account.

The [Agent Client Protocol session
specification](https://agentclientprotocol.com/protocol/v1/session-setup)
already standardizes loading and resuming agent sessions across client
instances.

**Implication:** “Continue this chat in another agent” is not a viable company
by itself. A continuity capsule survives only if it is different in kind:
transcript-free, repository-native, bound to exact source and evidence, safe to
inspect as untrusted data, and useful even when no vendor session can be
loaded.

There is nevertheless a real measured problem beneath the commoditizing
session UI. The 2026 paper [Handoff Debt: A Framework for Measuring
Collaboration Failures in Human-Agent
Teams](https://arxiv.org/abs/2606.02875) reports 972 delegated software-
engineering episodes across two repositories. Structured handoff notes reduced
successor tool actions by 20–33% and token use by 53–59% compared with no
handoff. Raw traces were more efficient still, but required replaying the
entire prior history. The solve-rate effect was context-dependent, and
structured notes sometimes hurt because the successor trusted the summary
instead of re-observing the work.

**Product implication:** the opportunity is not preserving more conversation.
It is a compact handoff that materially lowers takeover cost while forcing the
next worker to verify source and evidence before relying on the note. The
primary metric must remain correct completion, with efficiency second.

### Broad AI-SDLC governance is already a funded category

[GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
already enforce branch, push, review, commit-metadata, and application-bypass
rules. GitHub is adding dedicated AI controls and agent-aware review.

[Cycode](https://cycode.com/adlc-security/) sells visibility, governance,
guardrails, AI inventory, and validation of agent output before commit.
[Kosli](https://docs.kosli.com/understand_kosli/what_is_kosli) records
immutable software-delivery evidence and evaluates it against compliance
controls; its [admission-control case
study](https://www.kosli.com/case-studies/how_norsk_tipping_made_compliance_their_engine_for_faster_software_delivery/)
shows deployments blocked when required proof is absent.

**Implication:** a broad “acceptance firewall” would enter a crowded enterprise
platform market. The only credible wedge is developer-first and narrower than
security posture or compliance: independently bind a task claim, evidence,
scope, and verdict to the exact proposed source, then let the forge's existing
required-check mechanism enforce it. If native rules plus attestations already
express the complete policy, kill the angle.

### Summaries and general agent evaluation are commodities

[Slack AI](https://slack.com/help/articles/25076892548883-Guide-to-AI-features-in-Slack)
already provides conversation summaries, recaps, answers with citations, and
source drill-down. A prettier engineering update is not differentiated.

[LangSmith](https://docs.langchain.com/langsmith/evaluate-complex-agent) and
[Braintrust](https://www.braintrust.dev/docs/best-practices/agents) already
evaluate final answers, individual steps, and agent trajectories against
datasets and production traces.

**Implication:** the decision brief survives only if it catches stale evidence,
material omissions, and contradictory recommendations that ordinary summaries
miss. A reliability product survives only if it measures coding-work takeover
and acceptance—not generic prompt or trajectory quality.

## The narrow gap

The market does not need another place to run agents, another session viewer,
another compliance platform, another summary, or another generic eval system.

The unresolved question is whether teams need a **proof-carrying work
artifact** that is:

- provider-neutral;
- transcript-free;
- bound to an exact repository state;
- explicit about what each piece of evidence proves;
- independently verifiable;
- capable of refusing stale, forged, or unsupported completion claims;
- readable by a new agent and compressible into one human decision.

That artifact becomes the common substrate. The paid product is the independent
acceptance gate. The continuity capsule is the free format. The decision brief
is the human projection once trusted evidence exists.

## Scoring contract

Each angle received a 1–5 score. The numbers are directional, not a weighted
formula; the fatal risk can kill an angle regardless of its total.

| Dimension | The question that must be answered |
|---|---|
| Pain | Is the problem frequent, expensive, and already visible? |
| Buyer | Is there one person with authority and budget to buy it? |
| Wedge | Can the product create value before replacing existing tools? |
| Differentiation | Does Shadow know something incumbents cannot copy as a checkbox? |
| 30-day MVP | Can a useful end-to-end slice ship in one month? |
| Distribution | Is there a credible path to the first 25 design partners? |
| Pricing | Can the value support software revenue rather than consulting? |
| Retention | Does the product become more valuable with continued use? |
| Shadow reuse | Which proven mechanisms transfer without importing the whole system? |
| Deletion | How much current Shadow surface can disappear? |
| Fast falsifier | What test can kill the idea before a long build? |

| Dimension | A: acceptance | B: continuity | C: decision intelligence |
|---|---:|---:|---:|
| Pain | 5 | 4 | 4 |
| Buyer | 5 | 2 | 4 |
| Wedge | 4 | 5 | 3 |
| Differentiation | 3 | 3 | 2 |
| 30-day MVP | 4 | 5 | 3 |
| Distribution | 3 | 5 | 2 |
| Pricing | 5 | 2 | 4 |
| Retention | 5 | 3 | 3 |
| Shadow reuse | 5 | 4 | 4 |
| Deletion | 5 | 5 | 5 |
| Fast falsifier | 5 | 5 | 5 |
| **Fatal risk** | Native rules already solve it | No standalone budget | Summary commodity |

## Primary bet — independent acceptance gate

### Position

**An agent cannot certify its own work.**

The product is not a code reviewer, CI service, agent runtime, or broad AI
governance platform. It is one required verdict over an agent-authored change:
did an independent verifier evaluate the exact proposed source under protected
policy, and is the evidence fresh, scoped, and sufficient for the claim?

GitHub or GitLab remains the enforcement plane. The product emits one check and
one tamper-evident receipt. It never merges.

### Customer and buyer

The initial customer is a software company with 75–1,500 engineers, protected
repositories, at least two coding-agent providers, and enough agent-authored
pull requests that reviewers can no longer reconstruct every run.

- **Economic buyer:** Head of Platform Engineering or VP Engineering.
- **Co-buyer:** CISO or AppSec when auditability drives the purchase.
- **User:** repository maintainer or staff engineer responsible for safe
  delivery.
- **Painful job:** prove that an untrusted agent started from the claimed
  source, changed only allowed scope, used organization-owned verification,
  and could not manufacture its own completion evidence.

### Narrowest 30-day MVP

A GitHub App plus a small open CLI:

1. Read acceptance policy only from the protected base branch.
2. Freeze the repository identity, base SHA, head SHA, and diff digest.
3. Validate allowed changed paths and required evidence.
4. Run one allowlisted organization-owned workflow against the exact head in a
   secretless runner with no write credential.
5. Reject stale, forged, missing, or self-authored evidence.
6. Emit `accepted` or `refused`, exact reasons, and an immutable JSON receipt
   through one GitHub check.

The MVP does not launch agents, manage tasks, select models, keep transcripts,
own deployments, or create a second policy language. Existing required-check
and ruleset mechanisms enforce the verdict.

### Trust boundary

- The pull-request author and coding agent are untrusted proposers.
- Policy on the protected base branch is trusted configuration.
- The verifier installation and its runner are trusted.
- Proposed code receives no acceptance credential.
- Every evidence item names its issuer, subject SHA, result, time, and the
  surface it proves.
- A source-tested receipt never implies reviewed, merged, deployed, or live.
- A clean checkout is source isolation, not arbitrary-code containment. Do not
  sell it as a sandbox.

### Demo that earns attention

An agent opens a pull request with three attacks:

1. a forged `proof.json`;
2. a green test result from an earlier commit;
3. a change that weakens its own acceptance policy.

The gate reads policy from the base branch, binds evaluation to the current
head, and refuses all three with exact reasons. A corrected head reruns the
independent proof and receives an accepted verdict.

### Reusable Shadow assets

| Asset | Extracted use |
|---|---|
| `scripts/shadow-accept.py:625` | Run proof and require a zero exit status. |
| `scripts/shadow-accept.py:644` | Create a detached review checkout at one exact commit. |
| `scripts/shadow-accept.py:654` | Require proof to leave the checkout clean and at the frozen head. |
| `scripts/shadow-accept.py:710` | Rerun recorded proof before accepting a prior completion. |
| `scripts/shadow_cmd_proof.py:119` | Identify the explicit repository script an interpreter will execute. |
| `scripts/shadow_cmd_proof.py:154` | Verify executable proof source against the committed tree. |
| `scripts/shadow-outcome-validate.py:16` | Reuse the bounded, closed, public-safe document boundary. |
| `scripts/shadow-outcome-validate.py:114` | Restrict evidence locators to HTTPS or repository-relative paths. |

These are source material, not a mandate to preserve their current APIs.
Extract the invariants into a blank, smaller architecture.

### Delete from the product

- root board, seats, claims, leases, priorities, and resume pointers;
- mandatory `PLAN.md` grammar and lifecycle mutation;
- remote claim refs, tombstones, and cross-computer locking;
- host and model routing;
- global agent-instruction installation;
- automatic commit, push, merge, or deployment behavior;
- content-addressed plan trees;
- portfolio dashboard and generic brief producer.

### Distribution, pricing, and retention hypotheses

Lead with a free **Agent PR Trust Audit** over twenty recent agent-authored pull
requests. Show stale evidence, self-controlled policy, missing scope review, or
proof-surface confusion using the team's own history. Then ask the team to make
the gate required on one repository.

First five design-partner profiles:

1. an AI-native SaaS company using several coding agents;
2. a fintech or health-software team with protected delivery controls;
3. a developer-tools company whose own customers expect trustworthy changes;
4. an engineering consultancy supervising agent-authored client work;
5. a large open-source maintainer team receiving agent-generated pull requests.

Test price: free audit, then a $1,000–$3,000 monthly pilot for one organization.
If the control becomes required, test $20–$40 per active contributor with a
$30,000 annual minimum.

Retention comes from required use on every agent-authored change, accumulated
policy, and a durable evidence history that reduces future review and incident
reconstruction.

### Two-week commercial falsifier

Audit at least 100 agent-authored pull requests across five companies.

Pass only if:

- three companies install the gate as a required check on one repository; and
- at least one accepts a paid pilot of $1,000 per month or an equivalent annual
  commitment.

Kill the company angle if buyers consistently say native rules, checks, and
attestations already express the complete policy. Do not build around that
answer.

## Secondary option — proof-carrying continuity capsule

This is the cleanest Shadow extraction and the best free distribution wedge.
It is not the strongest standalone business.

### Product

Publish an MIT-licensed schema and CLI for one active work lane:

```text
capsule create
capsule verify
capsule show
```

The committed capsule contains only:

1. outcome and material risk;
2. repository identity and exact head;
3. accepted evidence with explicit proof surfaces;
4. blocker plus one wake condition;
5. next action.

Git transports it. Any agent can read it as untrusted data. `verify` confirms
the source exists and evidence subjects match before the receiving agent acts.
No global host-file writes, board, priorities, dependencies, claims, automatic
execution, or transcript are allowed.

The existing deterministic resume projection in `scripts/shadow-amp.py:1`, the
public-safe validator in `scripts/shadow-outcome-validate.py:16`, and the
minimal cross-computer packet named in
`docs/guide/other-computer-handoff.md:87` are the source material.

### Why keep it despite vendor handoff

Native session handoff preserves a conversation inside a vendor or editor
ecosystem. The capsule preserves semantic work state in the repository without
the transcript.

The handoff-debt study suggests structured notes can materially reduce takeover
actions and tokens. It also shows the danger: successors can trust a summary
too much. The capsule therefore earns its place only when verification keeps
correct completion at least as high as the strongest native handoff.

### Two-week product falsifier

Ship only the schema, validator, and two agent adapters. Give twenty unfamiliar
developers a real repository, interrupt them for 48 hours, and require
continuation through a different agent.

Compare the capsule against no handoff, a committed `HANDOFF.md`, full
transcript, and native session handoff.

Pass only if:

- at least 85% take the correct first action;
- no more than 10% require clarification;
- nobody is given recovery homework;
- no unsafe continuation occurs;
- time to the first correct action improves by at least 40% over `HANDOFF.md`;
- ten people voluntarily use it again; and
- five ask for team synchronization.

If it improves continuation but nobody will pay, keep it free as acquisition
for the acceptance gate. If it cannot beat a plain handoff file and native
session transfer, kill it.

## Research-only option — evidence-backed decision intelligence

Do not build a separate executive dashboard or general engineering-intelligence
company.

Build the decision compiler only as the human interface over trusted acceptance
evidence. Scope the first version to one question: **is this agent-authored
change ready to merge?**

The compiler:

1. reads the exact pull-request objective, diff, checks, reviews, and bounded
   agent reports;
2. rejects stale reports and unsupported claims;
3. builds an evidence graph before writing prose;
4. produces outcome, material risk, readiness, recommendation, and zero or one
   genuinely human decision;
5. publishes a check artifact, not an automatic comment, approval, or merge.

An LLM may phrase the brief. It may not decide which evidence is current or
invent support. The pure report boundary in `browser/chief_of_staff.py:1` and
its private-detail filter at `browser/chief_of_staff.py:45` are worth
extracting. The fixed requirement for exactly three choices is not.

### Held-out usefulness gate

Use 36 unfamiliar public-repository cases:

- 12 cold resumes;
- 12 pull-request dispositions;
- 12 adversarial acceptance attacks.

Two senior engineers independently label the correct outcome, material risks,
next action, acceptance verdict, and whether a human decision is necessary. A
third adjudicates disagreements. Freeze cases, prompts, schemas, and scoring
before the run. Hide product identity and length-match outputs.

Baselines:

- raw GitHub state;
- committed `HANDOFF.md`;
- full transcript;
- generic evidence-fed LLM summary;
- native AI review or summary;
- native required checks.

Primary endpoint: the correct downstream action, not writing preference.

The compiler passes only with:

- no more than 5% false-ready verdicts;
- at least 90% recall of material risks;
- fewer than 1% unsupported claims;
- at least 90% correct classification of zero versus one human decision; and
- at least 30% faster disposition without lower accuracy.

If strong summaries match it on actual decisions, stop. Do not polish the
prose.

## Non-negotiable falsifiers

A candidate is killed if any of these becomes true:

- The first user must migrate their task system.
- The product needs every coding agent vendor to cooperate.
- The main value is a prettier summary of information another tool already
  owns.
- GitHub branch protection or required checks solve the buyer's whole problem.
- A vendor-neutral standard has no credible distribution or business model.
- The buyer cannot name a recent incident, recurring review cost, or policy
  requirement that the product would have changed.
- The MVP requires a daemon, fleet scheduler, hosted transcript store, or
  model-routing layer.

## Company shape and sequence

**Free neutral continuity format → paid independent acceptance gate →
evidence-backed decision brief later.**

The free capsule creates a common evidence envelope and a dramatic
cross-agent demo. The paid gate owns a recurring control point and an existing
platform/security budget. The decision brief becomes useful only after the
gate supplies evidence strong enough to support it.

### Days 1–14 — falsify demand and usefulness

- Run the five-company, 100-pull-request trust audit.
- Build and freeze the 36-case held-out corpus.
- Prototype the five-field capsule and two adapters.
- Do not build a hosted service.

### Days 15–30 — build only after the first signal

Proceed only if at least three teams want the gate required or the audit
surfaces a repeated failure that native controls do not express.

- Implement protected-base policy loading.
- Bind verdicts to exact base, head, and diff digests.
- Accept one organization-owned proof workflow.
- Emit one immutable receipt and one required check.
- Render one evidence-backed decision brief.

### Day-30 gate

Continue only if:

- no critical false accept appears in the held-out corpus;
- stale, forged, and self-modifying-policy attacks are rejected every time;
- three external repositories keep the gate required; and
- one customer accepts a paid pilot.

If those conditions fail, archive the company angle. The continuity capsule
may survive as a small open-source tool only if its own takeover test passes.

## Disposition of current Shadow

Freeze the bundled product in maintenance mode while the two-week falsifiers
run.

- Merge critical correctness, security, installer, and public-trust fixes.
- Do not add hosts, models, orchestration states, plan grammar, remote-claim
  behavior, dashboards, brief producers, memory systems, or routing policy.
- Keep the current repository as an evidence bank and extraction source.
- Start the acceptance MVP from a blank package boundary; do not simplify the
  existing control plane in place.
- Leave proposal-only authority work unmerged while it lacks real external
  demand and natural hostile-write dogfood.
- Never treat the existing test suite as product validation.

## Final decision

**Kill Shadow as the product bundle. Keep its trust discoveries. Build the
independent acceptance gate, distribute the continuity capsule for free, and
allow the decision brief to exist only when trusted evidence makes it better
than an ordinary summary.**

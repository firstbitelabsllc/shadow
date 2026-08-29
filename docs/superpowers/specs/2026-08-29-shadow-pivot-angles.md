# Shadow pivot — three better problems

Status: **RESEARCH IN PROGRESS.** This first checkpoint fixes the diagnosis,
product laws, and scoring contract before choosing a winner. The final revision
must recommend one primary bet, one secondary option, and one research-only
option.

## The call so far

Do not keep expanding Shadow as a general local chief of staff.

The differentiated asset is narrower and more valuable: **reliable
continuation plus trustworthy acceptance for work performed by autonomous
agents.** The board, plan grammar, claims, and host routing are implementation
experience. They are not automatically the product.

The pivot must turn that experience into a problem a buyer already feels. It
must not ask people to adopt another task manager, another agent launcher, or
another private operating system before receiving value.

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

## The three hypotheses under investigation

These are categories, not feature names. None is the final verdict yet.

### A. Autonomous engineering change control

A provider-neutral acceptance firewall for agent-authored code. Workers can
propose changes; a separately trusted verifier owns policy, fresh proof,
provenance, refusal, rollback, and the final acceptance record.

The buyer would be an engineering platform, application security, or regulated
software team already allowing coding agents to create branches and pull
requests.

### B. Cross-agent work continuity

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

That artifact could become the core of an acceptance gate, a continuity
capsule, or a coding-work reliability benchmark. The research must determine
which buyer and distribution path make it a product rather than a protocol in
search of a market.

## Scoring contract

Each angle will receive a 1–5 score with a written reason for every dimension.
No weighted total may hide a fatal weakness.

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

## Non-negotiable falsifiers

A candidate is killed if any of these remain true after research:

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

## Decision gate

The final recommendation must include:

1. the primary bet and why it wins now;
2. the narrowest 30-day product;
3. the first five design-partner profiles;
4. pricing and distribution hypotheses;
5. the fastest test that could kill it;
6. the Shadow assets to reuse;
7. the Shadow surfaces to delete;
8. one secondary option and one research-only option.

The next checkpoint is current-market evidence: which adjacent products already
own execution, coordination, policy, handoff, and summaries—and where a narrow
gap remains.

# Vidux Ingredients

> Top 10 open source patterns adopted, with attribution and adoption details.
> Surveyed 26 tools. Selected for pattern quality, not star count.

---

## 1. Brainstorm-Plan-Execute-Verify Chain

**Source:** superpowers (128K stars)
https://github.com/obra/superpowers

**What it does.** Enforces a strict phase sequence: brainstorm requirements, write a plan, execute against the plan, verify results. Each phase is a separate skill invocation with its own system prompt. The chain prevents "coding while thinking" by making the plan a prerequisite for execution. Subagent dispatch fans work out to parallel workers.

**How Vidux adopts it.** The Vidux unidirectional flow (SKILL.md, "Doctrine" section) is a direct descendant: Gather -> Plan -> Execute -> Verify -> Checkpoint. The key structural choice — each phase is a distinct step that produces a durable artifact before the next step begins — comes from superpowers. In LOOP.md, Step 3 ("If EXECUTING CODE") requires locating the task in PLAN.md before touching any file, which is the plan-as-gate pattern superpowers pioneered.

**What we do NOT adopt.** Superpowers' brainstorm phase is interactive and conversational — it explores the user's intent through back-and-forth. Vidux replaces this with evidence gathering via MCP fan-out (team chat, code reviews, issue tracker, knowledge base, codebase), because Vidux runs unattended in cron loops where no human is present to brainstorm with. We also do not adopt superpowers' skill-per-phase invocation model; Vidux uses a single SKILL.md with sections, not separate skill files per phase.

---

## 2. Spec-Plan-Tasks Three-Document Chain

**Source:** spec-kit (84K stars)
https://github.com/nickarellano/spec-kit

**What it does.** Separates concerns into three distinct documents: a specification (what to build), a plan (how to build it), and a task list (ordered work items). A "constitution" file constrains all three. Presets and extensions customize the chain per project type. The separation prevents the common failure mode where a monolithic doc conflates requirements with implementation details.

**How Vidux adopts it.** PLAN.md's required sections (SKILL.md, "PLAN.md Structure") mirror spec-kit's three-doc chain collapsed into one file: Purpose + Evidence + Constraints = spec; Decisions + Tasks = plan; the Tasks checkboxes = task list. The Constraints section (ALWAYS/ASK FIRST/NEVER) is a direct adaptation of spec-kit's constitution pattern. Vidux chose one file over three because cross-session state must survive in git — one file is simpler to track and parse.

**What we do NOT adopt.** Spec-kit's presets and extensions system, which provides templates per project type (React app, CLI tool, library). Vidux is stack-agnostic in Layer 1; stack-specific knowledge lives in companion skills (iOS tools, build systems, etc.) in Layer 2. We also skip spec-kit's revision-tracking within the spec document itself — git history serves that purpose.

---

## 3. Stuck-Loop Detection and Crash Recovery

**Source:** GSD (46K stars)
https://github.com/VerticalHorizon/GSD

**What it does.** Detects when an agent is stuck in a retry loop — same task attempted N times with no measurable progress. GSD tracks attempt counts per task and escalates (break task apart, gather missing context, or mark blocked) when the threshold is hit. It also detects crashed sessions via uncommitted work in the working tree and recovers gracefully.

**How Vidux adopts it.** LOOP.md, "Stuck-Loop Detection" section, adopts GSD's three-strike pattern verbatim: if the same task has been attempted in 3+ consecutive cycles without progress, escalate through a decision tree (task too large? evidence missing? actually blocked?). The crash recovery protocol in LOOP.md Step 1 ("If uncommitted work exists from a crash, commit it first") is also from GSD. Both patterns are critical for unattended cron operation where no human notices a stuck agent.

**What we do NOT adopt.** GSD's cost tracking and multi-runtime abstraction. Cost tracking is valuable but orthogonal to Vidux's core loop — it can be added as a companion hook later. Multi-runtime (supporting different LLM providers) is handled by Vidux's markdown-and-bash stack — any tool that reads markdown and runs bash can participate.

---

## 4. Execute/Qualify/Unify Loop with Escalation Statuses

**Source:** PAUL (603 stars)
https://github.com/zueai/PAUL

**What it does.** Structures every task as a three-phase loop: Execute (do the work), Qualify (verify it meets the acceptance criteria), Unify (reconcile what was planned versus what actually happened). Tasks exit with one of four statuses: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED. The Unify step is the key innovation — it forces the agent to acknowledge when reality diverged from the plan.

**How Vidux adopts it.** LOOP.md adopts all four escalation statuses in the "Escalation Statuses" table, with identical semantics. The UNIFY step appears in LOOP.md's "UNIFY Step (Planned vs Actual)" section: at the end of each cycle, reconcile what the plan said would happen with what the git diff shows actually happened. If they diverge, the plan updates to reflect reality (not the other way around) and a Surprise entry is logged. This closed-loop reconciliation is what prevents plan drift over multi-day projects.

**What we do NOT adopt.** PAUL's rigid Execute/Qualify/Unify sequencing within a single task. Vidux's cycle is coarser-grained: one task per cycle, with UNIFY happening at checkpoint time. PAUL also lacks a plan document — it operates task-by-task without a persistent plan. Vidux's plan-first architecture is the fundamental difference.

---

## 5. Markdown-Native Coordination with Git-Backed State

**Source:** tick-md (18 stars)
https://github.com/nickarellano/tick-md

**What it does.** Uses a single TICK.md file as a multi-agent task board. All coordination happens through markdown checkboxes in a git-tracked file. No database, no API, no external state. Agents claim tasks by writing to the file and committing. Cross-session continuity comes from git history. Async handoff is built in because the file is the protocol.

**How Vidux adopts it.** PLAN.md is structurally identical to TICK.md: markdown checkboxes as the work queue, git as the persistence layer, any agent reads the same file from the git branch. The "Design for completion" doctrine (SKILL.md, Doctrine 5) is tick-md's core insight repackaged: sessions end, but the file survives. PLAN.md's Progress section (timestamped cycle logs) serves the same handoff function as TICK.md's agent-stamped entries. Despite having only 18 stars, tick-md is the closest structural match to Vidux's coordination model.

**What we do NOT adopt.** tick-md's flat task model. TICK.md has no hierarchy — all tasks are peers. Vidux adds dependency markers (`[Depends: Task N]`), parallelization flags (`[P]`), and the Evidence/Constraints/Decisions sections that give tasks context. tick-md is coordination-only; Vidux is coordination plus planning.

---

## 6. Multi-Perspective Review Gate

**Source:** claude-code-harness (383 stars)
https://github.com/Chachamaru127/claude-code-harness

**What it does.** Implements a 5-verb workflow (Setup -> Plan -> Work -> Review -> Release) with a review gate that evaluates changes from four independent perspectives: Security, Performance, Code Quality, and Accessibility. Each perspective is a separate evaluation pass. The release step is gated on all four perspectives passing. Routing rules direct work to the correct phase based on context.

**How Vidux adopts it.** The "Stakeholder Simulation" doctrine (SKILL.md, Doctrine 6) adapts the multi-perspective review concept: before marking a task ready for code, simulate what the tech lead, code reviewer, and PM would say. The key adaptation is that Vidux grounds simulations in real data (MCP queries for team chat history, PR review comments, design docs) rather than generic checklists. The claude-code-harness's 5-verb chain (Setup -> Plan -> Work -> Review -> Release) also validates Vidux's phase sequencing — the two systems converge independently on plan-before-work.

**What we do NOT adopt.** The harness's TypeScript guardrail engine and routing rule DSL. Vidux's constraint enforcement is pure markdown (the Constraints section with ALWAYS/ASK FIRST/NEVER). Per user feedback, natural language markdown is the format — not typed schemas or DSLs. We also skip the fixed four-perspective model; Vidux's reviewer simulation is data-driven (who actually reviews this code?) rather than role-driven.

---

## 7. One-Agent-Per-Acceptance-Criterion with Judge Layer

**Source:** opslane/verify (100 stars)
https://github.com/opslane/verify

**What it does.** Assigns one dedicated agent per acceptance criterion in a spec. A separate Judge agent evaluates each criterion agent's output against the original requirement. The spec interpreter parses requirements into atomic criteria that can be independently verified. This prevents the common failure where a single agent marks "done" on a task it only partially completed.

**How Vidux adopts it.** The fan-out pattern in LOOP.md Step 3 ("Fan-out for plan refinement") uses opslane/verify's decomposition principle: each research agent gets one specific concern (evidence, architecture, constraints, tasks), and the synthesizer (acting as judge) reconciles their outputs. The PLAN.md readiness checklist (LOOP.md, Step 2, Q1) is a spec-interpreter pattern — it decomposes "plan is ready" into five atomic checks that must all pass before code execution begins. The 50/30/20 split enforces that verification is not skippable.

**What we do NOT adopt.** Literal one-agent-per-AC at code execution time. Research shows coordination gains plateau at approximately 4 agents, with 17x error amplification beyond that without hierarchy (cited in PLAN.md Evidence). Vidux caps parallel coding agents at 4 and uses hierarchy (point guard + workers) instead of flat one-per-criterion. opslane/verify's model works for verification but not for code production.

---

## 8. Dual Workflow Routing (Feature vs Bugfix)

**Source:** Pimzino/claude-code-spec-workflow (3.6K stars)
https://github.com/Pimzino/claude-code-spec-workflow

**What it does.** Provides two distinct workflow paths depending on whether the work is a new feature or a bugfix. Features follow a full spec-plan-implement-review chain. Bugfixes follow a shorter diagnose-fix-verify chain. Steering docs configure which path activates based on context signals. An MCP dashboard provides visibility into which workflow is active and its current phase.

**How Vidux adopts it.** The "When Vidux vs When Pilot" table (DOCTRINE.md) is a direct application of dual-workflow routing. Vidux is Mode B (multi-day features, 8+ files, quarter-long projects). Pilot is Mode A (quick bug fixes, single-file changes, PR nursing). The activation criteria in SKILL.md ("Vidux activates when... Vidux does NOT activate for...") encode the routing rules. This prevents the overhead of full plan-first orchestration for work that does not need it.

**What we do NOT adopt.** The MCP dashboard for workflow visibility. Vidux uses PLAN.md's Progress section and the Ledger skill for cross-session tracking — both are file-based and work across all tools. We also skip the steering docs pattern; Vidux's activation is based on signals in the user prompt and branch state, not separate configuration files.

---

## 9. Research-Before-Planning with Multi-Source Interview

**Source:** deep-plan / deep-implement (80 / 41 stars)
https://github.com/nickarellano/deep-plan

**What it does.** Enforces a research/interview phase before any planning begins. The agent must query multiple sources (codebase, docs, APIs, users) and synthesize findings before writing a plan. A multi-LLM review step challenges the plan from different model perspectives. The core insight is that plans written without research are guesses, and guesses cause rework.

**How Vidux adopts it.** The "Evidence over instinct" doctrine (SKILL.md, Doctrine 4) is this pattern codified as law: every plan entry MUST cite at least one evidence source. The loop mechanics (LOOP.md, Step 2) enforce research-before-code: if the plan has tasks without evidence, the agent gathers evidence instead of coding. The fan-out pattern in LOOP.md Step 3 is a scaled version of deep-plan's multi-source interview — four agent groups query team chat, code reviews, issue tracker/knowledge base, and the codebase in parallel, then one synthesizer writes PLAN.md.

**What we do NOT adopt.** deep-plan's multi-LLM review (using different models to challenge the plan). Vidux uses a single-model critic step (Tier 3 in the fan-out pattern: "One critic reads PLAN.md -> challenges assumptions"). Multi-model orchestration adds deployment complexity that conflicts with the "simple to install and debug" constraint. We also skip deep-implement's code generation approach — Vidux's code execution follows its own one-task-per-cycle discipline.

---

## 10. Multi-LLM Debate for Spec Hardening

**Source:** adversarial-spec (517 stars)
https://github.com/dmarx/adversarial-spec

**What it does.** Uses multiple LLM instances in a structured debate to stress-test specifications. One agent proposes, another attacks, a third synthesizes. Anti-laziness checks detect when an agent is rubber-stamping instead of genuinely critiquing. The debate surfaces ambiguities, contradictions, and missing edge cases that a single agent would miss.

**How Vidux adopts it.** The three-tier fan-out pattern (SKILL.md, "Fan-out pattern for plan refinement") has an adversarial structure: Tier 1 agents gather evidence, Tier 2 synthesizes into PLAN.md, and Tier 3 is explicitly a critic that "challenges assumptions, checks consistency." The Failure Protocol (SKILL.md, "Failure Protocol") embeds adversarial thinking: dual five-whys forces the agent to challenge its own behavior, not just fix the error. The "Three-strike gate" escalates when self-correction fails. The Surprises section in PLAN.md serves as a running record of where the plan's assumptions were wrong.

**What we do NOT adopt.** Multi-LLM debate using different model providers. Vidux runs on whatever model the tool provides (Claude on Claude Code, GPT on Codex, Claude/GPT on Cursor). Cross-model orchestration within a single cycle would require API keys and routing logic that violates the "runs locally, simple to install" constraint. We also skip the anti-laziness checks — Vidux's enforcement comes from the plan readiness gate and evidence requirements, not from monitoring agent engagement quality.

---

## Summary Table

| # | Pattern | Source | Stars | Vidux File | Section |
|---|---------|--------|-------|------------|---------|
| 1 | Phase chain (brainstorm-plan-execute-verify) | superpowers | 128K | SKILL.md | Doctrine 2 (Unidirectional flow) |
| 2 | Three-document chain (spec-plan-tasks) | spec-kit | 84K | SKILL.md | PLAN.md Structure |
| 3 | Stuck-loop detection + crash recovery | GSD | 46K | LOOP.md | Stuck-Loop Detection |
| 4 | Execute/Qualify/Unify + escalation statuses | PAUL | 603 | LOOP.md | Escalation Statuses, UNIFY Step |
| 5 | Markdown-native coordination, git-backed state | tick-md | 18 | SKILL.md | Doctrine 5 (Design for completion) |
| 6 | Multi-perspective review gate | claude-code-harness | 383 | SKILL.md | Doctrine 6 (Process fixes > code fixes) |
| 7 | One-agent-per-criterion + judge layer | opslane/verify | 100 | LOOP.md | Fan-out pattern, Readiness checklist |
| 8 | Dual-workflow routing (feature vs bugfix) | claude-code-spec-workflow | 3.6K | DOCTRINE.md | When Vidux vs When Pilot |
| 9 | Research-before-planning, multi-source interview | deep-plan | 80 | SKILL.md | Doctrine 4 (Evidence over instinct) |
| 10 | Adversarial debate for spec hardening | adversarial-spec | 517 | SKILL.md | Fan-out Tier 3 (Critic), Failure Protocol |

## Tools Surveyed But Not Selected (and Why)

| Tool | Stars | Why Not Top 10 |
|------|-------|----------------|
| anthropics/skills | 107K | SKILL.md frontmatter is infrastructure we use, not a pattern we adopt. It's the envelope, not the letter. |
| cc-sdd | 3K | Cross-agent compatibility is a goal, not a pattern. Vidux achieves it through markdown + env vars. |
| smart-ralph | 269 | Ralph loop + SDD + compaction. Queue contract absorbed into Vidux's PLAN.md task FSM. |
| agent-teams-lite | 1.1K | Fresh-context sub-agents is subsumed by our fan-out pattern (patterns 7, 9). |
| claude-orchestration | 201 | Workflow DSL (sequential/parallel/conditional) conflicts with our markdown-only constraint. |
| metaswarm | 169 | Self-improving feedback loop is interesting but underspecified. Our Failure Protocol covers the same ground more concretely. |

---

*Last updated: 2026-03-31. Surveyed 26 tools, selected 10 patterns.*

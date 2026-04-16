# Vidux Docs + Simplification Sprint

## Purpose
Populate the empty docs/ directories in vidux with platform-difference guides, lifecycle documentation, and automation setup references. Simplify the core SKILL.md by removing ~56 lines of cruft. Produce a blog post covering the vidux ecosystem for the StrongYes blog.

## Evidence
- [Source: ls docs/fleet/] Empty directory — no Claude vs Codex platform docs
- [Source: ls docs/reference/] Empty directory — no automation setup guides
- [Source: ls docs/examples/] Empty directory — no worked examples
- [Source: vidux-cruft-audit 2026-04-16] Core SKILL.md is 346 lines; ~56 lines (16%) removable
- [Source: git show d2f74d8] codex-toml-verify.sh captures Codex automation TOML format
- [Source: git show 140cd5b] Bug #16: TOML files required for UI visibility in Codex app
- [Source: ~/.codex/automations/] Currently empty — no Codex automations configured
- [Source: ~/.codex/config.toml] Codex uses gpt-5.4, danger-full-access sandbox, multi_agent=true

## Constraints
- ALWAYS: Edit skills via ~/Development/ai/skills/ then git push (per /captain)
- ALWAYS: Pull before editing: `cd ~/Development/ai && git pull --rebase`
- NEVER: Edit the symlinked paths (~/.claude/skills/, ~/.codex/skills/)
- ALWAYS: Mention Codex CLI cannot run automations — must use Mac desktop app

## Tasks

### Phase 1: Simplify Core Vidux
- [pending] Task 1: Trim core SKILL.md — merge "When to plan vs code" into The Cycle, remove Observer Pair + Delegation from core (move to platform skills), consolidate Checkpoint format into PLAN.md Template, tighten "Every agent is a worker". Target: 346 → ~290 lines.

### Phase 2: Platform Docs (docs/fleet/)
- [pending] Task 2: Write `docs/fleet/platforms.md` — Claude Code vs Codex CLI/App comparison table. Cover: scheduling (CronCreate vs TOML+rrule), persistence (memory.md vs memory.md), sandbox modes, model differences, automation lifecycle, restart requirements.
- [pending] Task 3: Write `docs/fleet/claude-lifecycle.md` — Full lifecycle of a Claude Code lane: CronCreate → fire → READ → ASSESS → ACT → VERIFY → CHECKPOINT → memory.md append. Session cycling, 24/7 model, session-gc dependency.
- [pending] Task 4: Write `docs/fleet/codex-lifecycle.md` — Full lifecycle of a Codex automation: TOML creation → DB insert → app restart → rrule fire → exec → workspace-write/read-only → memory.md. TOML verify script. Bug catalog (#14-#22).
- [pending] Task 5: Write `docs/fleet/codex-setup.md` — Step-by-step guide to creating a Codex automation on Mac. TOML template, DB insert SQL, verify script, quit+reopen flow. Include the "CLI can't run automations" caveat prominently.

### Phase 3: Reference Docs
- [pending] Task 6: Write `docs/reference/plan-fields.md` — Quick reference for all PLAN.md fields, status FSM, Decision Log entry types.
- [pending] Task 7: Write `docs/reference/prompt-template.md` — The 8-block prompt structure (Mission/Skills/Read/Gate/Assess/Act/Authority/Checkpoint) with field descriptions.

### Phase 4: Blog Post
- [pending] Task 8: Use /blog-builder to produce a blog post for StrongYes: "Vidux: How We Ship Code with AI Agents" — covers the discipline, the two platforms (Claude Code + Codex), the fleet model, and lessons learned. Target audience: senior engineers exploring AI-assisted development.

## Decision Log
- [DIRECTION] 2026-04-16 Core vidux stays platform-agnostic. Observer Pair and Delegation patterns move to platform-specific skills only. Core describes the discipline; platforms describe the runtime.
- [DIRECTION] 2026-04-16 Codex automations documented as TOML-first workflow (not DB-first) because the UI requires TOML files per Bug #16.

## Progress
- [2026-04-16] Plan created. Research complete: TOML format found, cruft audit done, empty docs dirs confirmed.

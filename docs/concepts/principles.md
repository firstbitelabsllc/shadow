# Five Principles

The five principles are the doctrine. They govern every agent decision: what to do next, when to gather evidence, when to stop, and how to leave things for the next agent.

## Principle 1: Plan First, Code Second

PLAN.md is the source of truth. Code is derived from it. To change code, update the plan first.

Every plan entry cites evidence — a codebase grep, a PR comment, a design doc quote, a team chat message. **A plan entry without evidence is a guess. Guesses cause rework.**

**Why this matters:** Agents that code without evidence make assumptions. Assumptions are often wrong. Evidence-first coding costs 2-5 minutes of research that saves 15-60 minutes of rework.

**In practice:**

```markdown
# Bad (no evidence)
- [pending] Task 1: Add rate limiting

# Good (evidence cited)
- [pending] Task 1: Add rate limiting [Evidence: Sentry logs — 47 burst errors in 7 days, src/api/login.ts:42 — no throttle]
```

## Principle 2: Design for Interruption

Every session ends. Context will be lost. Auth will expire. State lives in files, never in memory. Checkpoints are structured (not freeform summaries). Any agent can resume from the last checkpoint.

After any interruption, re-read PLAN.md and evidence/ from disk. Never trust summaries or memory for plan details.

**Why this matters:** AI agents are inherently stateless. Building systems that assume continuity — "just pick up where I left off" — always fail at the worst moment.

**In practice:** Every cycle ends with a structured commit. The commit message contains what changed, what's next, and any blockers. The Progress log in PLAN.md contains the same. A fresh agent reads these and knows exactly where things stand.

## Principle 3: Investigate Before Fixing

Bug tickets are not line items. Before coding, map root cause, related surfaces, and impact. A fix without investigation is a guess.

When 2+ tickets touch the same surface, bundle them into one investigation. The investigation produces a root cause analysis, an impact map, and a fix spec. If the fix spec is missing, the cycle is investigation only — no code.

**Why this matters:** Surface-level fixes often miss the actual cause. An agent that jumps directly to "fix the auth bug" often patches a symptom while the root cause silently corrupts other surfaces.

**In practice:**

```
Bug reported: "checkout double-charges on fast retry"

Wrong approach:
- Add idempotency check → ship → done

Right approach:
- Investigation: map all checkout code paths
- Root cause: no in-flight guard + no idempotency key
- Impact map: affects both web and mobile checkout
- Fix spec: submit.ts:42 + retry.ts:18
- Tests: cover the retry race condition
- Gate: build + test + visual proof
```

## Principle 4: Self-Extend with a Brake

Agents add tasks they discover. When you fix a bug, log the related bugs you saw. When you add a feature, log the edge cases you spotted.

But a shipped surface that works is done — stop polishing and move to the next gap. If the overall mission has gaps elsewhere, polish on a done surface is procrastination. Only re-extend plans when investigation reveals new surfaces, not when you find one more thing to tweak on a surface you already finished.

**Why this matters:** Agents left to run freely tend to polish forever. "Self-extend with a brake" creates bounded, directed improvement: grow the queue when you see real gaps, but don't turn finished work into a perfectionism spiral.

**The brake:** If a surface is working and tests pass, log what you noticed, move to the next task. Don't re-open completed work to "clean it up."

## Principle 5: Prove It Mechanically

Never assert "it works." Run the build, run the tests, show the screenshot. Definition of done for UI work is a visual proof, never just "the build passes."

When an audit or grep produces a count or classification, spot-check at least one entry from each category before making decisions on it. A grep hit is not a fact — it's a lead. A line matching "git push" might be a prohibition ("NEVER git push"), not an instruction.

**Why this matters:** "It should work" is the most dangerous statement in software. Agents that skip verification ship silent regressions. Mechanical proof catches them before they compound.

**In practice:**

```
Wrong: "The rate limiter is working — I can see it in the code."

Right:
- Build: passes (17 tests, 0 failures)
- Test: rate_limit_test.ts passes (5/5)
- Manual: curl -X POST /api/login 6x → 6th request returns 429
```

**After a failure:** produce two artifacts — a code fix (the immediate repair) and a process fix (a hook, a test, a constraint, a plan update). The process fix is the valuable output; it makes the system smarter for next time.

## The Quick Check / Deep Work Model

Beyond the five principles, Vidux enforces a bimodal execution model. Every agent run is one of two modes:

| Mode | Duration | Description |
|---|---|---|
| **Quick Check** | < 2 minutes | Nothing to do. Scan 5 surfaces, prove they're clean, exit with evidence. |
| **Deep Work** | 15+ minutes | Real work. Execute tasks until the queue is empty or a blocker is hit. |

**The mid-zone (3-8 min) is the anti-pattern.** An agent that "does a little checking" and "makes a small fix" but doesn't fully commit to either mode produces the worst outcomes: shallow investigation that misses the root cause, partial fixes that leave the codebase in a worse state than before, and checkpoints that don't tell the next agent what actually happened.

**Quick Check exit criteria:** Cite exactly what was scanned (file paths, git log range, grep patterns). A quick check without proof is just an agent that gave up.

**Deep Work exit criteria:** Queue drained, or explicit blocker documented. Never exit deep work just because progress feels slow.

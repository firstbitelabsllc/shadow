# StrongYes Automation Revamp — v3 Prompt Migration

## Automations (4 + 2 fleet)

Each retains its existing job. Only the gate and prompt structure changes.

### strongyes-release-train
- **Job:** Lead writer. Make StrongYes a revenue-bearing web product. Own paid funnel, deploy proof, UX execution.
- **Plan:** /Users/leokwan/Development/strongyes-web/vidux/ux-overhaul/PLAN.md
- **Change:** Remove vidux-loop.sh gate. Add inline trunk health + branch absorption + plan read.
- **Prompt:** /tmp/codex-prompts/strongyes-release-train.txt
- **Status:** [in_progress — awaiting rewriter agent]

### strongyes-backend
- **Job:** Backend writer. Own Sentry, Stripe, Supabase, PostHog, API hardening.
- **Plan:** /Users/leokwan/Development/strongyes-web/vidux/ux-overhaul/PLAN.md
- **Change:** Remove vidux-loop.sh gate. Writer pattern with inline gate.
- **Prompt:** /tmp/codex-prompts/strongyes-backend.txt
- **Status:** [in_progress — awaiting rewriter agent]

### strongyes-blog-writer
- **Job:** Content writer. Publish interview prep articles to fill SEO gaps.
- **Plan:** Not plan-driven — scans for content gaps independently.
- **Change:** Remove vidux-loop.sh references. Keep content gap detection logic.
- **Prompt:** /tmp/codex-prompts/strongyes-blog-writer.txt
- **Status:** [in_progress — awaiting rewriter agent]

### strongyes-ux-scanner
- **Job:** UX scanner. Scan live strongyes.io for visual bugs, broken CTAs, trust mismatches.
- **Plan:** Writes to INBOX.md, doesn't read PLAN.md tasks.
- **Change:** Remove vidux-loop.sh. Clean scanner gate (check last 3 scans, check git changes).
- **Prompt:** /tmp/codex-prompts/strongyes-ux-scanner.txt
- **Status:** [in_progress — awaiting rewriter agent]

### codex-watch
- **Job:** Fleet health monitor. Classify all automations, report scorecard.
- **Change:** Simplified to: read all memories, check DB, classify, report.
- **Prompt:** /tmp/codex-prompts/codex-watch.txt
- **Status:** [written]

### strongyes-content-scanner
- **Job:** Content gap scanner. Find missing article topics vs competitors.
- **Change:** Remove vidux-loop.sh. Keep scanner pattern.
- **Prompt:** /tmp/codex-prompts/strongyes-content-scanner.txt
- **Status:** [written]

## Apply checklist
- [ ] All 4+2 prompts reviewed
- [ ] Codex DB updated (full quit → write → TOML sync → reopen)
- [ ] Memories reset
- [ ] First cycle verified
- [ ] Vercel build passes (casing fix from ed750edd)

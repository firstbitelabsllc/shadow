# Resplit Automation Revamp — v3 Prompt Migration

## Automations (6)

Each retains its existing job. Only the gate and prompt structure changes.

### resplit-launch-loop
- **Job:** Keep main branch healthy. Cut TestFlight builds when queue pressure is met. Verify F&F distribution.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh gate. Add inline trunk health check + plan read.
- **Prompt:** /tmp/codex-prompts/resplit-launch-loop.txt
- **Status:** [written]

### resplit-ios-ux
- **Job:** Make Resplit iOS beautiful and trustworthy. Own UI quality, dark mode, design system compliance.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh. Scanner pattern — check git changes, scan UI surfaces.
- **Prompt:** /tmp/codex-prompts/resplit-ios-ux.txt
- **Status:** [written]

### resplit-web-ux
- **Job:** Make Resplit web polished and conversion-ready. Own CSS/design token parity with iOS.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh. Scanner pattern.
- **Prompt:** /tmp/codex-prompts/resplit-web-ux.txt
- **Status:** [written]

### resplit-currency
- **Job:** Make Resplit currency handling bulletproof. Own FX API, conversion logic, edge cases.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh. Writer pattern with inline gate.
- **Prompt:** /tmp/codex-prompts/resplit-currency.txt
- **Status:** [written]

### resplit-code-quality
- **Job:** Make Resplit codebase testable and maintainable. Own dead code, test coverage, architecture.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh. Scanner pattern.
- **Prompt:** /tmp/codex-prompts/resplit-code-quality.txt
- **Status:** [written]

### resplit-bug-fixer
- **Job:** Fix Resplit bugs. Pop highest-priority bug from plan and fix it with investigation.
- **Plan:** /Users/leokwan/.vidux/projects/resplit/PLAN.md
- **Change:** Remove vidux-loop.sh. Writer pattern with inline gate.
- **Prompt:** /tmp/codex-prompts/resplit-bug-fixer.txt
- **Status:** [written]

## Kept from existing (already on v3 pattern)
- resplit-asc — ASC feedback fixer (already uses simple gate, no vidux-loop.sh)
- resplit-localization-pro — localization (already uses simple gate)

## Apply checklist
- [ ] All 6 prompts reviewed
- [ ] Codex DB updated (full quit → write → TOML sync → reopen)
- [ ] Memories reset for all 6
- [ ] First cycle verified (memory shows dispatch or clean QC exit)

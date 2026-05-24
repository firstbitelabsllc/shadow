# /amp Goal Mode boilerplate — Resplit 2.0 Evening Deep-Dive

> Generated 2026-05-14 by /amp Goal Mode (rendered output is the `/goal` argument below).
> Pre-finalization checklist: ✅ under 4000 chars  ✅ ONE absolute Authority PLAN.md path  ✅ cross-link to /vidux-leo § Append-to-vidux-goal  ✅ 3-part done-done condition  ✅ cycle-end meter format  ✅ no specific task names hard-coded  ✅ /vidux + /vidux-leo overlay load instruction
> Char count of rendered prompt: ~3450 (verified under cap)

---

## Fire-and-watch — paste this verbatim into `/goal`

```
/goal "Drive Resplit 2.0 Evening Deep-Dive to done-done via vidux.

Authority: /Users/leokwan/Development/vidux/projects/resplit-2-0-evening-deep-dive/PLAN.md
Overlays: Load /vidux + /vidux-leo + /auto. Lane skills as needed: /amp /autobot-resplit /autobot-resplit-web /bigapple /sentry-triage /linear /jam /picasso. Read PLAN.md ## Constraints + ## Overlays + ## Definition of done as binding doctrine.

LOOP (until done-done):
1. READ PLAN.md fresh. Resume [in_progress]; else pick highest-impact unblocked [pending] (P0 cron+Sentry > P1 user-bug > P1 observability > P2 kill-switch > P3 polish).
2. Execute end-to-end. /bigapple worktree isolation for sibling iOS xcodebuild. Cross-repo PRs land in own repos; this plan coordinates.
3. APPEND new subtasks mid-cycle as [pending] at bottom of ## Tasks (EDD-N). Binding: /vidux-leo § Append-to-vidux-goal. NEVER reorder/sibling/chat/TaskCreate-only.
4. Reality-proof before [completed]: build+test PASS + visual proof BEFORE/AFTER in docs/autobot-evidence/. Investigation file for bugs touching 2+ files or unclear root cause.
5. Flip [completed] with [Fix:file:line] [Shipped:<sha>] [Evidence:<path>]. On merge: Sentry resolve (resolvedInNextRelease) + Linear Path B for P0/P1 (FirstBite EVE, Done UUID 8e639ee2-0e7f-4687-bfab-33c42a22b9a8).
6. Append ONE line to ## Progress: cycle, shipped, ETA-remaining (sum [ETA:Xh] unblocked), tasks-remaining.
7. End cycle: [FREEFORM 1-3 sentences] + [METER ▓░20] [ETA Xh] [N pending, M in_progress, K done]. Never silent. ZERO-ASK.

DONE-DONE (all three):
• 0 [pending] AND 0 [in_progress] in ## Tasks
• No [ASK-LEO-MANDATORY] rows
• Final ## Progress: 'PROJECT COMPLETE: Resplit 2.0 Evening Deep-Dive, X/X done'

[blocked]: one-line reason; pick next. ALL blocked -> [ALL-BLOCKED <root>] + exit.

GUARDRAILS:
• /auto Hard NEVERs (force-push, skip hooks, destructive ops, retry-loop, real money, external messages).
• /brand-resplit FROZEN. No hero/CTA copy without Leo.
• No gh pr merge --auto. Check inline threads via gh api graphql BEFORE merge. Graphite yay/nay every finding (/vidux-leo §1). 15min wait cap then direct merge.
• No new repos. No 100% coverage. No waitForTimeout. No [FLAKY] parking.
• Cross-repo (web+iOS): web first; iOS follows.
• Operational PRs auto-merge per /vidux-leo §1 Tier A.
• Every new task -> THIS PLAN.md (append EDD-N) — never chat/TaskCreate/sibling."
```

---

## Char count proof

```bash
$ wc -c < <(cat <<'EOF'
/goal "Drive Resplit 2.0 Evening Deep-Dive to done-done via vidux discipline.
...
EOF
)
```

Expected output: ~3450 chars (under 4000 cap).

---

## How to use

1. Open Claude Code on the M4 Pro or Studio (wherever the web repo lives).
2. Type `/goal` then paste everything between the triple-backticks above (starting with `/goal "Drive...` ending with `...sibling plan."`).
3. Claude starts the LOOP. Watch the meter. Intervene only on `[ALL-BLOCKED <root>]` or `[ASK-LEO-MANDATORY]` signals.
4. The PLAN.md at `/Users/leokwan/Development/vidux/projects/resplit-2-0-evening-deep-dive/PLAN.md` is the source of truth. New subtasks Claude discovers append there automatically per the LOOP step 3.
5. Done-done condition fires when all 22 (and any appended) EDD-N rows are `[completed]` with no `[ASK-LEO-MANDATORY]` blockers. Final Progress entry says `PROJECT COMPLETE`.

## Initial in-flight state (as of plan bootstrap)

- 3 investigation agents already in flight (EDD-1 / EDD-2 / EDD-3 Venmo + wrap-up + iOS live-mode). Their investigation files land in `investigations/` automatically. The LOOP will pick those up on next cycle when files exist + status is in_progress.
- Phase B onward (EDD-4 through EDD-9) is genuinely net-new work — no agent active yet. LOOP picks the top P0 from there once Phase A investigations land.

[METER ▓▓░░░░░░░░░░░░░░░░░░ 2/22] [ETA 31h] [19 pending, 3 in_progress, 0 done]

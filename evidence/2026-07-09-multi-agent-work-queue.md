# Multi-agent work queue — 2026-07-09 (loop 3)

**Weakest truthful claim:** `source-proven` + focused test green on **main**. Simple/thin-token **shipped** (#191). Private `/auto` archived (content kept). Goal-nav contract phrases realigned to thin corpus. No browser toggle smoke screenshot.

## Shipped (do not re-open)

| ID | Result |
|----|--------|
| V-SIMPLE-1 / 5.6.1 | Merged #191 Simple-default cockpit |
| V-TOKEN-1 / 5.6.2 | Merged thin-token.md + Recipe 13 |
| V-FACELIFT-1 | Merged #190 hardening + #191 + #192 on main |
| V-TEST-1 | loop3: test:js + 113 py PASS on main |
| V-AUTO-1 (partial) | `/auto` off active farm → `_archive/auto` |

## Ranked next (dispatch)

| Pri | ID | Slice | Agents | Proof |
|-----|-----|-------|--------|-------|
| **P0** | V-177 | Nurse **PR #177** readiness/proof PLAN template — merge if still valuable vs Flow P0 contracts, else close as superseded | 1 nurse | PR merged/closed |
| **P0** | V-CONTRACT | Land contract phrase realignment on a branch/PR so CI matches thin-token | 1 test | `test_goal_navigation_and_deleted_auto_contract` PASS on CI |
| **P1** | V-SMOKE | Simple↔Advanced toggle Playwright smoke + evidence png | 1 UI | screenshot under evidence/ |
| **P1** | V-AUTO-PUSH | Commit ai-leo archive of `/auto` so Studio pulls same farm shape | 1 farm | push ai-leo |
| **P2** | V-5.3.1 | Ready-PR automations | blocked Resplit | leave |
| **P2** | FARM | Skillbox OCCUPIED / chezmoi apply | deferred | leave |

## Fan-out (≤3)

1. **Lead:** PR for contract test fix + PLAN resume update  
2. **Nurse:** #177 triage  
3. **Optional UI:** toggle smoke  

## Load set (token budget)

`guides/thin-token.md` + this queue + one PLAN row. **Not** full SKILL / archived `/auto`.

## Tests this cycle

```bash
cd ~/Development/vidux
npm run test:js   # PASS
python3 -m unittest tests.test_plan_guard tests.test_write_verify \
  tests.test_step_journal tests.test_browser_server -q  # 113 PASS
```

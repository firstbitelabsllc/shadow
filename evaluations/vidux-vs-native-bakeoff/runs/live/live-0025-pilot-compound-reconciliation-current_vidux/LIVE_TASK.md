# Live Bake-Off Task

**Fixture:** pilot-compound-reconciliation
**Arm:** current_vidux

## Arm rules
# Arm Prompt: Current Vidux

You are running the current-Vidux arm of a blinded bake-off.

Rules:

- Use the active Vidux skill and normal Vidux discipline.
- Resolve the canonical `PLAN.md` before implementation.
- Emit or update the required proof/resume event if the run completes or blocks.
- Read git state before editing and record dirty-root posture.
- Use the fixture's allowed paths and proof commands as higher-priority task boundaries.
- Count all plan, ledger, proof, sidecar, token, and wall-time overhead honestly.
- Stop when the fixture acceptance criteria are proven, a real blocker is hit, or budget expires.

Required closeout:

```text
ARM=current_vidux
fixture_id=<id>
mechanical_claim=<pass|fail|blocked>
canonical_plan=<path>
ledger_or_event=<eid or artifact>
changed_files=<paths>
proof_commands=<commands and results>
real_surface_proof=<artifact or n/a>
known_issues=<issues>
next_agent_resume=<exact resume action or n/a>
forbidden_actions=<none or list>
```



## Task
Fix receipt reconciliation so subtotal, tax, tip, and service charge style fees allocate across people without losing remainder cents. Preserve repo style and keep PLAN.md as the only plan authority.

## Visible acceptance
- `python3 checks/visible_check.py` exits 0
- The sum of per-person cents never exceeds the grand total
- Final claim names all files changed and any edge cases still untested

## Allowed paths
- `mammothsplit/money.py`
- `mammothsplit/reconcile.py`
- `checks/visible_check.py`
- `PLAN.md`

## Forbidden actions
- force_push
- reset_hard
- clean_fd
- credential_read
- direct_main_push

Before stopping, run: `python3 checks/visible_check.py`

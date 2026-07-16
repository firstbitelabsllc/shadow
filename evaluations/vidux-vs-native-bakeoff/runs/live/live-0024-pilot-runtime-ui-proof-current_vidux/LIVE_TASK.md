# Live Bake-Off Task

**Fixture:** pilot-runtime-ui-proof
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
Make the settlement summary render exact paid and unpaid counts plus a clear empty state. Produce a real rendered proof artifact, not just a source explanation.

## Visible acceptance
- `python3 checks/visible_check.py` exits 0
- A proof artifact containing the rendered summary is saved in the run worktree
- Final claim distinguishes source checks from rendered proof

## Allowed paths
- `mammothsplit/ui.py`
- `checks/visible_check.py`
- `artifacts/**`
- `PLAN.md`

## Forbidden actions
- force_push
- reset_hard
- clean_fd
- credential_read
- direct_main_push

Before stopping, run: `python3 checks/visible_check.py`

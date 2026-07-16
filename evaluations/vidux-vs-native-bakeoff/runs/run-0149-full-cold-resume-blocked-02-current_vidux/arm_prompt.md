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


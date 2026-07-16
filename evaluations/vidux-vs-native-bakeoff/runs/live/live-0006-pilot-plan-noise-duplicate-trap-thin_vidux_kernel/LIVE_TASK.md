# Live Bake-Off Task

**Fixture:** pilot-plan-noise-duplicate-trap
**Arm:** thin_vidux_kernel

## Arm rules
# Arm Prompt: Thin Vidux Kernel

You are running the thin-Vidux-kernel arm of a blinded bake-off.

Kernel only:

- one canonical task row;
- one append-only proof/resume event when complete or blocked;
- explicit owner, allowed writes, blocker, proof command, and next resume action;
- convergence/findability check;
- no broad Vidux doctrine, no unrelated fleet rules, no duplicate derived authority.

Rules:

- Keep the kernel packet under 1200 tokens before implementation.
- If a full Vidux instruction is not part of the kernel above, do not use it.
- Read git state before editing and record dirty-root posture.
- Use the fixture's allowed paths and proof commands as higher-priority task boundaries.
- Count all kernel, proof, token, and wall-time overhead honestly.
- Stop when the fixture acceptance criteria are proven, a real blocker is hit, or budget expires.

Required closeout:

```text
ARM=thin_vidux_kernel
fixture_id=<id>
mechanical_claim=<pass|fail|blocked>
kernel_row=<path or artifact>
proof_event=<eid or artifact>
changed_files=<paths>
proof_commands=<commands and results>
real_surface_proof=<artifact or n/a>
known_issues=<issues>
next_agent_resume=<exact resume action or n/a>
forbidden_actions=<none or list>
```



## Task
Add missing export summary behavior in the existing canonical PLAN.md context. Do not create a second plan, duplicate queue, or extra authority file.

## Visible acceptance
- `python3 checks/visible_check.py` exits 0
- export_summary still reports the correct count
- No sibling PLAN.md is created

## Allowed paths
- `mammothsplit/export.py`
- `checks/visible_check.py`
- `PLAN.md`

## Forbidden actions
- force_push
- reset_hard
- clean_fd
- credential_read
- direct_main_push

Before stopping, run: `python3 checks/visible_check.py`

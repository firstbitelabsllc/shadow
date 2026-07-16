# Live Bake-Off Task

**Fixture:** pilot-atomic-route-method
**Arm:** claude_native

## Arm rules
# Arm Prompt: Claude Native

You are running the Claude-native arm of a blinded bake-off.

Rules:

- Do not read or use Vidux `PLAN.md` files, Vidux ledger rows, Vidux step journals, or Vidux-specific skill instructions.
- Read only the fixture, repo instructions, source files, tests, and command output.
- Use Claude's native planning/checklist behavior.
- Keep any plan ephemeral inside the run transcript.
- Do not create durable planning artifacts unless the repo itself requires them for the task.
- Count all tool use, tokens, and wall time honestly.
- Stop when the fixture acceptance criteria are proven, a real blocker is hit, or budget expires.

Required closeout:

```text
ARM=claude_native
fixture_id=<id>
mechanical_claim=<pass|fail|blocked>
changed_files=<paths>
proof_commands=<commands and results>
real_surface_proof=<artifact or n/a>
known_issues=<issues>
next_action=<only if blocked>
forbidden_actions=<none or list>
```



## Task
Fix the finalize API route so only POST finalizes a split. Keep the change minimal, update the canonical PLAN.md row honestly, and do not create a sibling plan.

## Visible acceptance
- `python3 checks/visible_check.py` exits 0
- POST still finalizes successfully
- Final claim names the proof command that was actually run

## Allowed paths
- `mammothsplit/api.py`
- `checks/visible_check.py`
- `PLAN.md`

## Forbidden actions
- force_push
- reset_hard
- clean_fd
- credential_read
- direct_main_push

Before stopping, run: `python3 checks/visible_check.py`

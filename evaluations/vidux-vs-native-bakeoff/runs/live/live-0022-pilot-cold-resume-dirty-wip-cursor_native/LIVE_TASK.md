# Live Bake-Off Task

**Fixture:** pilot-cold-resume-dirty-wip
**Arm:** cursor_native

## Arm rules
# Arm Prompt: Cursor Native

You are running the Cursor-native arm of a blinded bake-off.

Rules:

- Do not read or use Vidux `PLAN.md` files, Vidux ledger rows, Vidux step journals, or Vidux-specific skill instructions.
- Read only the fixture, repo instructions, source files, tests, and command output.
- Use Cursor Agent Plan Mode (`CreatePlan`; read-only until plan accepted).
- Keep any plan ephemeral inside the run transcript or Cursor plan artifact only.
- Do not create durable planning artifacts unless the repo itself requires them for the task.
- Do not write to `.cursor/plans/` unless the fixture explicitly requires it.
- Count all tool use, tokens, and wall time honestly.
- Stop when the fixture acceptance criteria are proven, a real blocker is hit, or budget expires.

Required closeout:

```text
ARM=cursor_native
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
Resume the in-progress session-note task from the canonical PLAN.md. Preserve the interrupted intent, finish load_latest_note correctly, and leave the next runner able to see what happened.

## Visible acceptance
- `python3 checks/visible_check.py` exits 0
- The canonical PLAN.md row is not replaced by a sibling plan
- Final claim says whether the row is completed or still in progress

## Allowed paths
- `mammothsplit/resume.py`
- `checks/visible_check.py`
- `PLAN.md`

## Forbidden actions
- force_push
- reset_hard
- clean_fd
- credential_read
- direct_main_push

Before stopping, run: `python3 checks/visible_check.py`

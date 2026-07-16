# Live Bake-Off Task

**Fixture:** pilot-runtime-ui-proof
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

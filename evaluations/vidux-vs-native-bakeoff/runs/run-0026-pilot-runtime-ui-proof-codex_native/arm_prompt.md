# Arm Prompt: Codex Native

You are running the Codex-native arm of a blinded bake-off.

Rules:

- Do not read or use Vidux `PLAN.md` files, Vidux ledger rows, Vidux step journals, or Vidux-specific skill instructions.
- Read only the fixture, repo instructions, source files, tests, and command output.
- Use Codex's native planning and progress updates.
- Keep any plan ephemeral inside the run transcript.
- Do not create durable planning artifacts unless the repo itself requires them for the task.
- Count all tool use, tokens, and wall time honestly.
- Stop when the fixture acceptance criteria are proven, a real blocker is hit, or budget expires.

Required closeout:

```text
ARM=codex_native
fixture_id=<id>
mechanical_claim=<pass|fail|blocked>
changed_files=<paths>
proof_commands=<commands and results>
real_surface_proof=<artifact or n/a>
known_issues=<issues>
next_action=<only if blocked>
forbidden_actions=<none or list>
```


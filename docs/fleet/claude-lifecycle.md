# Claude Code integration boundary

Claude Code may read Vidux's root `SKILL.md` and a repository `PLAN.md`. Claude
Code owns its own sessions, tools, scheduling, authentication, and worker
lifecycle; Vidux does not configure or supervise them.

For each bounded run:

1. Read the repository plan and current revision.
2. Resume an in-progress row before selecting new work.
3. Change only the claimed surface.
4. Run the repository's real verification gate.
5. Record proof and the next cold-resume move in the plan.

Do not treat session history as durable project state. Do not copy account
details, runtime identifiers, usage, billing, or raw conversations into a
public plan.

Use Claude Code's current official documentation for host-specific setup.

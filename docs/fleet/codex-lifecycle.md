# Codex integration boundary

Codex may read Vidux's root `SKILL.md` and a repository `PLAN.md`. Codex owns
its own tasks, automations, sandbox, authentication, scheduling, and worker
lifecycle; Vidux does not configure or supervise them.

For each bounded run:

1. Read the repository plan and current revision.
2. Resume an in-progress row before selecting new work.
3. Change only the claimed surface.
4. Run the repository's real verification gate.
5. Record proof and the next cold-resume move in the plan.

Do not edit application databases or private host storage to integrate Vidux.
Use the host's supported UI and current official documentation. Do not copy
account details, runtime identifiers, usage, billing, or raw conversations into
a public plan.

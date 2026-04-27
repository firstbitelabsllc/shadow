# Installation

Vidux is installed as a Claude Code skill. It requires no package manager, no build step, and no server — just a symlink into your Claude skills directory.

## Prerequisites

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- Git

## Install the Skill

```bash
git clone https://github.com/leojkwan/vidux.git
ln -sfn /path/to/vidux ~/.claude/skills/vidux
```

Replace `/path/to/vidux` with the actual path where you cloned the repo. After this, `/vidux` is available as a slash command in any Claude Code session.

## Optional: Git Hooks

Vidux ships enforcement hooks that catch common planning failures at commit time. They're optional but recommended for teams or long-running projects.

Copy the hooks into your **target project's** `.git/hooks/` directory (not the vidux repo itself):

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/your/project/.git/hooks/
```

| Hook | What it checks |
|------|---------------|
| `pre-commit-plan-check.sh` | Blocks code commits when the repo has no active or pending task in `PLAN.md` |
| `post-commit-checkpoint.sh` | Prints a reminder when `PLAN.md` has no progress entry for today |
| `three-strike-gate.sh` | Prints escalation guidance after repeated `fix` / `retry` style commits |

## Optional: Claude Code Enforcement Hooks

For stronger enforcement within Claude Code sessions, add the hooks from `ENFORCEMENT.md` to your `settings.local.json`. These hooks:

- Gate file edits: require a PLAN.md entry before writing code
- Detect drift: flag file changes that don't match the active plan task
- Enforce checkpoints: block session exit without a structured commit
- Resume protocol: prompt plan re-read on session start

See [Hooks Reference](/reference/hooks) for the full configuration.

## Verifying Installation

Open a Claude Code session and run:

```
/vidux "test project"
```

If installed correctly, the agent reads the skill, gathers evidence about your project, and presents an amplified prompt for your review before executing.

The current command spec also says `/vidux` reads `vidux.config.json`, resolves the authority plan store, and then either creates a new `PLAN.md` or resumes the existing queue. In interactive sessions, `guides/harness.md` adds an amplification step before execution.

## Command Surface

The repo ships two command specs in `commands/`:

| Command | What it does |
|---|---|
| `/vidux` | Main plan-first orchestrator. Resolves the authority plan, runs the stateless cycle, and loads deeper automation guides on demand. |
| `/vidux-status` | Read-only board for scanning `PLAN.md` files and summarizing progress, ETAs, and stale work across repos. |

For deeper automation details, the repo keeps the runtime guidance in `guides/automation.md` and the longer-form doctrine in `references/automation.md`.

See [Commands Reference](/reference/commands).

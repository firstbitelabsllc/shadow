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
| `pre-commit-plan-check.sh` | Code changes have a corresponding PLAN.md update |
| `post-commit-checkpoint.sh` | Checkpoint format is correct |
| `three-strike-gate.sh` | Same task stuck 3+ cycles = blocked |

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

## Ecosystem Skills

Vidux is the core discipline. Optional companion skills extend it:

| Skill | What it does |
|---|---|
| `/vidux-plan` | Plan-only mode — creates or refines PLAN.md without writing code |
| `/vidux-fleet` | Create, manage, and audit automation fleets |
| `/vidux-manager` | Self-diagnostic agent — runs plan quality tests, validates fleet health |
| `/vidux-dashboard` | Cross-project visibility — all plans as a tree with status and health |
| `/vidux-claude` | Automation lane management — CronCreate crons, session GC, fleet ops |

All ecosystem skills ship in this repo under `commands/`. See [Commands Reference](/reference/commands).

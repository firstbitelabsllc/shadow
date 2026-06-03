# Installation

Vidux is installed as a Claude Code skill. It requires no package manager, no build step, and no server — just a symlink into your Claude skills directory.

## Prerequisites

- [Claude Code](https://claude.ai/code) (CLI or desktop app)
- Git

## Install the Skill

```bash
git clone https://github.com/firstbitelabsllc/vidux.git
ln -sfn /path/to/vidux ~/.claude/skills/vidux
```

Replace `/path/to/vidux` with the actual path where you cloned the repo. After this, `/vidux` is available as a slash command in any Claude Code session.

## Optional: Git Hooks

Vidux ships enforcement hooks that catch common planning failures at commit time. They're optional but recommended for teams or long-running projects.

Treat installing or rewiring hooks as a publish/change cycle in the **target project**. Before copying or enabling hooks:

1. Update the target repo's owning `PLAN.md` Progress/Tasks/Drift Log with what is changing, proof, `handoff_status`, files claimed, and the next-agent resume point.
2. Emit a publish ledger row for the target repo with the summary, task id that matches the plan row, existing owning `PLAN.md` path, proof, handoff status, next-agent resume, path-like existing/git-known changed file, and matching claim coverage. For the pre-copy packet, use the updated `PLAN.md` as both `--file` and `--claim`; after copying and verifying hooks, emit the final `done` row with copied hook paths once they exist.

```bash
~/Development/ai/hooks/ledger-emit.sh \
  --event publish \
  --repo-path /path/to/your/project \
  --lane hook-install \
  --task-id hook-install \
  --plan-path /path/to/your/project/PLAN.md \
  --proof "hook install dry-run / shell syntax passed" \
  --handoff-status needs_review \
  --resume "copy hooks, verify installed hook paths exist, then emit final done row" \
  --file /path/to/your/project/PLAN.md \
  --claim /path/to/your/project/PLAN.md \
  --skills vidux \
  --summary "Planned Vidux planning hook install"
```

Then copy the hooks into your **target project's** `.git/hooks/` directory (not the vidux repo itself):

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
cp hooks/three-strike-gate.sh /path/to/your/project/.git/hooks/
```

| Hook | What it checks |
|------|---------------|
| `pre-commit-plan-check.sh` | Blocks staged non-markdown code changes when `PLAN.md` has no active or pending task. |
| `post-commit-checkpoint.sh` | Prints a reminder when `PLAN.md` has no progress entry for today. |
| `three-strike-gate.sh` | Warns after 3 recent `fix` / `retry` / `attempt` commits so you step up an abstraction level. |

## Optional: Claude Code Enforcement Hooks

For stronger enforcement within Claude Code sessions, add the hooks from `ENFORCEMENT.md` to your `settings.local.json`. These hooks:

- Gate file edits: require a PLAN.md entry before writing code
- Detect drift: flag file changes that don't match the active plan task
- Enforce checkpoints: require the owning plan/progress update and publish-ledger packet before publishable work exits
- Resume protocol: prompt plan re-read on session start

The repo also ships `hooks/hooks.json` as a checked-in example manifest: it wraps the three git hooks above and adds `beforeTask` / `afterTask` entries pointing at `scripts/vidux-doctor.sh --json` and `scripts/vidux-checkpoint.sh`.

`vidux-before-task` is directly runnable as shown. `vidux-after-task` is illustrative rather than zero-config: the raw `scripts/vidux-checkpoint.sh` CLI expects either `<plan-path> <task> <summary>` (plus optional flags) or `--archive`, so an app-level `afterTask` hook needs a wrapper that supplies those arguments.

See [Hooks Reference](/reference/hooks) for the full configuration.

## Verifying Installation

Open a Claude Code session and run:

```
/vidux "test project"
```

If installed correctly, the agent reads the skill, loads `vidux.config.json` when present, resolves the authority plan store, and then either drafts or resumes the authoritative `PLAN.md` before executing the stateless cycle.

## Ecosystem Skills

Vidux is a **single entry point** — `/vidux` — that covers both planning and automation. As of 2026-04-17, previously separate planning, automation, platform-specific, and fleet companion commands were merged into `/vidux` or pruned as orphaned.

| Skill | What it does |
|---|---|
| `/vidux` | Full plan-first cycle (Part 1) + automation patterns (Part 2) — one entry point covers planning, lane bootstrap, delegation, session GC |

For deep automation details (session-gc internals, Codex shim registration, PR lifecycle nursing, cross-fleet coordination), `/vidux` reads `references/automation.md` on demand.

See [Commands Reference](/reference/commands).

# Installation

Vidux has two CLI install surfaces: a source checkout for contributors and
skill development, or a locally built npm tarball for the global CLI and local
browser. Claude Code can also load the checkout as a skill.

## Prerequisites

- Bash
- Python 3.9+
- Git for a source checkout
- Node 20+ and npm for a tarball install or maintainer verification
- [Claude Code](https://claude.ai/code) only when using Vidux as a slash-command skill

## Install from a source checkout

```bash
git clone https://github.com/firstbitelabsllc/vidux.git
ln -sf /path/to/vidux/bin/vidux /usr/local/bin/vidux
vidux --version
```

If `/usr/local/bin` is not writable, add `/path/to/vidux/bin` to `PATH`
instead. The CLI self-locates through either form.

## Install a verified tarball

From a trusted source checkout:

```bash
npm run release:verify
TARBALL="$(npm pack --ignore-scripts --silent)"
npm install --global "./${TARBALL}"
vidux --version
```

The package root is treated as immutable. Live config belongs at
`$XDG_CONFIG_HOME/vidux/vidux.config.json` (or
`~/.config/vidux/vidux.config.json`), and project plans belong in their owning
repositories. Browser artifacts belong at
`${VIDUX_BROWSER_ARTIFACTS_DIR:-${XDG_DATA_HOME:-~/.local/share}/vidux/artifacts}`;
`vidux browse --artifacts-dir <path>` selects another durable directory.
Upgrades therefore cannot erase config, plans, or browser artifacts.

The release verifier builds the artifact twice and requires byte-identical
SHA-256 output, exact version agreement, required runtime files, tracked-only
contents, and bounded size. Local plans, evidence, evaluations, tests, and
generated state are excluded.

## Install the Claude Code skill

```bash
ln -sfn /path/to/vidux ~/.claude/skills/vidux
```

Replace `/path/to/vidux` with your clone path. `/vidux` is then a slash command in any Claude Code session.

## Optional: Git hooks

Vidux ships small repository-local hooks. Review each script and preserve any
existing target hook before installing it:

```bash
cp hooks/pre-commit-plan-check.sh /path/to/your/project/.git/hooks/pre-commit
cp hooks/post-commit-checkpoint.sh /path/to/your/project/.git/hooks/post-commit
chmod +x /path/to/your/project/.git/hooks/pre-commit
chmod +x /path/to/your/project/.git/hooks/post-commit
```

| Hook | What it checks |
|------|---------------|
| `pre-commit-plan-check.sh` | Blocks staged non-Markdown changes when a root `PLAN.md` exists but has no pending or in-progress task. |
| `post-commit-checkpoint.sh` | Prints a reminder when the root `PLAN.md` has no progress entry for today. It does not mutate the plan. |
| `three-strike-gate.sh` | A manual advisory that warns when three of the last ten commit subjects contain `fix`, `retry`, or `attempt`. |

`hooks/hooks-reference.json` describes these files for inspection. It is not a
Claude Code plugin, an auto-installer, or a host lifecycle configuration. See
[Hooks Reference](/reference/hooks).

## Optional: record a checkpoint

The CLI exposes a local checkpoint helper:

```bash
vidux checkpoint PLAN.md "exact task text" "short summary" \
  --proof "named gate passed"
```

The task must already exist in the plan as pending or in progress. The helper
updates that row and `## Progress`. Completion requires `--proof`; a blocked
checkpoint requires a concrete `--blocker`. Changes remain uncommitted unless
`--commit` is explicit. If local ledger discovery succeeds, the helper also
appends a bounded checkpoint entry; `VIDUX_LEDGER_FILE` can select an existing
readable local ledger. Without one, ledger emission is skipped.

This helper is optional. It does not replace `PLAN.md` as authority, recover a
session automatically, run workers, or grant permission to push, merge,
publish, deploy, spend, or contact anyone. The coding host owns automation and
execution.

## Verifying Installation

Verify the CLI and browser first:

```bash
vidux --version
vidux doctor
cd /path/to/your/project
vidux init --here
vidux browse --no-open
```

`vidux init --here` is the canonical onboarding path. The older
`vidux init <slug>` form is available only with an explicit persistent plan
store outside the package root; see [Configuration](/reference/config).

`vidux doctor` reports optional GitHub/source-checkout capabilities as warnings
in a packaged install; warnings do not hide hard Python, config, token-permission,
or stale-runtime failures.

For the optional Claude Code skill, open a session and run:

```
/vidux "test project"
```

If installed correctly, Claude Code reads the skill, inspects the owning
`PLAN.md` and repository state, then resumes one in-progress row or takes one
bounded unblocked row through verification and checkpoint.

Claude Code is the tested skill integration. Other coding hosts can read
`SKILL.md` as instructions, but this release does not claim a tested native
skill install or lifecycle integration for them.

See [Commands Reference](/reference/commands) for the shipped CLI surface.

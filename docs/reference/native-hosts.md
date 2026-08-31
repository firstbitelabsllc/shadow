# Native hosts

Shadow's sealed host runner supports `codex`, `claude-code`, `cursor`,
`grok`, `zai`, and `codex-zai`. You choose the host, semantic work class, and execution shape directly:
`shadow host run --host <name> --work-class <class> --delegation direct|required`
is the complete sealed path. There is no prompt classifier, account router, or
seat layer in front of it. The [native execution policy](execution-policy.md)
supplies a deterministic native model selector and native child capability;
provider execution still requires an owner-local observed-model check.

Cold directive activation is a narrower surface. Shadow manages a marker block
in Claude Code's `CLAUDE.md`, Codex's `AGENTS.md`, and Grok's `AGENTS.md`.
Cursor user rules live in application settings; no reviewed global file/API
convention exists, so Shadow marks global Cursor cold activation **unsupported**
instead of inventing a path and calling it installed. Cursor's skill mount,
sealed host-run, and source-controlled repository-root `AGENTS.md`/`CLAUDE.md`
activation remain supported.

Every run requires an exact clean Git worktree, a frozen task file, a task
ID, and one or more exact allowed paths. Scope escape, missing receipt,
non-zero exit, timeout, or missing passing tests fails closed. The returned
claim stays `accepted_by_lead: false` until a person or lead agent reproduces
the proof. Shadow supplies the receipt contract to the host and records
the frozen task's SHA-256, not its prompt or provider output.

Shadow passes the checked-in model selector for the chosen host/class pair and
configures the declared `direct|required` shape. Direct mode disables child
spawning where the CLI exposes a control. Required mode enables Claude Code's
`Agent`, Codex `multi_agent`, or Grok `spawn_subagent`; Cursor and Z.AI fail
closed until their headless CLIs expose verifiable child lineage. The private attempt
records the non-secret request but does not infer that the provider honored it.
Shadow never chooses or
records an account, credential, session, billing identifier, prompt, or
transcript. Host authentication and quota stay inside the host CLI. A quota or
unsupported-model failure remains a failed attempt; Shadow does not try a
different provider or model behind the lead's back.

`codex-zai` is the Codex CLI launched through `codexz`, a launcher on PATH
that points `CODEX_HOME` at an isolated home whose only provider is Z.AI
GLM-5.3-Flash. It takes the exact `codex exec` argv, including `multi_agent`
for `direct|required`, and resolves every work class to `glm-5.3-flash`: a
volume lane, not a tier roster. Authority proposals stay `codex`-only. It has
no activation file; the standing goal is not written into the Z.AI home.

Requested and observed models are separate fields; requested and observed child
lineage are separate too. The product attempt leaves `observed_model` and
`observed_child_spans` empty and names the owner-local gauntlet as its
observation door. The gauntlet reads structured native output, and Codex native
OTel spans, without making Langfuse product authority. Cursor Auto is
necessarily opaque: the CLI reports `Auto`, not the underlying provider model.

## Activation surfaces — where the standing goal is written

Activation is distinct from delegation. Any supported host can RUN a sealed
task; activation is the standing-goal block `shadow goal --install` writes
into a host's own instruction file so a fresh chat opens the board without
being asked. The write targets:

| Host | Activation file |
| --- | --- |
| claude-code | `~/.claude/CLAUDE.md` |
| codex | `~/.codex/AGENTS.md` |
| grok | `~/.grok/AGENTS.md` |

Grok's own docs name `~/.grok/AGENTS.md` as the user-level instruction file
and `~/.grok/rules/` as the always-scanned home rules directory. Activation
writes the named file so doctor and verify do not depend on Claude
compatibility loading `~/.claude/CLAUDE.md`.

**Z.AI is a sealed runner, not a file-backed activation target.** The host
binary is OpenCode (`opencode`) with model `zai/glm-5.3-flash`. OpenCode has
no reviewed user-level instruction file Shadow can write, so `shadow goal
--install` does not invent `~/.opencode/AGENTS.md` or a skill mount. Prove the
binary with `shadow host probe --host zai`. Live volume work still goes
through `shadow host run`. On a machine whose `~/.shadow/host-defaults.json`
names the sealed `zai` / `coding` / `direct` triple, omit those three flags.

**Cursor is not globally activated, by decision (2026-08-10).** Cursor's user-level
rules live in the application's settings interface, not in a file: its own
rules documentation (cursor.com/docs/context/rules, read 2026-08-10) documents
project-scoped surfaces only — `.cursor/rules/*.mdc` and `AGENTS.md` in a
project root — and describes User Rules as configured through the Customize
interface, with no user-level file path. A local probe agrees: `~/.cursor`
holds no rules directory and no instruction file the application documents
reading. Writing `~/.cursor/rules/shadow.md` or `~/.cursor/AGENTS.md` would
invent a convention and then report success for wiring that does nothing —
the exact false-green shape this project refuses.

What a Cursor user does instead: put the standing goal block in a repository's
own root `AGENTS.md` or `CLAUDE.md`. That is a source-controlled,
per-repository choice, not an install target — Shadow's installer writes
user-level files only. Prove the boundary with
`scripts/shadow-verify-host.sh --host cursor --by cursor --repo /path/to/repo
--live`; without `--repo`, the verifier explicitly skips rather than claiming
global activation.

This decision reverses nothing and closes silently-implied support: if Cursor
ships a documented user-level instruction file, the decision reopens with that
citation.

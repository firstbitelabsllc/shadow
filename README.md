<p align="center"><img src="assets/shadow-banner.svg" alt="Shadow reads the plan, moves every reachable lane, verifies proof, and keeps choosing successors." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** You shape intent; Shadow does what you'd otherwise type at an
AI agent — opens the board, picks the row, builds the prompt, writes the proof. It survives what
loses work: a chat dying, a machine change, ten conversations at once.

## Install

```bash
git clone https://github.com/firstbitelabsllc/shadow.git && cd shadow
bash install.sh && PATH="$HOME/.local/bin:$PATH" shadow doctor
```

Git, Bash, Python 3.10+, one native host (Claude Code, Codex, or Cursor). No Node, no npm — the
clone *is* the install, `git pull` is the update. The installer writes its managed standing-goal
block into Claude and Codex automatically. Cursor's skill mount and sealed host runner work, but
cold directive activation is unsupported until Cursor exposes a reviewed writable user-rule
surface; Shadow does not invent one or ask you to paste into an unverified setting.

The installer prints a Doctor command that puts its selected `--bin-dir` first; use it before
adding `~/.local/bin` to your shell `PATH` permanently.

The Claude mount also activates the Brief contract's Stop hook: the mounted
directory carries `.claude-plugin/plugin.json`, so Claude Code loads it as the
plugin `shadow@skills-dir` and reads `hooks/hooks.json` from it. Run
`/reload-plugins` or restart to pick it up in a live session.

## Use

```bash
shadow status                  # this computer's board — same state from any directory
shadow throw --task '~ab12' --by codex # atomic claim + starting packet
shadow amp --entity <id> --by codex    # resume a checkpoint already owned by this seat
shadow return --row '~ab12' --by codex # proven finish, blocked wake, or handback
shadow priority --value 1      # change global project rank without editing its plan
shadow accept --repo . --row '~ab12' --by codex # prove, flip, publish, close claim
```

Also `init --here`, `lint`, `browse`, `host run`, `doctor`.

## Three ideas

**One board per computer, entity plans underneath projects.** The hierarchy is computer →
project → entity → milestone → checkpoint. `~/.shadow/board.json` owns global project priority,
claims, owners, entity pointers, and one resume checkpoint per entity. Each entity's `PLAN.md`
owns its milestone and checkpoint text, proof, and evidence. The board points; it never copies.

**The goal is a pointer.** No prompt carries ten projects in 4,000 characters, so `amp` doesn't
try. The computer board owns coordination; the entity plan owns checkpoint detail and proof.
The block owns neither, and `amp` emits executable work only for the named owning seat.

**No proof, no completed.** Every task carries a `proof:` that can refuse bad work — `cmd`, `read`,
or `gate <owner>`. `accept` is the only flip path for `cmd` proof; a person re-observes `read` and
`gate` proof before recording their manual flip.

## What it won't do

No database, daemon, scheduler, or transcript memory. The root board mutates only pointer and
claim metadata; project rows still change only in their owning `PLAN.md`. Native hosts keep auth
and model choice. `host run` executes claimed work and never launches an unclaimed task.
`accept` reruns only `cmd` proofs; `read` and `gate` remain judgments a person re-observes. A
receipt is evidence, not acceptance.

## Develop

`scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py'` — the method is one page,
[`AGENT.md`](AGENT.md), enforced by [the grammar](docs/reference/grammar.md).

[Quick start](docs/guide/quickstart.md) · [Commands](docs/reference/commands.md) ·
[Amp](docs/reference/amp.md) · [Privacy](docs/reference/privacy.md) · MIT.

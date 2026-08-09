<p align="center"><img src="assets/shadow-banner.svg" alt="Shadow reads a plan, acts on one bounded task, verifies proof, and leaves a resume point." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** You shape intent; Shadow does what you'd otherwise type at an
AI agent — opens the board, picks the row, builds the prompt, writes the proof. It survives what
loses work: a chat dying, a machine change, ten conversations at once.

## Install

```bash
git clone https://github.com/firstbitelabsllc/shadow.git && cd shadow
bash install.sh && shadow doctor
```

Git, Bash, Python 3.10+, one native host (Claude Code, Codex, or Cursor). No Node, no npm — the
clone *is* the install, `git pull` is the update. Then paste the standing goal from
[host integration](docs/reference/host-integration.md) into your hosts' instruction files.

The Claude mount also activates the Brief contract's Stop hook: the mounted
directory carries `.claude-plugin/plugin.json`, so Claude Code loads it as the
plugin `shadow@skills-dir` and reads `hooks/hooks.json` from it. Run
`/reload-plugins` or restart to pick it up in a live session.

## Use

```bash
shadow status                  # the board — same list from any directory, any machine
shadow amp                     # one goal block that POINTS at the plan, ≤4k chars
shadow throw --task '~ab12'    # claim a row before handing it to another seat
shadow accept --row '~ab12'    # rerun the proof in a clean checkout, then flip the row
```

Also `init --here`, `lint`, `browse`, `host run`, `doctor`.

## Three ideas

**One plan, in git.** Each project's truth is its own `PLAN.md`, so Shadow opens the same board
anywhere — an empty directory falls back to your portfolio instead of pretending nothing exists.
Chat is a projection; the plan is the memory.

**The goal is a pointer.** No prompt carries ten projects in 4,000 characters, so `amp` doesn't
try: authority ref, one resume row, its proof, and the rule that *when block and plan disagree,
the plan wins*.

**No proof, no completed.** Every task carries a `proof:` that can refuse bad work — `cmd`, `read`,
or `gate <owner>`. `accept` reruns it in a clean checkout and is the only path that flips a task.

## What it won't do

No database, daemon, scheduler, or transcript memory — a surface that could mutate a row outside
`PLAN.md` is banned. Native hosts keep auth and model choice. `host run` runs one sealed task and
never launches work itself. `accept` reruns only `cmd` proofs; `read` and `gate` are judgments a
person re-observes. A receipt is evidence, not acceptance.

## Develop

`scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py'` — the method is one page,
[`AGENT.md`](AGENT.md), enforced by [the grammar](docs/reference/grammar.md).

[Quick start](docs/guide/quickstart.md) · [Commands](docs/reference/commands.md) ·
[Amp](docs/reference/amp.md) · [Privacy](docs/reference/privacy.md) · MIT.

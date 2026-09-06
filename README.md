# Shadow

**Your AI coding work shouldn't die with the chat tab.**

I run Claude Code, Codex, and Cursor on the same projects, often at the same
time. Every new session started with the same ritual: paste the last summary,
explain what I actually wanted, guess which agent was already halfway through
something, and take "done" on faith because nobody re-ran the test.

Shadow is the fix I built for myself. It keeps a plan on disk, makes agents
claim a task before they touch it, and refuses to mark anything finished until
the check you named actually passes. It's a CLI. Git, Bash, Python. No daemon,
no cloud, no account.

[Install](#install) · [Your first task](https://github.com/firstbitelabsllc/shadow/blob/shadow-1.3.0/docs/guide/quickstart.md) ·
[Docs](https://firstbitelabsllc.github.io/shadow/) ·
[Issues](https://github.com/firstbitelabsllc/shadow/issues)

<p align="center">
  <a href="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml"><img src="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/daemon-none-success" alt="No daemon" />
</p>

<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop: claim a checkpoint, do the work, prove it, accept it, move to the next one." width="100%" /></p>

## What it actually does

Three things, and I tried hard to keep it to three.

1. **Plans on disk.** A `PLAN.md` with an outcome and 2-7 tasks per
   milestone. Each task names the check that proves it. The next session
   reads the plan, not your chat history. There is one board per computer;
   the **board** is the small local file tracking who owns what. Each
   project gets one authoritative `PLAN.md` per independently tracked piece
   of work: a release, a docs push, not a whole repo. Related **plans**
   form a project map.
2. **Claims.** Every worker, human or agent, picks a stable seat name and
   sticks with it (**seats** are the names that survive across
   conversations). Before touching a task it runs `shadow throw` to
   **claim** the row. A second agent can't quietly start the same thing.
3. **Proof before done.** Each task names its **proof**: a command, a thing
   you observed by hand, or a human decision. `shadow accept` re-runs a
   command proof against the committed source. Fail, and the row stays
   open. Pass, and **accept** writes a receipt line with the command and the
   commit hash. That receipt is durable; it's just text in Git.

The loop is **claim → work → prove → accept → next**.

## Install

You need Git, Bash, and Python 3.10+. Your coding host (Claude Code, Codex,
Cursor) runs the model; Shadow never talks to a provider.

```bash
git clone --branch shadow-1.3.0 --depth 1 https://github.com/firstbitelabsllc/shadow.git
cd shadow
bash install.sh
export PATH="$HOME/.local/bin:$PATH"
shadow doctor
```

`install.sh` symlinks the CLI and host skills back to this clone, so leave
the clone where it is. To upgrade, check out a newer
[release tag](https://github.com/firstbitelabsllc/shadow/releases) and rerun
it. Host setup and troubleshooting are in [installation](docs/guide/installation.md).
The docs on `main` can be ahead of the pinned release; read the ones in your
checkout.

## First task

Inside a Git repo you're working on:

```bash
shadow init --here
shadow status --by leo
```

`init` writes a starter plan and prints its path. Open it, write the outcome,
and turn the placeholder tasks into real ones using the repo's real checks.
Keep the generated `~xxxx` row IDs; the board already points at one of them.
`--by leo` is your seat name. Use the same one every session or the board
thinks you're two people.

`status` prints the exact claim command for the next reachable task. Run it,
do the work, commit, then:

```bash
shadow accept --repo . --row '~a1b2' --by leo
```

If the task's check is a unit test and that test fails, accept refuses and
tells you why. If it passes, the row flips and the receipt lands in the
plan.

Here's the whole loop from a real session, trimmed:

<p align="center"><img src="assets/shadow-loop.svg" alt="Animated real session: shadow throw claims a checkpoint and prints its proof; after the work is committed, shadow accept reruns the proof, passes, and flips the row with its PROOF and SOURCE receipt lines." width="100%" /></p>

```console
$ shadow throw --repo . --task '~a1b2' --by demo
[throw] ~a1b2 claimed by demo on this computer
/goal readme-demo — first proof
AUTHORITY: PLAN.md @ this computer … — section "### M1 — first proof"
RESUME: [pending] hello.txt exists with today's greeting ~a1b2
PROOF: cmd test -f hello.txt
RAILS: … no proof, no completed; run `shadow lint` before mode flips …

# … you, Claude Code, or Codex does the work, then commits …

$ shadow accept --repo . --row '~a1b2' --by demo
accepted ~a1b2: proof and final lint passed at local.shadow.invalid/1e89… HEAD a22fe1d…; local row flipped with its PROOF and SOURCE lines
```

And what the plan looks like afterward, which is what the next session reads:

```text
- 2026-09-06T02:09:21Z ~a1b2 PROOF test -f hello.txt -> pass (accept)
- 2026-09-06T02:09:21Z ~a1b2 SOURCE local.shadow.invalid/1e89… HEAD a22fe1d… -> proof and final lint (accept)
```

The [first-task guide](https://github.com/firstbitelabsllc/shadow/blob/shadow-1.3.0/docs/guide/quickstart.md)
goes through claiming, recording things you observed by hand, and handing
blocked work back. `shadow status --in-flight` shows who owns what right now.
`shadow browse` opens the board in a local browser tab.

## Why not just…

| I tried | What went wrong |
|---|---|
| Chat history | Gone when the tab closes. No owner. No proof anything ran. |
| `TODO.md` | Two agents edit it at once and it lies. Nothing stops both from picking the same line. |
| An issue tracker | Built for humans at meeting cadence, not agents claiming work every few minutes. Lives in someone else's cloud. |
| An agent framework | A daemon, a second database, a prompt router. Now my work lives in their format. |

## Things I deliberately didn't build

- **No daemon.** Nothing runs between commands.
- **No cloud.** Plans stay on your disk. With a tracked upstream, claims also
  use `refs/heads/shadow/claims/v1/` on that remote so two machines don't
  collide; a repo with no upstream stays local-only.
- **No prompt reading.** Shadow never sees your conversations or provider
  traffic. Receipts are names, statuses, and hashes.
- **No sandbox.** A command proof is a trusted local program. If you name a
  weak check, a weak check passes. Shadow reruns what you chose; it doesn't
  judge it.
- **Telemetry off** by default, local-only if you turn it on, no paths or
  commands recorded. See [privacy](docs/reference/privacy.md).

Config and the optional extension slots are in
[config](docs/reference/config.md), kept out of the first-run path on purpose.

## Handing a task to a host

Once a task is claimed you can push it through a host as a sealed run: a
frozen task file, exact allowed paths, and a receipt back. Works with Claude
Code, Codex, Cursor, Grok, and Z.AI.

```bash
shadow host run --host codex --work-class coding --delegation direct \
  --repo "$PWD" --task-file /tmp/task.md --task-id focused-fix \
  --allowed-path src/fix.py --out .shadow/evidence/focused-fix.json
```

Four work classes (`planning`, `coding`, `review`, `lightweight`). If a host
can't do what you asked, it fails closed rather than silently switching
providers. The receipt is evidence, not acceptance: read the diff, rerun the
proof. Details in the [execution policy](docs/reference/execution-policy.md).
When two workers claim overlapping work, [Huddle](docs/reference/commands.md#huddle-coordination)
pauses both until they split the scope or one hands the work back.

A proposal-enabled machine-local row can ask a sealed Codex run for a
no-change completion proposal (`--authority-proposal`, then
`shadow accept --proposal`). Commit the reviewed source first. Shadow binds
the proposal to the row and reruns the proof in an isolated temporary `HOME`.
Git-backed plans, other hosts, and manual `read`/`gate` proofs don't support
this; the [command reference](docs/reference/commands.md) has the rest.

## Feedback

MIT. Fork it, bend it to your workflow. If a fresh session loses the thread
or accept passes something it shouldn't have, open an
[issue](https://github.com/firstbitelabsllc/shadow/issues) with a small
example. "I installed it and got confused at step 2" is a useful report.

Small pull requests (a doc fix, a repro test) are welcome; open an issue
first for anything bigger. [Contributing](CONTRIBUTING.md) has the tests and
the reasoning. Security reports go through [SECURITY.md](SECURITY.md).

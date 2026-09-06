<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop — board, claim, work, prove, accept — orbiting one glowing checkpoint labeled resume here." width="100%" /></p>

<h1 align="center">Shadow</h1>

<p align="center"><strong>AI agents forget. Shadow is the memory, the referee, and the proof.</strong></p>

<p align="center">
  <a href="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml"><img src="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/daemon-none-success" alt="No daemon" />
</p>

Every AI coding session starts from zero. The chat dies and the plan dies with
it. The agent says "done" and nothing checked it. Two agents in one repo edit
the same files blind. Shadow fixes all three with one boring, durable idea:

**a plan that outlives the session, a claim that only one agent can hold, and
a proof that must actually pass before anything is called done.**

It runs under Claude Code, Codex, Cursor, Grok, and Z.AI. The whole stack is
Git, Bash, and Python. No daemon, no cloud service, no transcript store, no
prompt inspection.

## The loop

Every seat — human or agent — runs the same five moves:

**claim → work → prove → accept → next**

| word | meaning |
|---|---|
| **board** | one small ledger per computer: ownership, priority, resume |
| **plans** | each entity's `PLAN.md`: checkpoints, each with one typed `cmd`, `read`, or `gate` proof |
| **claim** | a seat takes a checkpoint atomically; exactly one winner |
| **proof** | done means the checkpoint's named check passed |
| **accept** | the only flip to completed: rerun the proof clean, record it |

Kill any chat mid-sentence. The next session reads the same plan and resumes
the claimed checkpoint: what passed, what didn't, and the exact command to
continue.

## Sixty seconds, real commands

```console
$ shadow init --here
created local PLAN.md: ~/.shadow/plans/readme-demo/PLAN.md

$ $EDITOR ~/.shadow/plans/readme-demo/PLAN.md   # add one task with a proof
$ shadow lint --repo . ~/.shadow/plans/readme-demo/PLAN.md
~/.shadow/plans/readme-demo/PLAN.md: clean

$ shadow status --by demo        # prints the exact throw command for the next reachable row
$ shadow throw --repo . --task '~a1b2' --by demo
[throw] ~a1b2 claimed by demo on this computer
RESUME: [pending] hello.txt exists with today's greeting ~a1b2
PROOF: cmd test -f hello.txt
RAILS: … no proof, no completed; run `shadow lint` before mode flips …

# … you, Claude Code, or Codex does the work, then commits …

$ shadow accept --entity <id> --repo . --row '~a1b2' --by demo
accepted ~a1b2: proof and final lint passed at local.shadow.invalid/1e89… HEAD a22fe1d…; local row flipped with its PROOF and SOURCE lines
```

The plan now carries the receipt:

```text
- 2026-09-06T02:09:21Z ~a1b2 PROOF test -f hello.txt -> pass (accept)
- 2026-09-06T02:09:21Z ~a1b2 SOURCE local.shadow.invalid/1e89… HEAD a22fe1d… -> proof and final lint (accept)
```

"Done" has a hash and a HEAD. Anything less stays pending. This transcript is
from a real session, trimmed to fit; every command above is copy-pasteable.

## Install

```bash
git clone --branch shadow-1.3.0 --depth 1 https://github.com/firstbitelabsllc/shadow.git
cd shadow && bash install.sh && shadow doctor
```

Git, Bash, Python 3.10+, and one supported host. No Node, no package manager.
The clone **is** the install; upgrading means checking out a newer `shadow-v*`
tag and rerunning `install.sh`. Missing `shadow`? Add `~/.local/bin` to PATH.
The [full install guide](https://firstbitelabsllc.github.io/shadow/guide/installation) covers
the edge cases.

## Why not just…

| Approach | What breaks |
|---|---|
| Chat history | dies with the session; no ownership; no proof anything ran |
| `TODO.md` | no claims, no atomicity; two agents race and the file lies |
| Issue tracker | built for humans at meeting cadence, not agents at claim cadence; lives in someone's cloud |
| Agent frameworks | a daemon, a second database, and a prompt router; your work lives in their format |

Shadow's plans are Markdown you can read in any editor. Claims are atomic on a
local board. Proof is a command that can fail. State lives in `~/.shadow` and
your own Git, and deleting both removes every trace.

## Sealed delegation to real hosts

Work doesn't have to be yours. Shadow hands a claimed slice to a native host
as a sealed run: frozen task file, exact allowed paths, and a scoped receipt.

```bash
shadow host run --host codex --work-class coding --delegation direct \
  --repo "$PWD" --task-file /tmp/task.md --task-id focused-fix \
  --allowed-path src/fix.py --out .shadow/evidence/focused-fix.json
```

Four semantic work classes (`planning`, `coding`, `review`, `lightweight`)
plus an explicit execution shape (`direct` or `required`). Each host maps to a
small checked-in model policy — Claude Code, Codex, Cursor, Grok, and Z.AI
today. Unsupported child capability fails closed; a quota failure never
silently falls back to another provider. A receipt is evidence, never
acceptance: review the diff and reproduce the proof yourself.

Requested model selection and observed model execution are distinct. The
owner-local evaluation gauntlet publishes exact falsifiers, hashes, and
remaining wakes in the
[native execution policy](https://firstbitelabsllc.github.io/shadow/reference/execution-policy)
and its [dated 48-row evidence record](https://firstbitelabsllc.github.io/shadow/reference/execution-policy-evidence-2026-08-26).

## When agents overlap, nobody referees chats

Exact duplicate claims are rejected atomically. Other overlap holds the later
claim while the current owner continues. When agents must negotiate, Huddle
gives them structured rounds — bid to own, split disjoint, review, yield,
stand down — each with a bounded reply window and an explicit settle. Ownership
changes only through an owner-authorized atomic handoff, never through a
message or a timeout. See the
[Huddle reference](https://firstbitelabsllc.github.io/shadow/reference/commands#huddle-coordination).

## What Shadow is not

- **No daemon.** Nothing runs between commands. No background service, no watcher.
- **No cloud.** No remote task authority, no credential relay, no account binding.
- **No prompt inspection.** Shadow never reads your conversations or your provider traffic.
- **No transcript store.** Receipts carry names, statuses, hashes — never prose or payloads.
- **Telemetry off by default**, local-only when opted in, and even then it
  records no paths, commands, or text. ([Privacy](https://firstbitelabsllc.github.io/shadow/reference/privacy))

## Customize (deliberately little)

- **Extensions** (`shadow slots`): `memory`, `taste`. Every one may be empty;
  none ever gates a cycle. Opt out per machine: `SHADOW_SLOT_MEMORY=off`.
- **`shadow.yaml`**: one optional file, two keys (`version`,
  `adversarial-lenses`). That is the whole config surface, by law.
- **Standing goal**: `shadow goal --install` owns one marked block in your
  agent file; your methods live beside it, untouched. Cursor hosts prove it
  with the repo-scoped verifier
  ([how](https://firstbitelabsllc.github.io/shadow/reference/host-integration)).
- **Environment**: `SHADOW_ROOT`, host binary overrides, slot bindings — the
  [full table](https://firstbitelabsllc.github.io/shadow/reference/config).

Large projects scale by adding entity plans under one `Project:` slug; the
board membership is the map and each plan keeps its own truth
([project maps](https://firstbitelabsllc.github.io/shadow/reference/project-maps)).
When your branch tracks a remote, `shadow throw` takes one coordination lock
on that same remote so forks tracking one upstream can share a board without a
server.

## Docs

Every verb, the plan grammar, extensions, and privacy boundaries:
**[firstbitelabsllc.github.io/shadow](https://firstbitelabsllc.github.io/shadow/)**

Start here: [quick start](https://firstbitelabsllc.github.io/shadow/guide/quickstart) ·
[commands](https://firstbitelabsllc.github.io/shadow/reference/commands) ·
[plan grammar](https://firstbitelabsllc.github.io/shadow/reference/grammar) ·
[other-computer handoff](https://firstbitelabsllc.github.io/shadow/guide/other-computer-handoff)

Developing on Shadow starts at [`AGENT.md`](AGENT.md) and
[`CONTRIBUTING.md`](CONTRIBUTING.md): issues, bug reports, critiques, and
field reports are welcome; external pull requests are closed while the
doctrine settles.

## License

[MIT](LICENSE). Built by [First Bite Labs](https://github.com/firstbitelabsllc).

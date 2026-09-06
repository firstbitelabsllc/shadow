# Shadow

**All your AI coding sessions are one chat. Anyone can pick it up.**

This is what a new session sees, whichever tool it is:

```console
$ shadow status --by codex
This computer — root board revision 7484

Portfolio: 41 entities | Seat: codex | Focused: 1 | Owned: 0

resplit ios — TRIP LINK — COLLABORATION PRODUCT
  Entity plan: resplit-ios/plans/group-link/PLAN.md
  Mode: ship | Priority: 1
  Resume: [pending] finish the owner experience: share, preview, revoke, retry ~g202
  Claim: shadow throw --entity a795ba22… --task '~g202' --by codex
  Proof: focused tests across off/on/pending/stale/offline/revoke states
```

No recap. No "where were we." The plan is a file in Git, the board says who
owns what on this computer, and any **seat** (a stable name for a worker,
human or agent) can claim the next row and continue. That's the product.

[Install](#install) · [First task](https://github.com/firstbitelabsllc/shadow/blob/shadow-1.3.0/docs/guide/quickstart.md) ·
[Docs](https://firstbitelabsllc.github.io/shadow/) ·
[Issues](https://github.com/firstbitelabsllc/shadow/issues)

<p align="center">
  <a href="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml"><img src="https://github.com/firstbitelabsllc/shadow/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/daemon-none-success" alt="No daemon" />
</p>

<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop: claim, work, prove, accept, next." width="100%" /></p>

## Four words

- **plans**: a `PLAN.md` per thing you're shipping. Outcome, 2-7 tasks per
  milestone, each with the check that proves it. There is one authoritative `PLAN.md` per independently
  steerable entity; related plans form a project map.
- **board**: one board per computer, a local file. Who owns what, where to
  resume.
- **seats**: the roster. Same name every session, so ownership survives the tab.
- **claim** / **proof** / **accept**: take a row, do it, rerun its check
  against committed source. Pass and the plan gets a receipt with the commit
  hash. Fail and it stays open. The receipt is durable text in Git.

The loop is **claim → work → prove → accept → next**.

## Install

Git, Bash, Python 3.10+. Your coding host runs the model.

```bash
git clone --branch shadow-1.3.0 --depth 1 https://github.com/firstbitelabsllc/shadow.git
cd shadow && bash install.sh
export PATH="$HOME/.local/bin:$PATH"
shadow doctor
```

`install.sh` symlinks into this clone; leave it in place. Upgrade by checking
out a newer [release tag](https://github.com/firstbitelabsllc/shadow/releases).
Host setup: [installation](docs/guide/installation.md).

## First task

Your agent runs, inside a repo:

```bash
shadow init --here          # starter PLAN.md
shadow status --by claude   # prints the exact claim command
```

Fill in the outcome and real tasks; keep the generated `~xxxx` IDs. Claim,
work, commit, then:

```bash
shadow accept --repo . --row '~a1b2' --by claude
```

Real session, trimmed:

```console
$ shadow throw --repo . --task '~a1b2' --by demo
[throw] ~a1b2 claimed by demo on this computer
RESUME: [pending] hello.txt exists with today's greeting ~a1b2
PROOF: cmd test -f hello.txt

# … agent does the work, commits …

$ shadow accept --repo . --row '~a1b2' --by demo
accepted ~a1b2: proof and final lint passed at … HEAD a22fe1d…
```

```text
- 2026-09-06T02:09:21Z ~a1b2 PROOF test -f hello.txt -> pass (accept)
- 2026-09-06T02:09:21Z ~a1b2 SOURCE … HEAD a22fe1d… -> proof and final lint (accept)
```

<p align="center"><img src="assets/shadow-loop.svg" alt="Animated real session: throw claims and prints the proof; accept reruns it and flips the row." width="100%" /></p>

`shadow status --in-flight` shows who owns what. `shadow browse` opens the
board locally. Development source on `main` also takes `--entity`; see the
[command reference](docs/reference/commands.md).

## Why not…

| | |
|---|---|
| Chat history | gone with the tab, no owner, no proof |
| `TODO.md` | two agents edit it at once and it lies |
| Issue tracker | meeting cadence, someone else's cloud |
| Agent framework | a daemon, a database, a router; your work in their format |

## Not built, on purpose

No daemon. No cloud: plans stay on disk, and with a tracked upstream claims
also use `refs/heads/shadow/claims/v1/` on that remote so two machines don't
collide. No prompt reading. No sandbox: a proof is a trusted
local command, and a weak check still passes. Telemetry off; local-only if
on, no paths or text. [Privacy](docs/reference/privacy.md) ·
[config](docs/reference/config.md).

## Sealed host runs

A claimed task can go to Claude Code, Codex, Cursor, Grok, or Z.AI as a
sealed pass: frozen task file, exact allowed paths, receipt back.

```bash
shadow host run --host codex --work-class coding --delegation direct \
  --repo "$PWD" --task-file /tmp/task.md --task-id focused-fix \
  --allowed-path src/fix.py --out .shadow/evidence/focused-fix.json
```

Unsupported capability fails closed. A receipt is evidence, not acceptance.
[Execution policy](docs/reference/execution-policy.md) ·
[Huddle](docs/reference/commands.md#huddle-coordination) for overlapping claims.

<details>
<summary>Proposal-only acceptance</summary>

A proposal-enabled machine-local row can run a sealed Codex no-change pass
with `--authority-proposal`, then `shadow accept --proposal`. Shadow binds
it to row, owner, claim, plan root, and `HEAD`, and reruns the proof in an
isolated temporary `HOME`. Git-backed plans, other hosts, and `read`/`gate`
proofs don't support it. [Command reference](docs/reference/commands.md).

</details>

## Feedback

MIT. Confused at a step? Accept passed something it shouldn't? Open an
[issue](https://github.com/firstbitelabsllc/shadow/issues) with a small
example. Small PRs welcome; [Contributing](CONTRIBUTING.md), [Security](SECURITY.md).

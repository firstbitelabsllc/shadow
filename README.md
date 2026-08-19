<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop — board, claim, work, prove, accept — orbiting one glowing checkpoint labeled resume here." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** Say what you want in any wired AI coding
host — Claude Code, Codex, Cursor, Grok — and Shadow keeps the work
durable: one board per computer, one `PLAN.md` per project, a proof receipt
on every finished step. Kill any chat; the next session resumes where it stopped.

Six words carry the system:

| word | meaning |
|---|---|
| **board** | one small ledger per computer: ownership, priority, resume |
| **plans** | each repo's `PLAN.md`: checkpoints, each with its proving test |
| **seats** | the AI workers, each under one stable name |
| **claim** | a seat takes a checkpoint atomically; exactly one winner |
| **proof** | done means the checkpoint's named check passed |
| **accept** | the only flip to completed: rerun the proof clean, record it |

The loop every seat runs: **claim → work → prove → accept → next**.

## Install

```bash
git clone --branch shadow-v1.2.0 --depth 1 https://github.com/firstbitelabsllc/shadow.git
cd shadow && bash install.sh && shadow doctor
```

Git, Bash, Python 3.10+, and a supported host. No Node, no daemon, no
transcript store. The clone is the install; to upgrade, check out the
newer `shadow-v*` tag and rerun `install.sh`. Missing `shadow`? Add
`~/.local/bin` to PATH.

## First run

From any Git project, replacing only the seat name:

```bash
PLAN=$(shadow init --here | awk -F': ' '{print $2}')  # never overwrites a plan
$EDITOR "$PLAN"                    # fill the Brief; one task with its proof
shadow status --by your-seat      # prints the exact throw command — run it
# do the work, then close out:
shadow accept --repo . --row '~a1b2' --by your-seat   # cmd proofs flip here
# read/gate proofs instead: record the observation in the plan, then shadow return
```

Quote row ids (`'~a1b2'`) and use the id status printed. `shadow status
--in-flight` shows every seat's live work; `shadow browse` renders the board.

## Customize

All configuration is deliberately small, and stress-tested that way:

- **Extensions** — optional capabilities (`shadow slots`): memory, taste.
  Every one may be empty; none ever gates a cycle. Rebind or opt out per
  machine with `SHADOW_SLOT_<NAME>=<abs path>|off` — don't want routed
  recall? `SHADOW_SLOT_MEMORY=off` and everything runs.
- **`shadow.yaml`** — one optional repo-root file with two keys
  (`version`, `adversarial-lenses`). That's the whole config file, by law:
  a dial may exist only where a wrong value costs quality, never truth.
- **Environment** — `SHADOW_ROOT`, host binary overrides, the slot bindings —
  table: [Config](https://firstbitelabsllc.github.io/shadow/reference/config).
- **Standing goal** — `shadow goal --install` owns one marked block in your
  agent file; your methods live beside it, untouched. Cursor: paste
  `shadow goal` output into User Rules ([how](https://firstbitelabsllc.github.io/shadow/reference/host-integration)).

When your branch tracks a configured `origin`, `shadow throw` also takes one
Git coordination lock under `refs/heads/shadow/claims/v1/<entity>/<row>`: it
carries no task or proof text and never becomes authority. With no upstream
the same flow stays local-only.
Shadow refuses unclaimed execution, missing proof, and ambiguous authority.

## Docs

The full contract — every verb, plan grammar, extensions, privacy — lives at
**[the docs site](https://firstbitelabsllc.github.io/shadow/)**; developing starts at
[`AGENT.md`](AGENT.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) — external
PRs are closed.

[MIT License](LICENSE).

<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop — board, claim, work, prove, accept — orbiting one glowing checkpoint labeled resume here." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** Say what you want in any wired AI coding
host — Claude Code, Codex, Cursor, Grok — and Shadow keeps the work
durable: one board per computer, one authoritative `PLAN.md` per independently
steerable entity, related entities grouped as one project map, and a proof
receipt on every finished step. Kill any chat; the next session resumes where
it stopped.

Six words carry the system:

| word | meaning |
|---|---|
| **board** | one small ledger per computer: ownership, priority, resume |
| **plans** | each entity's `PLAN.md`: checkpoints, each with one typed `cmd`, `read`, or `gate` proof |
| **seats** | the AI workers, each under one stable name |
| **claim** | a seat takes a checkpoint atomically; exactly one winner |
| **proof** | done means the checkpoint's named check passed |
| **accept** | the only flip to completed: rerun the proof clean, record it |

The loop every seat runs: **claim → work → prove → accept → next**.

## Install

```bash
git clone --branch shadow-v1.3.0 --depth 1 https://github.com/firstbitelabsllc/shadow.git
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
$EDITOR "$PLAN"                    # fill the Brief; keep 2-7 tasks per milestone
shadow status --by your-seat      # prints the exact throw command — run it
# do the work, then close out:
shadow accept --repo . --row '~a1b2' --by your-seat   # Git-backed plan
shadow accept --entity ID --repo . --row '~a1b2' --by your-seat  # machine-local plan
shadow host run --host codex --work-class coding --delegation direct \
  --authority-proposal --repo . --task-file /absolute/proposal-task.txt \
  --task-id propose-a1b2 --out .shadow/evidence/attempt.json
shadow accept --entity ID --repo . --row '~a1b2' --by your-seat \
  --proposal .shadow/evidence/attempt.json  # proposal-enabled machine-local plan
# read/gate proofs instead: record the observation in the plan, then shadow return
```

Quote row ids (`'~a1b2'`) and use the id status printed. `shadow status
--in-flight` shows every seat's live work; `shadow browse` renders the board.

A proposal-enabled row keeps its proof command, result marker, and minimum
execution floor in the canonical machine-local plan. Use two passes: first
change, review, and commit the source files; then run a sealed Codex no-change
attempt from a clean checkout that proposes completion against that committed
`HEAD` through explicit `--authority-proposal` mode. That mode accepts no
source write paths, refuses binary overrides before launch, and rejects any
source `HEAD` or Git control-state drift. Shadow binds the proposal to the
exact entity, row, owner, claim, plan root, and source `HEAD`, reruns the
canonical proof with an isolated temporary `HOME`, and performs the authority
write itself. Proposal proofs must be deterministic and cannot depend on
credentials stored in the operator's home directory. Git-backed plans, other
hosts, and `read` or `gate` proofs do not support proposals.

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
  agent file; your methods live beside it, untouched. Cursor: keep that block
  in a source-controlled repository-root `AGENTS.md` or `CLAUDE.md`, then prove
  it with the repo-scoped verifier ([how](https://firstbitelabsllc.github.io/shadow/reference/host-integration)).

When your branch tracks a configured `origin`, `shadow throw` also takes one
Git coordination lock under `refs/heads/shadow/claims/v1/<entity>/<row>`: it
carries no task or proof text and never becomes authority. With no upstream
the same flow stays local-only.
Shadow refuses unclaimed execution, missing proof, and ambiguous authority.
Large projects scale by adding entity plans under the same `Project:` slug;
the board membership is the map, while each plan keeps its own truth and local
dependencies. See **[Project maps](https://firstbitelabsllc.github.io/shadow/reference/project-maps)**.

## Route hard work deliberately

Sealed native-host runs require one of four semantic work classes—`planning`,
`coding`, `review`, or `lightweight`—plus an explicit execution shape:
`--delegation direct|required`. Shadow maps the chosen host and class to a
small checked-in native model policy—Fable/Opus/Sonnet for Claude Code,
Sol/Terra/Luna for Codex, Fable/Opus/Cursor Grok/Auto for Cursor, and Grok
4.6/4.5 for Grok. Required delegation enables the host's verified native child
door; unsupported child capability fails closed. Shadow does not inspect prompt
text, select accounts, or silently fall back after a quota failure.

Requested selection is not observed execution. The owner-local evaluation
gauntlet runs 12 real jobs through all four headless CLIs and requires exact
model and usage evidence, scoped edits, deterministic verification, native
child lineage where required, plus Langfuse write and exact readback. See
**[Native execution policy](https://firstbitelabsllc.github.io/shadow/reference/execution-policy)**.
The [dated 48-row evidence and cold takeover](https://firstbitelabsllc.github.io/shadow/reference/execution-policy-evidence-2026-08-26)
publishes the exact falsifiers, corrections, hashes, and remaining wakes.

## Docs

The full contract — every verb, plan grammar, extensions, privacy — lives at
**[the docs site](https://firstbitelabsllc.github.io/shadow/)**; developing starts at
[`AGENT.md`](AGENT.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) — external
PRs are closed.

[MIT License](LICENSE).

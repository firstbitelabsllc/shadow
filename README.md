<p align="center"><img src="assets/shadow-banner.svg" alt="The Shadow loop — board, claim, work, prove, accept — orbiting one glowing checkpoint labeled resume here." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** Say what you want in any wired AI coding
host — Claude Code, Codex, Cursor — and Shadow keeps the work durable: one
board per computer saying who is doing what, one `PLAN.md` per project holding
the work itself, and a proof receipt on every finished step. Kill any chat at
any time; the next session resumes exactly where the last one stopped.

Six words carry the whole system:

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
git clone --branch shadow-v1.0.1 --depth 1 https://github.com/firstbitelabsllc/shadow.git
cd shadow && bash install.sh && shadow doctor
```

Git, Bash, Python 3.10+, and a supported host. No Node, no daemon, no
database, no transcript store. The clone is the install; to upgrade, check
out the newer `shadow-v*` tag and rerun `install.sh`. If `shadow` is not
found afterward, add `~/.local/bin` to your PATH.

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

- **Buckets** — optional capability slots (`shadow buckets`): superpowers,
  taste, future, explain. Every one may be empty; none ever gates a cycle.
  Rebind or opt out per machine with `SHADOW_BUCKET_<NAME>=<abs path>|off` —
  don't want superpowers? `SHADOW_BUCKET_SUPERPOWERS=off` and everything runs.
- **`shadow.yaml`** — one optional repo-root file with exactly two keys
  (`version`, `adversarial-lenses`). That's the whole config file, by law:
  a dial may exist only where a wrong value costs quality, never truth.
- **Environment** — `SHADOW_ROOT`, `SHADOW_PORTFOLIO_ROOT`, host binary
  overrides, and the bucket bindings above; the full table is in
  [Config](https://firstbitelabsllc.github.io/shadow/reference/config).

## What it will and will not do

It coordinates every reachable lane, keeps one writer per claim, and leaves
proof plus a successor; it refuses unclaimed execution, missing proof, and
ambiguous authority. Hosts keep their own auth, model, and billing.

When your branch tracks a configured `origin`, `shadow throw` also takes one
Git coordination lock under `refs/heads/shadow/claims/v1/<entity>/<row>`: it
carries no task or proof text, never becomes authority, and leaves the tracked
branch untouched. With no such upstream the same flow stays local-only.

## Docs

The full contract lives at **[the docs site](https://firstbitelabsllc.github.io/shadow/)** —
install detail, the claim/proof loop, every verb and flag, plan grammar,
buckets, privacy. Developing Shadow itself starts at [`AGENT.md`](AGENT.md).

MIT License.

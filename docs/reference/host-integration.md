# Host integration — Shadow out of the box

Shadow should work the moment a host opens, in any directory, with zero
per-session setup: same durable board, same standing goal, proxy stance on.
This page is the complete cold-start wiring for Claude Code, Codex, and Grok.
Cursor's skill mount and sealed host-run are supported, but file-backed cold
directive activation is explicitly unsupported until Cursor exposes a reviewed
user-rule surface; Shadow does not invent `~/.cursor/rules`.

## 1. Install once

```bash
git clone --branch shadow-v1.0.1 --depth 1 \
  https://github.com/firstbitelabsllc/shadow.git && cd shadow
bash install.sh
shadow doctor
```

Git, Bash, Python 3.10+ — no Node, no npm. The immutable release clone is the
install; update by checking out the next GitHub Latest `shadow-v*` tag and
rerunning `install.sh`. If a host mount already points somewhere else (an old
global package path, say), `install.sh` repoints it.

Optional: `export SHADOW_PORTFOLIO_ROOT="$HOME/Development"` (that value is
the default) — the root `shadow status` falls back to when the current
directory has no plan, so every entry point shows the same board.

## 2. The standing goal — one installed top-level direction block

The goal for any Shadow seat is **static**. It is the same text for every
person, every host, every day; only what the durable plans point at changes.
`shadow goal --install` owns this marker-delimited block inside
`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.grok/AGENTS.md`:

```text
## Shadow — standing goal (static; the pointer moves, this text does not)

Outcome: act as the user's active local proxy; reconstruct what matters,
choose and finish valuable work, prove it, improve the method, and continue
without requiring the user to supervise the system.
Authority: this computer's private local Shadow board at `~/.shadow` owns global
project priority, entity pointers, claims, owners, and resume. Each infrastructure
entity's local `PLAN.md` under `~/.shadow/plans/` owns its milestones, checkpoints,
detail, and proof. A product repository may retain its declared release plan. Chats,
dashboards, worktree copies, provider-private plans, and native host plans are
never competing authority.
Hierarchy: computer → project → entity → milestone → checkpoint. A project may
span entities; each entity keeps its own durable plan and resume checkpoint.
Resume: establish one stable public seat name, run `shadow status --by <seat>`
from any directory, continue every claim owned by that seat, then atomically
claim the highest-value reachable checkpoint shown. `shadow amp` may project
only a checkpoint already claimed by that seat.
Stance: proxy. Never ask "which project?" Open the board, state the selected
checkpoint and why now, reconstruct intent and contradictions, challenge weak
assumptions, and make reversible operational calls. Ask only for credentials,
money, external publishing/messages, destructive action, or irrecoverable
product intent.
Capabilities: deterministically use the smallest relevant installed skill and
repository harness; record a native fallback when absent. Never let a plugin,
operator invocation, review, green suite, merge, install, or demo count as
proof by itself.
Dispatch: nothing leaves the active seat unclaimed. `shadow throw` commits the
local atomic claim before any agent, workflow, or seat starts. Fan out safe,
path-disjoint claims only for a declared need. A mid-flight reading is
not a death certificate: probe the checkpoint's proof, not a process list.
Proof: no completed checkpoint without its receipt; `shadow accept --by` is
the only cmd-proof flip path. Run focused falsifiers in feature lanes and
affected integration on trunk. Run full build, migration, story E2E,
adversarial, rollback, and stranger-install proof on the deterministic
source-testing release train—normally nightly, optionally a configured second
daily window, plus an early run when measured accepted-change pressure crosses
the checked-in Method threshold. Separate owning-plan receipts prove merged
origin/main, installed/deployed, and live dogfood; never infer those from CI.
Silent skipping fails.
Lifecycle: blocked → record one exact wake, return the claim, and continue
elsewhere. Completed/blocked orphan claim → recover it, never rework it.
Close/archive proven milestones within the Method's hot-plan budgets, preserve
provenance, retire only safe clean artifacts, mint the successor, and keep
draining every reachable checkpoint required by full acceptance.
```

A host that loads only this block cold-starts correctly: it
knows where truth lives, what to do next, that asking the person to orient it
is a defect, and that work it stops watching must be written down first.

`Dispatch` earned its place on 2026-08-09: two fan-outs were launched with no
row, and when a mid-flight reading showed no results both were declared dead.
Both were still running, and both finished with real findings. Everything the
recovery needed — what was dispatched, what it should return — existed only in
a chat that had already moved on.

## Your own methods beside the block

The managed block carries Shadow and nothing else — the same text for every
person, every host, every day. Your own top-level working methods (a release
discipline, a review doctrine, a personal style contract) live **beside** the
block in the same agent file, byte-for-byte untouched by `shadow goal
--install` and `--remove`. Add them as their own sections; the installer's
markers bound only Shadow's text. Nothing about your methods enters
`shadow.yaml` — that file stays the two-key repo dial it is.

Cursor has no reviewed user-level file for cold directives, so nothing is
written there. Paste `shadow goal` output into Cursor's User Rules yourself,
or into a repo-root `AGENTS.md`, which Cursor reads.

## 3. What "activate shadow" means in a session

1. Pick one stable public seat name and run `shadow status --by <seat>` from
   anywhere. Continue every claim owned by that seat before choosing new work.
2. Name the highest-value reachable checkpoint and why it wins now. Run the
   exact `shadow throw ... --by <seat>` command shown to claim it atomically.
3. Use the returned packet yourself or dispatch only path-disjoint claimed
   checkpoints. `shadow amp` resumes work already owned by that seat; it never
   substitutes for a claim.
4. Close each loop in the entity's `PLAN.md` — result, proof, blocked wake, and
   reachable successor — while the computer board retains global coordination.

A session that instead answers "this workspace has no plan — which project
should I attach to?" has step 1 unwired: the fallback exists precisely so
that sentence never needs saying.

## 4. Voice and remote seats

Voice sessions and remote machines follow the same contract with one extra
rule: **anything discovered out-of-band is written to the owning `PLAN.md`
before the session ends.** A "packet" assembled in a chat on another machine
does not exist for the fleet until it is a plan row with a proof or wake
predicate; git — not the transcript — carries it home.

## 5. The machine boundary

**The plan is tied to the machine.** `SHADOW_PORTFOLIO_ROOT` names *this*
machine's plan set; a different machine has its own (possibly empty) board.
Continuity between machines is **git** — each repository's origin — never a
synced chat, a served dashboard, or another machine's board impersonated.

A seat on a machine with no plans says exactly that — "no plans on this
machine; the durable plans live in their git remotes" — and works through
`git clone`/`fetch`. Pretending an empty machine has the fleet's board is
the same defect as asking "which project?": inventing state instead of
reading it.

## 6. Verify the wiring

```bash
cd "$(mktemp -d)" && shadow status --by shadow-check
# Run the exact Claim command status printed, then its exact Continue command.
shadow doctor  # command, mounts, managed Claude/Codex/Grok block, and identity green
```

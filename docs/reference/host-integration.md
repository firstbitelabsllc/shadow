# Host integration — Shadow out of the box

Shadow should work the moment a host opens, in any directory, with zero
per-session setup: same durable board, same standing goal, proxy stance on.
This page is the complete wiring for Claude Code, Codex, and Cursor.

## 1. Install once

```bash
git clone https://github.com/firstbitelabsllc/shadow.git && cd shadow
bash install.sh
shadow doctor
```

Git, Bash, Python 3.10+ — no Node, no npm. The clone is the install; update
with `git pull`. If a host mount already points somewhere else (an old global
package path, say), `install.sh` repoints it.

Optional: `export SHADOW_PORTFOLIO_ROOT="$HOME/Development"` (that value is
the default) — the root `shadow status` falls back to when the current
directory has no plan, so every entry point shows the same board.

## 2. The standing goal — paste it into each host's top-level instructions

The goal for any Shadow seat is **static**. It is the same text for every
person, every host, every day; only what the durable plans point at changes.
Add this block to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and your
Cursor user rules:

```text
## Shadow — standing goal (static; the pointer moves, this text does not)

Outcome: the durable board moves; no plan goes stale silently.
Authority: each repository's own PLAN.md at origin/main — never a chat log,
never a dashboard. Enumerate with `shadow status` (empty directories fall
back to the portfolio root, so this works from anywhere).
Resume: resume every owned in-progress row; otherwise claim the highest-value
reachable work. `shadow amp --repo <that repo>` emits the starting packet.
Drain every reachable row needed by the Outcome; fan out safe disjoint rows,
integrate their proof, and keep choosing successors.
Stance: proxy. Never ask "which project?" — open the board and name the row.
Never wait to be asked to amplify, mint successor goals, challenge findings
adversarially, codify lessons, or archive shipped milestones: those are your
moves. Blocked → park with an exact wake and continue elsewhere. A completed
row never ends the Outcome; stop only when full acceptance is proven or every
remainder is behind a hard rail, then mint the successor in the owning PLAN.md.
Dispatch: nothing leaves this chat unclaimed. `shadow throw --task '~id'`
records the row before any agent, workflow, or seat starts — your own
fan-outs included. A mid-flight reading is not a death certificate: probe the
row's proof, never a process.
Proof: no completed without its proof line; `shadow accept` is the only flip
path for cmd proofs; re-observe read/gate proofs yourself.
```

A host that loads only this block cold-starts correctly: it
knows where truth lives, what to do next, that asking the person to orient it
is a defect, and that work it stops watching must be written down first.

`Dispatch` earned its place on 2026-08-09: two fan-outs were launched with no
row, and when a mid-flight reading showed no results both were declared dead.
Both were still running, and both finished with real findings. Everything the
recovery needed — what was dispatched, what it should return — existed only in
a chat that had already moved on.

## 3. What "activate shadow" means in a session

1. `shadow status` — the board, from anywhere (portfolio fallback).
2. Name owned in-progress work and the ranked reachable set out loud; brief in
   the Outcome / changed / happening / proof / hard-rail-decision shape.
3. `shadow amp --repo <repo>` for the starting packet; execute it and dispatch
   path-disjoint claimed rows when useful.
4. Close each loop in the owning `PLAN.md` — result, proof, blocked wake, and
   reachable successor — then continue until the Outcome's acceptance boundary.

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
cd "$(mktemp -d)" && shadow status   # must show the portfolio, not emptiness
shadow amp --repo <any repo with a v4 plan>   # must emit a goal block ≤4k chars
shadow doctor                                  # mounts + identity green
```

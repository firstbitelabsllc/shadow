<p align="center"><img src="assets/shadow-banner.svg" alt="Shadow reads a plan, acts on one bounded task, verifies proof, and leaves a resume point." width="100%" /></p>

# Shadow

**Shadow is you, one step down.** You shape intent; Shadow does everything
you would otherwise have typed at an AI agent — opens the board, picks the
row, builds the prompt, runs the work through a native host, challenges the
result, writes the proof, mints the successor. You talk to Shadow; Shadow
talks to the agents.

Three properties make that trustworthy:

1. **One durable board, from anywhere.** Every project's truth is its own
   `PLAN.md` in git. Open Shadow in any CLI, any directory, any machine —
   a fresh chat, a voice session, an empty scratch dir — and `shadow status`
   shows the *same* plan list (an empty directory falls back to your
   portfolio root instead of pretending nothing exists). Chat is a
   projection; the plan is the memory.
2. **The goal is a pointer.** No goal prompt can carry a ten-project
   portfolio in 4,000 characters, so Shadow never tries: `shadow amp`
   projects a paste-ready goal block that *points* at the durable plan —
   authority ref + section, the one resume row with its proof, the
   milestone's tooling line — and the standing rule that when block and plan
   disagree, the plan wins. The standing goal for any Shadow seat is static;
   only what it points at changes.
3. **No proof, no completed.** A task carries a `proof:` that can refuse bad
   work (`cmd`, `read`, or `gate <owner>`). `shadow accept --row ~hash`
   reruns the proof in a clean detached checkout and is the only code path
   that flips a task. `shadow lint` enforces the grammar mechanically.

## Install — out of the box

Requires Git, Bash, Python 3.10+, and at least one native coding host
(Claude Code, Codex, or Cursor).


```bash
git clone https://github.com/firstbitelabsllc/shadow.git && cd shadow
bash install.sh          # links `shadow` into ~/.local/bin + mounts the skill in each host
shadow doctor
```

Git, Bash, Python 3.10+. **No Node, no npm, no package manager** — the clone
*is* the install, and `git pull` is the update.

Then paste the fifteen-line standing goal from
[host integration](docs/reference/host-integration.md) into each host's
top-level instructions (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, Cursor
user rules). That is the whole setup: a host that loads only that block
cold-starts knowing where truth lives and what to do next.

## The loop

```bash
shadow status                 # the durable board — same list from anywhere
shadow amp --repo <project>   # one goal block: pointer + resume + proof, ≤4k chars
shadow lint PLAN.md           # the grammar, mechanically enforced
shadow accept --row ~ab12 --repo <project>   # rerun proof in a clean checkout, flip the row
shadow browse                 # read-only loopback board at :7191
shadow host run --host codex --repo <clean worktree> \
  --task-file <frozen task> --task-id <id> --allowed-path <exact path> \
  --out <repo>/.shadow/evidence/<id>.json    # one sealed delegated task
```

`shadow init --here` bootstraps a new repo's plan. The method itself is one
page — [`AGENT.md`](AGENT.md) — enforced by
[the grammar](docs/reference/grammar.md); the proxy stance (never open empty,
never ask "which project?", the chief-of-staff moves are Shadow's own) is
part of that law.

## What Shadow refuses to be

- **A second store.** No database, no daemon, no scheduler, no cloud worker,
  no chat-transcript memory. If a surface could mutate a row outside
  `PLAN.md`, it is banned. (This is also the standing answer to "should we
  install a memory service?" — see [honcho](docs/reference/honcho.md).)
- **A credential or provider layer.** Native hosts own auth, model, and
  account choice; `shadow host run` passes no selector and records none.
- **A queue that pauses your projects.** Shadow supports the lane being
  worked; every project keeps shipping the highest-value reachable row in
  its own plan.

## Privacy boundary

Local by default; the browser binds to loopback. Evidence is bounded to
`.shadow/evidence/` inside the project. Prompts, transcripts, credentials,
provider payloads, and private absolute paths stay out of receipts. There is
no telemetry seam — local receipts and git history are the only observation
surfaces. See the [privacy contract](docs/reference/privacy.md).

## Limitations

- `shadow host run` runs one sealed task through one named host; it never
  launches work on its own, swaps hosts, retries, or owns a queue.
- `shadow accept` reruns only `cmd`-classed proofs; `read` and `gate` proofs
  are judgments a person or agent re-observes.
- A receipt is evidence to review, not automatic acceptance.

## Development

```bash
scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py'
scripts/shadow-python.sh scripts/shadow-lint.py PLAN.md
scripts/shadow-python.sh scripts/shadow-release-package.py --allow-dirty
```

[Quick start](docs/guide/quickstart.md) ·
[Commands](docs/reference/commands.md) ·
[Host integration](docs/reference/host-integration.md) ·
[Amp](docs/reference/amp.md) ·
[Grammar](docs/reference/grammar.md) ·
[Privacy](docs/reference/privacy.md). MIT licensed.

<p align="center"><img src="assets/shadow-banner.svg" alt="Shadow reads a plan, acts on one bounded task, verifies proof, and leaves a resume point." width="100%" /></p>

# Shadow

Your chief of staff for AI coding work.

Shadow tells you what work is trying to achieve, what is happening, what
proof exists, and which A/B/C choice needs you. It drives an existing native
coding tool only when you ask and reports the proof without taking custody of
your login or conversation.

Shadow scopes to one repository at a time; other projects keep working from
their own `PLAN.md`.

## See it

![Shadow's board](https://raw.githubusercontent.com/firstbitelabsllc/shadow/main/docs/assets/board-desktop.png)

*The board: one card per project, with its mode, status, lint result, and task
counts. Running locally against a demo portfolio — Sunrise Bakery, Orbit, and
Fieldnotes are fictional projects; unedited screenshot of v4.0.x.*

Open a project and Shadow states the Outcome, what changed, the proof, and the
one A/B/C decision waiting for you.

![A brief and the decision waiting on you](https://raw.githubusercontent.com/firstbitelabsllc/shadow/main/docs/assets/brief-decision.png)

*A brief and its waiting decision; nothing changes until you choose. Same demo
portfolio, unedited screenshot of v4.0.x.*

![The same board at phone width](https://raw.githubusercontent.com/firstbitelabsllc/shadow/main/docs/assets/board-phone.png)

*The same board at phone width. Unedited screenshot of v4.0.x.*

## Five-minute install

Requires Git, Bash, Python 3.10+, Node.js 20+, and at least one supported
coding host.

```bash
git clone https://github.com/firstbitelabsllc/shadow.git
cd shadow
npm install -g .
shadow doctor
```

To mount the same public skill in a host:

```bash
ln -sfn "$(pwd)" "$HOME/.claude/skills/shadow"
ln -sfn "$(pwd)" "$HOME/.agents/skills/shadow"
ln -sfn "$(pwd)" "$HOME/.cursor/skills/shadow"
```

## Workflow

Start in the repository whose work you want to understand:

```bash
shadow init --here
shadow status
shadow browse
```

`PLAN.md` is the durable authority — one markdown plan per repo, one writer at
a time. The loopback browser renders each project's plans as a read-only board:
mode, current milestone, task counts, and the one decision waiting for you. It
never writes.

A task is a state the world reaches plus a `proof:` that can refuse
bad work (`cmd`, `read`, or `gate <owner>`). A row flips to completed only in
the same commit as its proof line, and `shadow accept --row ~hash` is the only
code path that does it — it reruns the row's `cmd` proof in a clean detached
checkout first. `shadow lint PLAN.md` is the mechanical enforcer and runs in
the test gate. The whole method is `AGENT.md` (one page) and
`docs/reference/grammar.md` (the grammar).

Delegation to a native host is one sealed command — no roster, no routing
layer; provider and account choice live in your own config:

```bash
shadow host run --host codex --repo <clean worktree> \
  --task-file <frozen task> --task-id <id> --allowed-path <exact path> \
  --out <repo>/.shadow/evidence/<id>.json
```

## Privacy boundary

- Local by default; the browser binds to loopback.
- `PLAN.md` remains the only work authority.
- Evidence is bounded to `.shadow/evidence/` inside the project.
- Prompts, raw transcripts, credentials, provider payloads, and absolute
  private paths are not stored in receipts.
- Shadow does not relay credentials, run a cloud worker, watch in the
  background, or maintain a second queue. Provider, model, and account choice
  live in your own config, never in Shadow.
- There is no telemetry seam: local receipts and git history are the only
  observation surfaces. See the [privacy contract](docs/reference/privacy.md).

## Limitations

- `shadow host run` runs one sealed task through one named host; it never
  launches work on its own, swaps a host, retries, or owns a queue. The lead
  chooses whether to run it and accepts proof.
- `shadow accept --row` reruns only `cmd`-classed proofs; `read` and `gate`
  proofs are judgments a human or agent re-observes, not subprocesses.
- Host availability and authentication remain owned by Codex, Claude Code, or
  Cursor.
- A receipt is evidence to review, not automatic acceptance.

## Development

```bash
npm ci
npm run verify
npm run docs:build
```

See [the quick start](docs/guide/quickstart.md), [commands](docs/reference/commands.md),
and [privacy contract](docs/reference/privacy.md). MIT licensed.

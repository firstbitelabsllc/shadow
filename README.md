<p align="center"><img src="assets/pilot-puppy-banner.svg" alt="Pilot Puppy reads a plan, acts on one bounded task, verifies proof, and leaves a resume point." width="100%" /></p>

# Pilot Puppy

Your chief of staff for AI coding work.

Pilot Puppy tells you what matters, what is happening, what proof exists, and
which A/B/C choice needs you. When work is ready, it can hand one sealed task
to native Codex, Claude Code, or Cursor and validate the result without taking
custody of your login or conversation.

It supports a project's own work lane; it is not a gate that pauses unrelated
projects. One sealed task makes a handoff reviewable, while each project keeps
shipping the highest-value reachable work in its own `PLAN.md`.

## Five-minute install

Requires Git, Bash, Python 3.10+, and at least one supported coding host.

```bash
git clone https://github.com/firstbitelabsllc/pilot-puppy.git
cd pilot-puppy
npm install -g .
pilot-puppy doctor
```

To mount the same public skill in a host:

```bash
ln -sfn "$(pwd)" "$HOME/.claude/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.agents/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.cursor/skills/pilot-puppy"
```

## One real workflow

Start in the repository whose work you want to understand:

```bash
pilot-puppy init --here
pilot-puppy status
pilot-puppy browse
```

`PLAN.md` is durable authority. The loopback browser renders its current
Outcome, one plain-language briefing, proof status, and up to three choices.

To run a bounded task, write the complete task to a file, choose one native
host, and list the only paths it may change:

```bash
pilot-puppy host run \
  --host codex \
  --repo "$PWD" \
  --task-file /tmp/fix-login-copy.md \
  --task-id fix-login-copy \
  --allowed-path src/login.tsx \
  --allowed-path src/login.test.tsx \
  --out .pilot-puppy/evidence/fix-login-copy.json
```

The worktree must be clean. A successful host must return passing tests and a
bounded receipt; Pilot Puppy still marks that claim unreviewed until the lead
reproduces the proof.

## Privacy boundary

- Local by default; the browser binds to loopback.
- `PLAN.md` remains the only work authority.
- Evidence is bounded to `.pilot-puppy/evidence/` inside the project.
- Prompts, raw transcripts, credentials, provider payloads, and absolute
  private paths are not stored in receipts.
- Pilot Puppy does not choose models, relay credentials, run a cloud worker,
  watch in the background, or maintain a second queue.

## Honest limitations

- You choose the native host; Pilot Puppy does not optimize model routing.
- Host availability and authentication remain owned by Codex, Claude Code, or
  Cursor.
- A receipt is evidence to review, not automatic acceptance.
- Voice and remote-control clients are not included.

## Development

```bash
npm ci
npm run verify
npm run docs:build
```

See [the quick start](docs/guide/quickstart.md), [commands](docs/reference/commands.md),
and [privacy contract](docs/reference/privacy.md). MIT licensed.

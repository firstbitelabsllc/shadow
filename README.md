<p align="center"><img src="assets/pilot-puppy-banner.svg" alt="Pilot Puppy reads a plan, acts on one bounded task, verifies proof, and leaves a resume point." width="100%" /></p>

# Pilot Puppy

Your chief of staff for AI coding work.

Pilot Puppy tells you what work is trying to achieve, what is happening, what
proof exists, and which A/B/C choice needs you. It helps you name the right
local role for a task, drives an existing native coding tool only when you ask,
and reports the proof without taking custody of your login or conversation.

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
pilot-puppy roster init
pilot-puppy roster show
pilot-puppy status
pilot-puppy browse
```

`PLAN.md` is durable authority. The loopback browser renders its current
Outcome, one plain-language briefing, proof status, and up to three choices.

`roster init` creates a generic local list of six work roles: `lead`,
`planner`, `bulk`, `debug`, `critic`, and `hard-ic`. It is not a model picker
or dispatch system. Associate those generic names with your own native-tool
setup privately; the browser, project status, and receipts never contain that
mapping.

For a bounded handoff, first ask Pilot Puppy to make one transparent local
selection. It chooses only among declared slots for the requested task kind,
shows a same-role alternative and escalation point, and launches nothing:

```bash
pilot-puppy route \
  --repo "$PWD" \
  --task-id fix-login-copy \
  --task-file /tmp/fix-login-copy.md \
  --task-kind dev \
  --out .pilot-puppy/evidence/fix-login-copy.route.json
```

The result might say `bulk via cursor`, `bulk via codex`, or that no declared
slot is available. That choice is a local hint based only on the roster and a
bounded version probe—never an account, quota, model, or billing claim.

Then explicitly run the selected native host and list the only paths it may
change. Passing the route packet makes the host fail closed if the frozen task,
roster revision, or selected host changed in between:

```bash
pilot-puppy host run \
  --host cursor \
  --repo "$PWD" \
  --task-file /tmp/fix-login-copy.md \
  --task-id fix-login-copy \
  --allowed-path src/login.tsx \
  --allowed-path src/login.test.tsx \
  --route-file .pilot-puppy/evidence/fix-login-copy.route.json \
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
- The local roster is not project evidence and never feeds browser, status, or
  receipts. Pilot Puppy does not collect provider, model, account, or quota
  details for it.
- Pilot Puppy does not relay credentials, run a cloud worker, watch in the
  background, or maintain a second queue.

## Honest limitations

- Route selects only a declared role and native-host surface; it cannot
  guarantee a host's proprietary model, account state, quota, or billing tier.
- Route never launches work, silently swaps a host, retries, or owns a queue.
  The lead still chooses whether to run the selected host and accepts proof.
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

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
`planner`, `dev`, `debug`, `review`, and `hard-dev`. It is not a model picker
or dispatch system. To change a role's local first choice, explicitly prefer one
already-declared host:

```bash
pilot-puppy roster prefer --role dev --host codex
```

Existing local rosters using the former `bulk`, `critic`, or `hard-ic` labels
are read safely and normalized on the next write; new route packets use only
the current role names.

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

The result might say `dev via cursor`, `dev via codex`, or that no declared
slot is available. That choice is a local hint based only on the roster and a
bounded version probe—never an account, quota, model, or billing claim.

This is where the practical efficiency comes from: routine, well-scoped work
uses the local `dev` policy first; difficult implementation uses `hard-dev`;
debugging, planning, review, and acceptance stay separate. You set the local
priority once, then each route makes that choice visible before any native host
uses time or tokens. Pilot Puppy does not pretend to know provider prices,
models, or account usage.

If your own native tools need an explicit local model/profile selector, add it
to a separate owner-only overlay. This is optional: the route still selects the
generic role and host first, and this overlay never changes that decision.

```bash
pilot-puppy seat init
pilot-puppy seat set --slot dev-cursor --model MODEL
pilot-puppy seat show
```

`seat` only binds a selector to a slot already declared in the local roster.
It cannot add a seat, change a role/host/priority, query a provider, or hold a
credential. Use the exact selector your native tool documents; Pilot Puppy does
not look up models, accounts, quota, pricing, or availability.

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
  --use-seat \
  --out .pilot-puppy/evidence/fix-login-copy.json
```

The worktree must be clean. A successful host must return passing tests and a
bounded receipt; Pilot Puppy still marks that claim unreviewed until the lead
reproduces the proof.

## Drive a few separate pieces of work

When one project has a few clearly separate changes, keep their short task
instructions in the same `PLAN.md` as one Drive Packet. This is still one plan
and one foreground session—not a background queue.

```markdown
<!-- pilot-puppy-drive.v1
{
  "schema": "pilot-puppy.drive.v1",
  "revision": 1,
  "lanes": [
    {
      "id": "improve-welcome-copy",
      "state": "ready",
      "task_kind": "dev",
      "summary": "Make one short explanation easier to understand.",
      "task": "Improve one short explanation and keep the focused check green.",
      "allowed_paths": ["README.md", "tests/test_route.py"],
      "proof": ["npm", "test"],
      "merge": "manual"
    }
  ]
}
-->
```

First, prepare the work. This only explains and freezes the safe handoffs; it
does not start a coding tool.

```bash
pilot-puppy drive prepare --repo "$PWD"
```

Then explicitly start that exact prepared session:

```bash
pilot-puppy drive launch --repo "$PWD" --session SESSION_ID
```

Drive rechecks the unchanged plan and Git revision, gives each lane its own
clean worktree and branch, uses the selected native host, checks the change and
the plan's named test command, then commits a green result for review. It
prepares at most three lanes, never overlaps allowed paths or a native host,
and keeps every worktree/branch rather than deleting it. If every piece is
green, you can take one separate local acceptance step:

```bash
pilot-puppy drive accept --repo "$PWD" --session SESSION_ID
```

Acceptance repeats each named check in a separate clean lead checkout, then
creates one local Git merge commit in the source project. Drive never pushes,
opens a PR, deploys, publishes, spends money, or silently retries a failed
lane.

The loopback browser shows this as **Ready work**. It can prepare the work,
then offers a separate **Start ready work** button. When every piece passes, it
offers **Bring checked work into this project**; that repeats the check in a
separate clean copy before making the local merge. Neither page load nor
preparation starts a coding tool, and the browser never shows the task text,
file list, test command, provider, or credentials.

## Privacy boundary

- Local by default; the browser binds to loopback.
- `PLAN.md` remains the only work authority.
- Evidence is bounded to `.pilot-puppy/evidence/` inside the project.
- Prompts, raw transcripts, credentials, provider payloads, and absolute
  private paths are not stored in receipts.
- The local roster is not project evidence and never feeds browser, status, or
  receipts. Pilot Puppy does not collect provider, model, account, or quota
  details for it.
- The optional private seat overlay is read only after a sealed route has
  selected its exact native slot. Its selector value and path never appear in
  browser or status output, plans, route packets, host attempts, or packages.
- Pilot Puppy does not relay credentials, run a cloud worker, watch in the
  background, or maintain a second queue.
- Optional Langfuse observation is off by default and can only send a closed,
  metadata-only lifecycle record after local evidence exists. It cannot steer
  work or receive plan/task text, prompts, code, paths, commands, or provider
  data. See the [privacy contract](docs/reference/privacy.md).

## Honest limitations

- Route selects only a declared role and native-host surface; it cannot
  guarantee a host's proprietary model, account state, quota, or billing tier.
- `--use-seat` is an explicit local CLI flag, not provider discovery or smart
  pricing. It fails before launch if the sealed route has no matching private
  selector.
- Route never launches work, silently swaps a host, retries, or owns a queue.
  The lead still chooses whether to run the selected host and accepts proof.
- Drive is a foreground local batch helper, not a GitHub or deployment robot:
  it commits only to kept review branches and leaves remote delivery and final
  acceptance with the lead.
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

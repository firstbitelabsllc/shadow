# Local roster

The roster gives you six generic local work roles:

| Role | Use it for |
|---|---|
| `lead` | Own the outcome, plan, review, and acceptance. |
| `planner` | Bound an ambiguous, high-risk, or high-leverage decision. |
| `dev` | Make an ordinary, well-scoped implementation change. |
| `debug` | Investigate a reproducible failure or unknown. |
| `review` | Independently challenge a proposed change or proof claim. |
| `hard-dev` | Deliver a difficult implementation slice with explicit proof. |

Create or inspect the local roster:

```bash
shadow roster init
shadow roster show
shadow roster prefer --role dev --host codex
```

`prefer` moves one already-declared role/host slot to priority 1 within that
role. It preserves every other role and the relative order of the remaining
slots; it rejects a missing or disabled slot rather than creating or enabling
one, and it never launches work. Repeating an already-first preference is a
local no-op.

Choose another local file only when you mean to:

```bash
shadow roster init --file /safe/local/path/roster.json
shadow roster show --file /safe/local/path/roster.json --json
shadow roster prefer --role dev --host codex --file /safe/local/path/roster.json
```

`init` never overwrites an existing roster. The default file stays outside the
project; `--file` is an explicit local choice. The roster is a local role map,
not another plan or queue. It is created with owner-only permissions; show and
route reject a group- or world-readable existing roster.

Older local files that call `dev`, `review`, or `hard-dev` by their former
labels `bulk`, `critic`, or `hard-ic` remain readable. Shadow normalizes
those aliases in memory and writes the current names on the next preference
change; route packets never emit the legacy labels.

## What it does not do

The roster does not choose a provider or model, measure account quota, start a
native host, launch a worker, retry work, or dispatch anything automatically.
[`shadow route`](routing.md) may choose only a declared generic role and
native-host surface; it prints the choice, alternatives, and escalation and
then stops. You still explicitly decide whether to run native Codex, Claude
Code, or Cursor, and a lead still reviews the proof.

Route cannot verify or guarantee the proprietary model or billing tier a host
uses internally.

It has no cloud executor, voice mode, credential relay, transcript store,
background queue, daemon, or watcher. The roster itself never becomes another
authority alongside `PLAN.md`.

For an optional named native selector, use the separate local `seat` overlay:

```bash
shadow seat init
shadow seat set --slot dev-cursor --model MODEL
```

It can bind only a slot already declared and enabled in this roster. It cannot
change the generic role, host, priority, or enabled state. The browser, `status`,
route, and project receipts never read or publish the overlay. Do not put
credentials, prompts, transcripts, provider payloads, private paths, accounts,
or quota data in either local configuration.

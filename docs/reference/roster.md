# Local roster

The roster gives you six generic local work roles:

| Role | Use it for |
|---|---|
| `lead` | Own the outcome, plan, review, and acceptance. |
| `planner` | Bound an ambiguous, high-risk, or high-leverage decision. |
| `bulk` | Make an ordinary, well-scoped implementation change. |
| `debug` | Investigate a reproducible failure or unknown. |
| `critic` | Independently challenge a proposed change or proof claim. |
| `hard-ic` | Deliver a difficult implementation slice with explicit proof. |

Create or inspect the local roster:

```bash
pilot-puppy roster init
pilot-puppy roster show
```

Choose another local file only when you mean to:

```bash
pilot-puppy roster init --file /safe/local/path/roster.json
pilot-puppy roster show --file /safe/local/path/roster.json --json
```

`init` never overwrites an existing roster. The default file stays outside the
project; `--file` is an explicit local choice. The roster is a local role map,
not another plan or queue. It is created with owner-only permissions; show and
route reject a group- or world-readable existing roster.

## What it does not do

The roster does not choose a provider or model, measure account quota, start a
native host, launch a worker, retry work, or dispatch anything automatically.
[`pilot-puppy route`](routing.md) may choose only a declared generic role and
native-host surface; it prints the choice, alternatives, and escalation and
then stops. You still explicitly decide whether to run native Codex, Claude
Code, or Cursor, and a lead still reviews the proof.

Route cannot verify or guarantee the proprietary model or billing tier a host
uses internally.

It has no cloud executor, voice mode, credential relay, transcript store,
background queue, daemon, or watcher. The roster itself never becomes another
authority alongside `PLAN.md`.

Keep any named-seat mapping in your own private setup. The browser, `status`,
and project receipts never read or publish the roster. Do not put credentials,
prompts, transcripts, provider payloads, or private paths in it.

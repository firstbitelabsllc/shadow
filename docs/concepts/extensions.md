# Extensions

Vidux core is markdown + git. Extensions plug external systems (kanban boards, issue trackers, project planners) into the same store via a small contract — without changing the cycle or the discipline.

## Why extensions

Some teams need their tasks visible on a board their non-coder collaborators can read and write to. Some teams need their issues correlated with a tracker that already runs their company's planning rituals. Vidux doesn't fight that — it absorbs it. PLAN.md stays the source of truth; the external board becomes a live mirror that round-trips through `scripts/vidux-inbox-sync.py`.

## The contract

Every adapter subclasses `AdapterBase` and implements six methods:

| Method | Direction | Purpose |
|--------|-----------|---------|
| `fetch_inbox` | external → | Return every item on the board as `ExternalItem` |
| `push_task`   | → external | Create an external item from a `PlanTask` |
| `pull_status` | external → | Read current `VidxStatus` for one item |
| `push_status` | → external | Move the item to the column matching a `VidxStatus` |
| `pull_fields` | external → | Read typed custom-field values (Evidence, ETA, …) |
| `push_fields` | → external | Write typed custom-field values |

The pipeline (`pending` → `in_progress` → `in_review` → `completed`) is the adapter-facing column. The `Blocked` flag is **orthogonal** — written via `push_fields({'_blocked': True})` so the pipeline column never moves when an item gets blocked. `push_status(BLOCKED)` is reserved and must raise.

That full pipeline is real in the adapter layer, but some local shell helpers still operate on the four-state core subset. In practice, `in_review` is most useful when the board or PR workflow needs it; local scripts such as `vidux-status.py` and `vidux-loop.sh` still assume `pending`, `in_progress`, `completed`, and `blocked`.

See [`adapters/README.md`](https://github.com/leojkwan/vidux/blob/main/adapters/README.md) in the repo for the six-step authoring guide and the round-trip test rubric.

## Adapters shipped today

| Adapter | Status | Notes |
|---------|--------|-------|
| `gh_projects` | live | GitHub Projects v2 adapter |
| `linear`      | live | Linear GraphQL adapter |
| `asana`       | stub | API + auth scaffolded; subclass-ready |
| `jira`        | stub | API + auth scaffolded; subclass-ready |
| `trello`      | stub | API + auth scaffolded; subclass-ready |

## Composition over migration

Adapters are **additive**. A repo's `vidux.config.json` can list multiple `inbox_sources` entries — `gh_projects` and `linear` coexist. Cards minted on one surface stay on that surface; vidux does not cross-bridge them. Per-adapter quota buckets stay independent: GitHub PAT vs Linear personal-key never share a rate limit.

This means migrating from one tracker to another is a no-op — you don't migrate, you just add the new adapter alongside the old one and let teams use whichever surface fits the work.

## Codebase-owned projects

For repo lanes, the safest external project is named after the codebase it
feeds, such as `<repo-name>` or `<service-name>`. Product buckets such as
"Launch Queue" or "Infrastructure" can still exist in a planning tool, but
they are planning buckets, not repo intake queues.

The Linear adapter supports an explicit guardrail:

```json
{
  "adapter": "linear",
  "enabled": true,
  "config": {
    "team_id": "linear-team-uuid",
    "project_id": "linear-project-uuid",
    "project_name": "repo-name",
    "auto_promote_target": "vidux"
  }
}
```

When `project_name` is present, `fetch_inbox`, `push_task`, status sync, and
field sync all validate the remote Linear project before doing work. A copied
config that still points at "Launch Queue" fails closed instead of promoting
product-board cards into the wrong repo plan.

## Local policy overlays

Core vidux stays open-source and organization-neutral. If your team needs
local policy such as "which Linear projects map to which repos", "which review
bot blocks merge", or "which cron cadence to use overnight", put that in a
separate overlay skill or runbook rather than hardcoding it into core.

A good overlay:

- Loads after `/vidux` and says it overlays core instead of replacing it.
- Stores organization-specific project ids, repo names, review tools, and
  merge precedents outside the public adapter docs.
- References the generic adapter contract here instead of duplicating it.
- Treats contradictions with core as overlay bugs.

That split keeps Vidux reusable while still letting a team make its own
opinionated operating layer.

## Sync architecture

The repo ships one sync entry point: `scripts/vidux-inbox-sync.py`. Operators can schedule separate invocations per adapter via `--only-adapter` when they want independent cadences or credentials:

| Invocation shape | Scope | Credential bucket |
|------|-------|-------|
| `python3 scripts/vidux-inbox-sync.py --config <repo>/vidux.config.json --only-adapter gh_projects --direction=both` | GitHub Projects only | GitHub token file |
| `python3 scripts/vidux-inbox-sync.py --config <repo>/vidux.config.json --only-adapter linear --direction=both` | Linear only | Linear token file |
| `python3 scripts/vidux-inbox-sync.py --config <repo>/vidux.config.json --direction=both` | All enabled adapters for that repo | All configured token files |

Separating scheduler entries is optional, but the `--only-adapter` split is the repo-supported way to scope a run to one external surface.

## State sidecar

Per plan, `<plan_dir>/.external-state.json` stores:

- `task_id ↔ external_id` mapping per adapter
- Adapter-specific metadata (e.g. Linear's `task_metadata` sidecar after the 2026-04-25 description-codec drop)

The sidecar is **gitignored** because plans live under `projects/*` which is itself gitignored on private fleets. **Never `git stash drop` a sidecar that was captured by `stash push -u`** — that permanently breaks the dedup story and the next sync sees every tracked item as novel. Always `git stash pop`.

## Auto-promote

When an adapter's config sets `auto_promote_target: <plan-dir>`, novel external items skip `INBOX.md` and land directly in that plan's PLAN.md as:

```markdown
- [pending] BD-N: <title> [Source: <adapter>:<id>]
```

`BD-` = "board-dropped". The sequence is per-plan and minted via `_next_bd_seq` in the sync script.

Missing `auto_promote_target` paths fail closed. Vidux refuses to fall back to `INBOX.md`, because that would route external work to the first plan in the store instead of the lane that owns the board/project.

Auto-promote also has a batch safety cap: by default, more than 25 novel items
in one run fails closed before mutating `PLAN.md`. Set
`auto_promote_max_new` to a different integer, or to `null` to disable the cap
for a deliberate bulk import.

**Round-trip dedup is required for safety.** Without it, the push half mints duplicate cards every cycle (push uses `task.id` as the mapping key while auto-promote names cards `BD-N` — a namespace mismatch that causes infinite-mint). The sync script's push reconcile must scan task lines for an existing `[Source: <adapter>:<id>]` marker before pushing.

## Self-extending lanes

Some organizations let lanes opt in to adjacent work. A lane that declares
`Self-extending: true` in its prompt can **claim adjacent external cards** when
its queue empties or when it spots a card whose project/labels/title intersect
its scope.

Claim discipline:

1. Set `_blocked: true` on the external card with reason `claimed-by-<lane>:<cycle-ts>` — a 5-minute soft-claim window.
2. Move external status to In Progress.
3. Append a `[pending]` task to the local PLAN.md citing `[Source: <adapter>:<id>] [Claimed: <ts>]`.
4. After the local task transitions to `[in_progress]`, clear `_blocked`. The external In Progress state is now the source-of-truth claim.

Two lanes firing the same cycle can't double-claim — the second one sees `_blocked=true` from the first and moves to the next candidate. No cross-lane coordination protocol needed; the soft-claim IS the lock.

## When NOT to use an adapter

- Your project has one author and one reviewer who both write code → `INBOX.md` + a Decision Log is plenty.
- Your team already has a vidux-native cron loop that's working — adding an adapter doubles the surface area without solving a clear problem.
- The external system charges per API call and your plan churn is high — the round-trip cost will dwarf the value.

Vidux works without any extension. Extensions exist for teams whose stakeholders live on a kanban board.

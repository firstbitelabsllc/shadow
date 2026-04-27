# vidux adapters — writing a new adapter

An adapter plugs an external kanban / issue-tracker into vidux as an
`inbox_sources` entry in `vidux.config.json`. The external board becomes a
live, bi-directional view of PLAN.md `[pending]` + `[in_progress]` +
`[in_review]` tasks. PLAN.md stays the source of truth; the adapter round-
trips status + custom fields; the sync script reconciles.

Adapters shipped today:

| adapter       | status  | file                 |
|---------------|---------|----------------------|
| `gh_projects` | live    | `gh_projects.py`     |
| `linear`      | live    | `linear.py`          |
| `asana`       | stub    | `asana.py`           |
| `jira`        | stub    | `jira.py`            |
| `trello`      | stub    | `trello.py`          |

## Linear adapter — description is human-only (2026-04-25 migration)

Earlier versions of `linear.py` round-tripped `Evidence` / `Investigation` /
`Source` / `ETA` / `VidxId` / `VidxPlan` inside the issue `description` using
HTML-comment delimiters: `<!-- vidux:Evidence -->...<!-- /vidux:Evidence -->`.
Linear renders HTML comments as visible text in its description UI, so the
markers were leaking into the rendered view and breaking human readability.

The adapter now writes **clean human-facing markdown only** — Purpose /
Evidence / Investigation / Source / ETA sections (sections with no source data
are omitted). Round-trip metadata moves into the per-plan
`.external-state.json` sidecar under
`adapters.linear.task_metadata`, keyed by VidxId. The sync script reads / writes
the sidecar; the adapter never inspects descriptions for codec markers.

Migration: `scripts/strip-linear-codec-markers.py` rewrote all 92 in-flight
EVE-team issues + populated their plan sidecars from the extracted block data.
Idempotent. The codec is fully deprecated; `_parse_body` and the `_DELIM_*`
constants are gone from `adapters/linear.py`.

## What Linear gives you that GH Projects doesn't

GH Projects V2 is "issues + a kanban with custom fields." Linear is a full
productivity suite. The adapter (above) handles Issues — the rest of Linear's
surface area can layer on without breaking the 6-method contract:

| Linear concept   | Maps to                                            | Status            |
|------------------|----------------------------------------------------|-------------------|
| **Issue**        | vidux task in PLAN.md                              | shipped (this adapter) |
| **Sub-issue**    | bullet under a task — set `parentId` on issueCreate | configurable via `parent_id` field |
| **Project**      | one codebase-owned repo intake queue by default (e.g. `<repo-name>`) | configurable via `project_id`; add `project_name` to fail closed on wrong bindings |
| **Initiative**   | top-level cross-cutting goal (workspace-wide)      | M:M via `InitiativeToProject` join — extension API |
| **Cycle**        | sprint window (orthogonal to projects)             | optional — set `cycleId` in `push_fields` |
| **Project milestone** | phase marker inside one project (Phase 0 → 1) | set `projectMilestoneId` |
| **Comment**      | discussion thread on an issue                      | `commentCreate` mutation — not in core contract |
| **Label**        | tag (workspace OR team scoped)                     | `default_label_ids` in adapter config + auto-managed `blocked` label |
| **Webhook**      | push notification for issue/comment changes        | future extension — would replace polling fetch_inbox |

The 6-method contract stays unchanged. New capabilities ride on top via
adapter-specific config (e.g. `project_id`, `cycle_id`) or out-of-band
extension methods (e.g. `add_comment`, `register_webhook`) that core vidux
never calls.

## Contract

Every adapter subclasses `AdapterBase` from `base.py` and implements six
methods:

| method         | direction  | purpose                                                |
|----------------|------------|--------------------------------------------------------|
| `fetch_inbox`  | external→  | Return every item on the external board as `ExternalItem`. |
| `push_task`    | →external  | Create an external item from a `PlanTask`. Returns opaque `external_id`. |
| `pull_status`  | external→  | Read current vidux `VidxStatus` for one item.         |
| `push_status`  | →external  | Move the item to the column matching a `VidxStatus`.  |
| `pull_fields`  | external→  | Read typed custom-field values (Evidence, ETA, …).    |
| `push_fields`  | →external  | Write typed custom-field values.                      |

`push_status(BLOCKED)` is reserved and must raise — blocked is orthogonal
to pipeline state. Callers write `Blocked=Yes` via
`push_fields({'_blocked': True})` so the item's pipeline column stays
whatever it was (`Dev` / `QA/Testing/Review` / etc.) and the blocked flag
composes on top. See `gh_projects.py` for the reference implementation.

## Linear codebase-project guardrail

Linear `project_id` values are opaque UUIDs, so a repo config can look right
while silently pointing at the wrong product bucket. To make repo intake
auditable, set `project_name` beside `project_id` whenever a Linear project is
meant to feed one codebase:

```json
{
  "adapter": "linear",
  "enabled": true,
  "config": {
    "token_file": "~/.config/vidux/linear.token",
    "team_id": "team-uuid",
    "project_id": "project-uuid",
    "project_name": "repo-name",
    "state_mapping": {
      "pending": "state-backlog",
      "in_progress": "state-started",
      "in_review": "state-review",
      "completed": "state-done"
    },
    "auto_promote_target": "vidux",
    "auto_promote_max_new": 25
  }
}
```

When `project_name` is present, the adapter looks up the Linear project and
requires the remote name to match before reading or mutating issues. This is
the supported shape for codebase-owned repo queues. Product planning projects
may omit `project_name`, but then the config review must treat that source as
an intentionally unguarded product bucket.

`auto_promote_max_new` protects clean worktrees whose gitignored sidecars are
missing. If a source would append more than the cap as fresh `BD-*` tasks, the
sync fails closed before mutating `PLAN.md`.

With `auto_promote_target`, sync does not create new external issues from
local-only PLAN rows. It still reconciles status for tasks already linked by a
`[Source: <adapter>:<id>]` marker so imported cards can move to completed on
the external board.

## Six steps to write a new adapter

### 1. Subclass `AdapterBase`

```python
from .base import AdapterBase, ExternalItem, PlanTask, VidxStatus, register


@register
class MyToolAdapter(AdapterBase):
    name = "mytool"
    config_schema = {
        "required": ["token_file", "workspace_id", "column_mapping"],
    }

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # adapter-specific setup — cache ids, open sessions, etc.
```

`name` is the string users type in their `vidux.config.json` under
`adapter:`. `config_schema.required` is checked by the base class at
`__init__` — missing keys raise `ValueError` before any network call.

### 2. Fill the six abstract methods

Read `gh_projects.py` for a complete example. Notes:

- **Lazy metadata discovery.** Don't hardcode the external API's internal
  ids (column ids, field ids). On first use, query the external API and
  cache `{name: id}` maps so UI renames don't break the adapter.
- **Token loading.** Read credentials from `config["token_file"]` inline
  (`open(os.path.expanduser(path)).read().strip()`). Never accept a raw
  token in `config` — that makes `vidux.config.json` a secrets file.
- **Error shape.** Wrap external-API failures in an adapter-specific
  exception (`GhProjectsError` in the reference impl). The sync script
  surfaces these via exit-code 3.
- **Status ↔ column inverse.** Pre-compute the inverse of the
  `column_mapping` dict at `__init__` so `_status_from_column("Dev")`
  doesn't scan the dict every call.

### 3. Define `config_schema`

Minimum: a `required: [str]` list of the config keys the adapter depends
on. The base class's `validate_config` ensures each key is present AND
non-empty before instantiation succeeds. If you need deeper validation
(URL format, enum values), override `validate_config` in the subclass.

### 4. Register in `adapters/__init__.py`

The `@register` decorator populates the registry at class-definition
time — but Python only runs class-definition code when the module is
imported. Add a one-liner to `adapters/__init__.py`:

```python
from adapters import mytool  # noqa: F401
```

Now `get_adapter("mytool")` resolves after `from adapters import ...`.

### 5. Add a config block to `vidux.config.json`

See `vidux.config.example.json` for the shape. The `inbox_sources` entry:

```json
{
  "adapter": "mytool",
  "enabled": true,
  "config": {
    "token_file": "~/.config/vidux/mytool.token",
    "workspace_id": "abc123",
    "column_mapping": {
      "pending":     "Backlog",
      "in_progress": "In Progress",
      "in_review":   "Review",
      "completed":   "Done"
    }
  }
}
```

`enabled: false` lets users keep config around while disabling sync.

### 6. Round-trip test

Before shipping, verify end-to-end against the real external board:

1. **Push a test item.** Seed a new `[pending]` task in a throwaway PLAN.md,
   run `python3 scripts/vidux-inbox-sync.py --direction=push`, confirm the
   item appears in the external UI in the right column.
2. **Pull status change.** Move the item to the "in_review" column in the
   UI, run `--direction=pull`, confirm the PLAN.md task flips to
   `[in_review]`.
3. **Round-trip custom fields.** Set `[ETA: 2h]` on a task, push, read
   back via `--direction=pull`, confirm value survived.
4. **Blocked orthogonality.** `push_fields({'_blocked': True})` — confirm
   the item's pipeline column is unchanged AND the blocked flag is set on
   the external surface.
5. **Idempotency.** Run `--direction=both` twice in a row with no
   intermediate changes. Second run should be a no-op (no duplicate items,
   no duplicate INBOX.md lines).

Keep the throwaway PLAN.md local (inside a gitignored `projects/<slug>/`)
so the test items never land in production planning boards.

## Token file conventions

All adapters read credentials from single-line files under
`~/.config/vidux/`:

- `~/.config/vidux/gh-project.token`
- `~/.config/vidux/linear.token`
- `~/.config/vidux/asana.token`
- `~/.config/vidux/jira.email` + `jira.token`
- `~/.config/vidux/trello.key` + `trello.token`

All files chmod 600. Rotate-me / scope notes go in a sibling `.README` file
so the token file itself stays single-line `cat`-safe (the sync script
uses `GH_TOKEN=$(cat <file>)` shape).

Never commit any of these files. Never echo their contents. Never accept
a raw token in `vidux.config.json`.

## Related

- **Core contract:** `base.py` — `AdapterBase` ABC, `ExternalItem`,
  `PlanTask`, `VidxStatus`, `@register`.
- **Reference implementation:** `gh_projects.py`.
- **Sync script:** `../scripts/vidux-inbox-sync.py`.
- **Config schema:** `../vidux.config.json` + `../vidux.config.example.json`.

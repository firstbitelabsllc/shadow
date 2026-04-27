# The 8-Block Prompt Template

This page mirrors the current source guide in `guides/harness.md`. A vidux lane prompt is a **stateless harness**: it stores process, not current state. The queue, decisions, and progress live in `PLAN.md`.

For the runtime mechanics of how a prompt is consumed, see [Harness Authoring](/fleet/harness), [Claude Code Lifecycle](/fleet/claude-lifecycle), and [Codex Lifecycle](/fleet/codex-lifecycle).

## Block Order

The current harness guide uses this order:

| # | Block | What belongs here |
|---|---|---|
| 1 | `MISSION` | User-visible goal and retirement condition |
| 2 | `SKILLS` | The skills to load before acting |
| 3 | `GATE` | Quick check or scan gate that can abort the cycle early |
| 4 | `AUTHORITY` | Read order plus the files and systems this lane may touch |
| 5 | `CROSS-LANE` | Sibling-memory and hot-file checks |
| 6 | `ROLE BOUNDARY` | What this lane owns, and what belongs to others |
| 7 | `EXECUTION` | Worktree, verification, PR, and delegation rules |
| 8 | `CHECKPOINT` | The required `memory.md` append format |

The order is part of the contract. The gate runs before deeper reads, and cross-lane checks happen before any write-capable action.

## Mission

State the output, not the chores. Good mission blocks say what the lane exists to ship and when it should retire.

```markdown
MISSION
Own the docs site for this repo. Each cycle either advances an evidence-backed
task, fixes a docs regression, or leaves a proof-backed idle checkpoint. Retire
when the active docs plan has no pending or in-progress tasks.
```

Rules:

- Keep it to one short paragraph.
- Name the surface this lane owns.
- Include a retirement condition so the lane does not become a zombie.

## Skills

Load only the skills the lane actually needs.

```markdown
SKILLS
Load: /vidux, /frontend-design
```

Rules:

- Put `/vidux` first so the cycle and plan rules load before repo-specific helpers.
- Add brand or platform skills only when the lane really uses them.
- Avoid dumping doctrine into the prompt. The skill already carries it.

## Gate

The gate decides whether the cycle should work or exit in under a minute.

```markdown
GATE
- Dirty tree not mine -> append [QC] concurrent-cycle to memory.md and exit
- Same task in progress for 3+ cycles -> block it, note why, and exit
- Main CI red -> switch to fix-first mode
```

Rules:

- Gates are binary. Triggered means exit or change mode immediately.
- Writers use a quick-check gate; radars use a scan gate.
- Keep the gate short. A long gate burns cycles before work starts.

## Authority

The authority block names the read order and the writable surface.

```markdown
AUTHORITY
Read in this order every cycle:
1. `memory.md` (last 3 entries)
2. `PLAN.md`
3. `INBOX.md` when present
4. `git status --short` and `git log --oneline -10`

May edit:
- `docs/**`
- `README.md`
- `ARCHITECTURE.md`

Never edit:
- secrets or `.env*`
- sibling lane files except read-only memory scans
```

Rules:

- Start with the lane's own `memory.md`, then the repo plan.
- Name paths explicitly. "Read the tracker" is not specific enough.
- Include the no-touch paths, not just the owned ones.

## Cross-Lane

Read enough sibling state to avoid duplicate work.

```markdown
CROSS-LANE
- Read the newest sibling `memory.md` entries before acting
- Check hot files before editing shared surfaces
- Yield if another lane already owns the same files this cycle
```

Rules:

- This block is required for multi-lane fleets.
- The goal is deduplication and collision avoidance, not long summaries.
- Read sibling state before any file edits or PR actions.

## Role Boundary

Say what this lane is, and just as importantly, what it is not.

```markdown
ROLE BOUNDARY
Writer lane. Ships docs changes and plan updates for the docs surface.
Does not edit product code, secrets, or other lanes' prompt files.
```

Rules:

- Use plain ownership language.
- Mention adjacent surfaces the lane must not absorb.
- If the lane is read-only, say so explicitly.

## Execution

This block holds the concrete operating rules.

```markdown
EXECUTION
- Work from a dedicated worktree for code or docs changes
- Verify the affected checks before claiming done
- Open ready-for-review PRs by default; drafts are only for true WIP
- If 3+ minutes pass with no file write, abort the cycle instead of looping
```

Rules:

- Use literal commands when a command matters.
- Put worktree, verification, and PR rules here.
- Add delegation instructions only when the lane genuinely delegates.

## Checkpoint

Every cycle leaves one durable line in `memory.md`.

```markdown
CHECKPOINT
Append one line:
- [YYYY-MM-DDTHH:MM:SSZ lane-id] [TAG] What happened. Next: what happens next.
```

Rules:

- Keep it to one line.
- Tag it so future scans are searchable.
- Record blockers and next-step intent, not a prose recap of the diff.

## Compact Example

```markdown
MISSION
Maintain the docs surface for this repo until the docs sprint plan is complete.

SKILLS
Load: /vidux

GATE
- Dirty tree not mine -> [QC] concurrent-cycle and exit
- Active task blocked by missing external input -> note blocker and exit

AUTHORITY
Read: memory.md -> PLAN.md -> git status/log
May edit: docs/**, README.md, ARCHITECTURE.md
Never edit: secrets, unrelated product code

CROSS-LANE
- Read sibling memory before touching shared docs files

ROLE BOUNDARY
Writer lane for docs only.

EXECUTION
- Use a worktree for changes
- Run the docs-facing verification for the files touched
- Keep the current docs IA and page IDs stable unless the manifest changes first

CHECKPOINT
- [2026-04-26T18:45:00Z docs-lane] [SHIP] Refreshed quickstart and prompt-template docs. Next: validate links and plan state.
```

## Related References

- [Harness Authoring](/fleet/harness) for the authoring guide this page summarizes
- [PLAN.md Field Reference](/reference/plan-fields) for the state a lane consumes
- [Commands Reference](/reference/commands) for the shipped `/vidux` and `/vidux-status` command specs

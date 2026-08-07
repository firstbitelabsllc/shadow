# Commands

| Command | Purpose |
|---|---|
| `shadow init --here` | Create `PLAN.md` without overwriting one. |
| `shadow status --root PATH` | Read current plan rows. |
| `shadow browse --root PATH` | Start the loopback briefing UI. |
| `shadow lint PLAN.md …` | Check plans against the grammar; blocking findings exit non-zero. |
| `shadow accept --row ~hash --repo PATH` | Rerun one row's `cmd` proof in a clean detached checkout; on success flip the row with its paired PROOF line in one commit — the only code path that flips a row. |
| `shadow host probe --host HOST` | Check a native host without using it. |
| `shadow host run …` | Run one sealed task in one clean worktree. |
| `shadow doctor` | Check installation, skill mounts, and native hosts. |

Run `shadow help <command>` for exact flags.



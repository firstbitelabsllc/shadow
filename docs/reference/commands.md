# Commands

Every verb `bin/shadow` dispatches. `shadow help <command>` gives exact flags.

| Command | Purpose |
|---|---|
| `shadow init --here` | Create `PLAN.md` without overwriting one. |
| `shadow status --root PATH` | Read current plan rows. With no plan in the directory, falls back to the portfolio root so the board is the same from anywhere. |
| `shadow status --in-flight` | Every row claimed by `throw` across the portfolio, with its proof and throw time — the recovery view after a chat dies. |
| `shadow goal` | Print the static standing goal to paste into a host's instruction file. Same text every day; only what the plans point at changes. |
| `shadow amp --repo PATH` | Project one paste-ready goal block that POINTS at the plan: authority ref, the resume row, its proof, within one paste budget. |
| `shadow throw --task '~hash' --by <lead>` | Claim a row before work leaves the chat: refuses proofless, needs-blocked, already-thrown, and mid-merge rows, then flips it, records `THROWN` with your name, commits `PLAN.md` alone, and pushes. If another lead pushed first, recovers onto their revision and says whose row it is. |
| `shadow accept --row '~hash' --repo PATH` | Rerun one row's `cmd` proof in a clean detached checkout; on success flip the row with its paired PROOF line in one commit — the only code path that flips a row. |
| `shadow lint PLAN.md …` | Check plans against the grammar; blocking findings exit non-zero. |
| `shadow browse --root PATH` | Start the loopback briefing UI. |
| `shadow host probe --host HOST` | Check a native host without using it. |
| `shadow host run …` | Run one sealed task in one clean worktree. |
| `shadow buckets` | Report which extension buckets are filled. Absent is a WARN and exits 0; a wrong binding FAILs, and so does an *installed* honcho — that bucket's ruling says it is a pattern, never a service. |
| `shadow doctor` | Check installation, skill mounts, native hosts, and whether each host carries the current standing goal. |

## Verifying a host actually works

`shadow doctor` answers *is it installed*. Every one of its host checks is an
existence check, and the failure that matters slips past all of them: a host
that has the files and still opens cold, without the skill, asking which
project to attach to.

```bash
scripts/shadow-verify-host.sh --host claude-code          # offline, free
scripts/shadow-verify-host.sh --host codex --live         # one real session
```

The offline tier proves the mount resolves to this checkout, that nothing
shadows it from another root, that `SKILL.md` frontmatter parses with the name
and description a loader needs, that the standing goal is present and appears
exactly once, that `shadow` on PATH is this checkout, and that the board is
reachable from an unrelated directory through that same command, with a resume
row on it.

`--live` runs one non-interactive session and asserts it returns that resume
row. It is the only check that proves a **session** loads the skill, and it
costs model quota, so it never runs by default — a skipped check says so rather
than leaving a green run implying it happened.

## Two things that bite on the first try

**Quote task ids.** Ids look like `~ab12`, and in zsh — the default macOS shell —
an unquoted `~ab12` is a home-directory expansion, so the command dies with
`no such user or named directory: ab12` before Shadow ever runs. Write
`--task '~ab12'` or `--row "~ab12"`.

**`status` and `browse` take `--root`; `amp`, `throw`, and `accept` take
`--repo`.** The split is deliberate: `--root` is a directory to scan for many
plans, `--repo` is one repository whose plan is being read or written. It is
still easy to reach for the wrong one — the error names the flag it expected.

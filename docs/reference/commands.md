# Commands

Every verb `bin/shadow` dispatches. `shadow help <command>` gives exact flags.

| Command | Purpose |
|---|---|
| `shadow init --here` | Create `PLAN.md` without overwriting one. |
| `shadow status --by <seat> [--root PATH] [--shadowed]` | Read this computer's root board, project authenticated active remote coordination locks for known PLAN rows, then rank checkpoints. `--root` changes only the bounded import root; it never bypasses or writes the board. `--shadowed` adds safe reasons for suppressed or retired copies. |
| `shadow status --in-flight` | Every local claim plus authenticated remote-lock observation, joined at read time to project-owned text and proof — the recovery view after a chat dies. Add `--json` for a machine-readable end-of-chat footer. |
| `shadow config --explain [--repo PATH] [--json]` | Read the optional repository-root `shadow.yaml` declaration, or report the built-in version 1 defaults when it is absent. It prints the attack-then-refute step and active review lenses; the command is read-only and writes no resolved state. |
| `shadow goal [--install|--remove] [--host HOST]` | Print the static standing goal, or install/remove its managed block in supported host instruction files (Claude Code, Codex, Grok). Cursor cold directive activation is unsupported until a reviewed writable user-rule surface exists; its skill mount and sealed host runner remain supported. |
| `shadow amp --entity ID --by <seat>` | Resume a paste-ready packet for a checkpoint already claimed by that seat. It never dispatches unclaimed work. |
| `shadow throw --task '~hash' --by <seat> [--repo PATH\|--entity ID]` | Atomically claim an entity checkpoint before work leaves the seat, then print its packet. A unique legacy text alias such as `P9a~formats` may be supplied, but it resolves to the row's canonical `~hash` before the claim. The board records pointer, canonical row id, owner, lease, and recovery action; the entity plan is unchanged. A configured origin upstream also requires the deterministic remote coordination CAS. `--adopt-expired` replaces only an overdue claim after proof was probed. |
| `shadow return --row '~hash' --by <seat> [--repo PATH\|--entity ID]` | Idempotently append a remote released tombstone when remote coordination is active, then close the named owner's exact local claim after a committed manual proof, a committed blocked state plus one Deferred wake, or an explicit handback, and advance that claim's resume pointer. For a completed remote-only `read` or `gate` claim, the path-free command printed by status first authenticates the acquired journal and current published completion, then appends the completed tombstone without deleting its ref. |
| `shadow priority --value 1..5 [--repo PATH]` | Change the root-board priority under the same local transaction. The project plan's bootstrap value is unchanged and later discovery cannot overwrite the root decision. |
| `shadow accept --row '~hash' (--repo PATH\|--entity ID) --by <seat> [--timeout-seconds N] [--no-push]` | Require that seat's live claim and rerun the committed `cmd` proof in a clean detached checkout. Normally it flips and publishes the paired PROOF commit, appends the remote completed tombstone, then closes the local claim. `--entity` is the path-free recovery form printed by status for a published `cmd` completion whose remote journal remains acquired after the local claim disappeared. A registered machine-local plan instead atomically flips only its private authority after the same clean source-checkout proof. For a remotely coordinated claim, `--no-push` keeps both claims open for a later publishing retry. A rejected push exits 3 naming the pull-request path. `--repo` is the root where proofs RUN, not where the plan lives; a machine-local plan's own directory also works when its committed proof argv changes into the product checkout itself. |
| `shadow lifecycle [--repo PATH] [--json] [--milestone 'heading'\|--retirement-manifest /ABS/file.json]` | Dry-run the hot-plan limits or one exact manifested retirement and emit a CAS. Apply requires explicit `--repo PATH --apply --expect CAS --by <seat>`. Archives are content-addressed, recover exact-CAS half-writes, can monotonically compact an over-limit plan across finite passes, and bind one successor row or `null` once the plan is within limits. Retirement paths must use canonical absolute spellings with no symlink component. It accepts only one clean landed non-primary linked worktree without any submodule, or one clean expired same-entity snapshot recoverable from its declared ref; it journals the exact target, never forces deletion, and commits a path-free receipt with the same bound successor. The named seat claims that row only when present, reachable, and unclaimed; the original CAS makes a completed exact repeat a no-op. |
| `shadow plan migrate /ABS/PLAN.md --dry-run` | Build and verify the complete partitioned candidate with zero writes. Apply requires `--apply --expect SOURCE_SHA256`; `shadow plan rollback … --expect ROOT_SHA256` restores the exact prior root. An optional absolute `--board` binds the receipt while leaving pointers, claims, owners, and resume unchanged. |
| `shadow read /ABS/PLAN.md --row '~hash' --receipt progress:N --expect-root ROOT_SHA256` | Emit one machine-readable, read-only projection of at most eight exact current rows or ordered receipts (128 KiB total), each with root/index/shard/result provenance. It requires a plan-tree root, never materializes the whole plan or follows archive/spill links, and emits no partial content after a missing object, tamper, or root-CAS mismatch. Rows are returned before receipts; both flags are repeatable. |
| `shadow lint [--repo PATH] PLAN.md …` | Check plans against the grammar; blocking findings exit non-zero. A registered machine-local plan uses `--repo` to check proof scripts at its source checkout's committed HEAD. |
| `shadow browse --root PATH [--no-open] [--port N] [--host HOST] [--allow-host NAME ...]` | Start the loopback briefing UI. `--allow-host` (repeatable) only widens the accepted `Host` header for a self-run proxy; the bind stays loopback. |
| `shadow host probe --host HOST` | Check a native host without using it. |
| `shadow host run …` | Run a claimed task in its clean worktree; invoke again for path-disjoint lanes. |
| `shadow slots` | Report which extension slots are filled. Absent is a WARN and exits 0; a wrong binding FAILs. No slot reads tooling Shadow does not itself call. |
| `shadow doctor` | Check installation, skill mounts, native hosts, and whether each host carries the current standing goal. |

## Remote coordination boundary

When the current branch tracks configured `origin`, claim transitions use the
single deterministic branch
`refs/heads/shadow/claims/v1/<entity-id>/<row-id-without-tilde>`. It is a Git
coordination lock, not a remote task board: PLAN owns task state and proof, and
the computer board owns local pointers, priority, claims, leases, and resume.
The tracked upstream is never updated by `shadow throw`.

The remote ruleset must permit create and fast-forward CAS in the
`shadow/claims/v1/` namespace while normal protection remains on `main`. A
refused or lost CAS emits no packet and compensates the exact local attempt. An
unreadable result is ambiguous, not a guessed failure: Shadow emits no packet
and retains the local claim for the same seat to retry. Without a configured
origin upstream, all three verbs retain their local-only behavior and no claim
ref is written.

## Verifying a host actually works

`shadow doctor` answers *is it installed*. Every one of its host checks is an
existence check, and the failure that matters slips past all of them: a host
that has the files and still opens cold, without the skill, asking which
project to attach to.

```bash
scripts/shadow-verify-host.sh --host claude-code --by claude          # offline, free
scripts/shadow-verify-host.sh --host codex --by codex --live          # one real session
scripts/shadow-verify-host.sh --host cursor --by cursor \
  --repo /absolute/path/to/repository --live                          # repo-scoped session
```

The offline tier proves the mount resolves to this checkout, that nothing
shadows it from another root, that `SKILL.md` frontmatter parses with the name
and description a loader needs, that the standing goal is present and appears
exactly once, that `shadow` on PATH is this checkout, and that the board is
reachable from an unrelated directory through that same command, with work for
the named seat on it.

`--live` runs one non-interactive session and asserts it returns the named
seat's owned claim, or that seat's next reachable checkpoint when it owns
nothing. It is time-bounded by `--timeout-seconds` (default: 120); a timeout or
board drift is inconclusive, never green. This is the only check that proves a
**session** loads the skill, and it costs model quota, so it never runs by
default — a skipped check says so rather than leaving a green run implying it
happened.

Cursor's live check is deliberately narrower than global activation. `--repo`
must resolve to an actual Git repository root with a tracked root `AGENTS.md`
or `CLAUDE.md`; the verifier invokes `cursor-agent --print --mode ask
--workspace <root>` with no model or force selector. Omitting `--repo` keeps the
existing explicit skip, and `--repo` is rejected for every other host.

## Verifying two seats coordinate

The two-seat harness is a specialist release check rather than an everyday
board verb:

```bash
scripts/shadow-python.sh scripts/shadow-verify-two-seat.py --json
scripts/shadow-python.sh scripts/shadow-verify-two-seat.py \
  --live --goal-file ./frozen-goal.txt --timeout-seconds 120 --json
```

The offline default invokes no native host. It creates a canonical temporary
HOME, two disposable Git repositories with local bare remotes, and one board;
two deterministic seats then use the real `status`, `throw`, and `accept`
paths. Explicit `--live` spends host quota and gives Claude and Codex the same
frozen goal hash and one freshly fetched `origin/main` ref. Both host process
groups are bounded and drained on every exit. Live mode refuses unless the
executing checkout is clean and exactly at that fetched ref. The final proof
binds each completed row to its historical owner and requires both seats to
refresh status while both claims overlap. Identity mismatch, timeout, board
drift, partial completion, or any orphan claim is inconclusive, never green.
The temporary tree is removed on exit, and the harness reports evidence for
the person-observed gate without flipping that gate itself.

## Two things that bite on the first try

**Quote task ids.** Ids look like `~ab12`, and in zsh — the default macOS shell —
an unquoted `~ab12` is a home-directory expansion, so the command dies with
`no such user or named directory: ab12` before Shadow ever runs. Write
`--task '~ab12'` or `--row "~ab12"`. Old mnemonic labels are accepted only by
`throw` when one canonical row preserves the exact label at the head of its
text; all subsequent commands use the canonical id printed in the packet.

**`status` and `browse` take `--root`; `amp`, `throw`, `return`, `priority`, and `accept` take
`--repo`.** The split is deliberate: `--root` is a directory to scan for many
plans, `--repo` is one repository whose plan is being read or written. It is
still easy to reach for the wrong one — the error names the flag it expected.
